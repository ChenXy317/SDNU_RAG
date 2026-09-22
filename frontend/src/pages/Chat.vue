<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue"
import { message } from "ant-design-vue"
import { DeleteOutlined, PlusOutlined, SendOutlined, UnorderedListOutlined } from "@ant-design/icons-vue"
import { apiJson, streamChat, type Citation, type MessageItem, type SessionItem } from "../api"
import { useIsMobile } from "../useIsMobile"

const suggestions = [
  "山东师范大学的校训是什么？",
  "学校有哪些校区？",
  "本科招生如何录取？",
  "图书馆开放情况怎样？",
]

const isMobile = useIsMobile()
const sessions = ref<SessionItem[]>([])
const currentId = ref("")
const messages = ref<MessageItem[]>([])
const input = ref("")
const streaming = ref(false)
const loadingSessions = ref(false)
const loadingHistory = ref(false)
const sessionsOpen = ref(false)
const bottomRef = ref<HTMLElement | null>(null)
let abortController: AbortController | null = null

function abortStream() {
  abortController?.abort()
  abortController = null
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    const data = await apiJson<{ items: SessionItem[] }>("/api/v1/sessions")
    sessions.value = data.items
  } finally {
    loadingSessions.value = false
  }
}

async function openSession(id: string) {
  if (streaming.value || id === currentId.value) {
    sessionsOpen.value = false
    return
  }
  abortStream()
  currentId.value = id
  sessionsOpen.value = false
  loadingHistory.value = true
  try {
    const data = await apiJson<{ messages: MessageItem[] }>(`/api/v1/sessions/${id}`)
    if (currentId.value === id) messages.value = data.messages
  } catch (err) {
    if (currentId.value === id) {
      messages.value = []
      message.error(err instanceof Error ? err.message : "加载历史失败")
    }
  } finally {
    if (currentId.value === id) loadingHistory.value = false
  }
}

async function createSession() {
  abortStream()
  streaming.value = false
  const created = await apiJson<SessionItem>("/api/v1/sessions", { method: "POST" })
  currentId.value = created.id
  messages.value = []
  sessionsOpen.value = false
  await loadSessions()
}

async function removeSession(id: string) {
  if (currentId.value === id) abortStream()
  await apiJson(`/api/v1/sessions/${id}`, { method: "DELETE" })
  if (currentId.value === id) {
    currentId.value = ""
    messages.value = []
    streaming.value = false
  }
  await loadSessions()
}

function sourceLabel(source: string) {
  return source === "user" ? "用户" : "公共"
}

async function scrollDown() {
  await nextTick()
  bottomRef.value?.scrollIntoView({ behavior: "smooth", block: "end" })
}

function onPressEnter(event: KeyboardEvent) {
  if (event.shiftKey) return
  event.preventDefault()
  void send()
}

async function send(preset?: string) {
  const text = (preset ?? input.value).trim()
  if (!text || streaming.value) return
  if (!currentId.value) {
    try {
      await createSession()
    } catch (err) {
      message.error(err instanceof Error ? err.message : "创建会话失败")
      return
    }
  }
  input.value = ""
  streaming.value = true
  messages.value.push({ id: `local-user-${Date.now()}`, role: "user", content: text, citations: null })
  const draft: MessageItem = {
    id: `local-assistant-${Date.now()}`,
    role: "assistant",
    content: "",
    citations: [],
  }
  messages.value.push(draft)
  const controller = new AbortController()
  abortController = controller
  try {
    await streamChat(
      currentId.value,
      text,
      (event, data) => {
        if (event === "citation") {
          draft.citations = draft.citations || []
          draft.citations.push(data as Citation)
        } else if (event === "token") {
          draft.content += String(data.text || "")
        } else if (event === "done") {
          draft.id = String(data.message_id || draft.id)
          draft.content = String(data.answer || draft.content)
        } else if (event === "error") {
          message.error(String(data.detail || "生成失败"))
          messages.value = messages.value.filter((item) => item !== draft)
        }
      },
      controller.signal,
    )
    await loadSessions()
  } catch (err) {
    if (!(err instanceof DOMException && err.name === "AbortError")) {
      message.error(err instanceof Error ? err.message : "发送失败")
      messages.value = messages.value.filter((item) => item !== draft)
    }
  } finally {
    if (abortController === controller) abortController = null
    streaming.value = false
  }
}

watch(messages, () => scrollDown(), { deep: true })

onMounted(async () => {
  try {
    await loadSessions()
    if (sessions.value.length) await openSession(sessions.value[0].id)
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载会话失败")
  }
})
</script>

<template>
  <div class="chat-grid" :class="{ 'is-mobile': isMobile }">
    <a-drawer
      v-if="isMobile"
      title="会话"
      placement="left"
      :open="sessionsOpen"
      width="86vw"
      :body-style="{ padding: '8px 0' }"
      @close="sessionsOpen = false"
    >
      <template #extra>
        <a-button size="small" type="primary" ghost @click="createSession">
          <template #icon><PlusOutlined /></template>
          新建
        </a-button>
      </template>
      <a-spin :spinning="loadingSessions">
        <p v-if="!sessions.length" class="hint" style="padding: 20px; text-align: center">暂无会话，直接提问或点新建。</p>
        <div
          v-for="item in sessions"
          :key="item.id"
          class="session-item"
          :class="{ 'is-active': item.id === currentId }"
          @click="openSession(item.id)"
        >
          <span class="session-title">{{ item.title || "未命名会话" }}</span>
          <a-button type="text" size="small" danger @click.stop="removeSession(item.id)">
            <template #icon><DeleteOutlined /></template>
          </a-button>
        </div>
      </a-spin>
    </a-drawer>
    <a-card v-else class="surface-card" size="small" title="会话" :body-style="{ padding: '8px 0', overflow: 'auto' }">
      <template #extra>
        <a-button size="small" type="primary" ghost @click="createSession">
          <template #icon><PlusOutlined /></template>
          新建
        </a-button>
      </template>
      <a-spin :spinning="loadingSessions">
        <p v-if="!sessions.length" class="hint" style="padding: 20px; text-align: center">暂无会话，直接提问或点新建。</p>
        <div
          v-for="item in sessions"
          :key="item.id"
          class="session-item"
          :class="{ 'is-active': item.id === currentId }"
          @click="openSession(item.id)"
        >
          <span class="session-title">{{ item.title || "未命名会话" }}</span>
          <a-button type="text" size="small" danger @click.stop="removeSession(item.id)">
            <template #icon><DeleteOutlined /></template>
          </a-button>
        </div>
      </a-spin>
    </a-card>

    <a-card
      class="surface-card chat-main"
      :title="isMobile ? '对话' : '与山师知识库对话'"
      :body-style="{ display: 'flex', flexDirection: 'column', minHeight: 0, paddingTop: '12px' }"
    >
      <template v-if="isMobile" #extra>
        <a-button size="small" @click="sessionsOpen = true">
          <template #icon><UnorderedListOutlined /></template>
          会话
        </a-button>
        <a-button size="small" type="primary" ghost @click="createSession">
          <template #icon><PlusOutlined /></template>
        </a-button>
      </template>
      <div class="chat-thread">
        <a-spin :spinning="loadingHistory">
          <div v-if="!messages.length && !loadingHistory" class="chat-empty">
            <img src="/sdnu-emblem-64.png" alt="" width="56" height="56" />
            <h3>了解山东师范大学</h3>
            <span class="hint">弘德明志，博学笃行 · 从校训、校区到招生就业</span>
            <div class="suggest-row">
              <button v-for="item in suggestions" :key="item" type="button" class="suggest-chip" @click="send(item)">
                {{ item }}
              </button>
            </div>
          </div>
          <div v-for="msg in messages" :key="msg.id" class="bubble-row" :class="msg.role">
            <div class="bubble-stack">
              <div class="bubble" :class="msg.role">
                <template v-if="msg.content">{{ msg.content }}</template>
                <template v-else-if="streaming && msg.role === 'assistant'">正在检索…</template>
                <a-collapse v-if="msg.citations?.length" size="small" style="margin-top: 8; background: #fff">
                  <a-collapse-panel :key="msg.id" :header="`引用 · ${msg.citations.length} 条`">
                    <div v-for="(cite, index) in msg.citations" :key="index" class="cite-block">
                      <strong>{{ sourceLabel(cite.source) }} · {{ cite.filename }}</strong>
                      <span class="hint"> · #{{ cite.chunk_index }} · {{ Number(cite.score).toFixed(3) }}</span>
                      <div class="cite-text">{{ cite.text }}</div>
                    </div>
                  </a-collapse-panel>
                </a-collapse>
              </div>
            </div>
          </div>
          <div ref="bottomRef" />
        </a-spin>
      </div>
      <div class="composer">
        <a-textarea
          v-model:value="input"
          :bordered="false"
          :auto-size="{ minRows: 1, maxRows: isMobile ? 3 : 4 }"
          :placeholder="isMobile ? '输入问题' : '输入问题，Enter 发送 · Shift+Enter 换行'"
          :disabled="streaming"
          @press-enter="onPressEnter"
        />
        <a-button type="primary" shape="round" :loading="streaming" aria-label="发送" @click="send()">
          <template #icon><SendOutlined /></template>
          <span v-if="!isMobile">发送</span>
        </a-button>
      </div>
    </a-card>
  </div>
</template>
