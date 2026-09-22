<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { FileTextOutlined, LogoutOutlined, MessageOutlined, SettingOutlined } from "@ant-design/icons-vue"
import { apiJson } from "../api"
import { useIsMobile } from "../useIsMobile"

const route = useRoute()
const router = useRouter()
const email = ref("")
const collapsed = ref(false)
const isMobile = useIsMobile()

const nav = [
  { key: "chat", label: "对话", fullLabel: "知识库对话", to: "/chat", icon: MessageOutlined },
  { key: "docs", label: "文档", fullLabel: "文档管理", to: "/docs", icon: FileTextOutlined },
  { key: "settings", label: "设置", fullLabel: "设置", to: "/settings", icon: SettingOutlined },
]

const headings: Record<string, { kicker: string; title: string }> = {
  chat: { kicker: "Knowledge", title: "知识库对话" },
  docs: { kicker: "Corpus", title: "文档管理" },
  settings: { kicker: "System", title: "设置" },
}

const activeKey = computed(() => {
  if (route.path.startsWith("/docs")) return "docs"
  if (route.path.startsWith("/settings")) return "settings"
  return "chat"
})
const heading = computed(() => headings[activeKey.value])
const initial = computed(() => (email.value || "U").slice(0, 1).toUpperCase())

async function loadMe() {
  if (!localStorage.getItem("access_token")) return
  try {
    const me = await apiJson<{ id: string; email: string }>("/api/v1/auth/me")
    email.value = me.email
  } catch {
    email.value = ""
  }
}

function logout() {
  localStorage.removeItem("access_token")
  email.value = ""
  router.push("/login")
}

onMounted(loadMe)
</script>

<template>
  <a-layout class="app-shell" :class="{ 'is-mobile': isMobile }">
    <a-layout-sider
      v-if="!isMobile"
      v-model:collapsed="collapsed"
      class="app-sider"
      theme="light"
      collapsible
      :width="232"
      :collapsed-width="72"
      breakpoint="lg"
    >
      <div class="brand-lockup" :class="{ 'is-collapsed': collapsed }">
        <img src="/sdnu-emblem-64.png" alt="山东师范大学校徽" width="40" height="40" />
        <div v-if="!collapsed">
          <div class="brand-name">山东师范大学</div>
          <div class="brand-sub">知识库问答</div>
        </div>
      </div>
      <p v-if="!collapsed" class="brand-motto">弘德明志 · 博学笃行</p>
      <a-menu class="app-menu" mode="inline" :selected-keys="[activeKey]">
        <a-menu-item v-for="item in nav" :key="item.key">
          <template #icon>
            <component :is="item.icon" />
          </template>
          <router-link :to="item.to">{{ item.fullLabel }}</router-link>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="app-header">
        <div v-if="isMobile" class="header-brand-mini">
          <img src="/sdnu-emblem-64.png" alt="" width="28" height="28" />
          <div class="header-title">{{ heading.title }}</div>
        </div>
        <div v-else>
          <div class="header-kicker">{{ heading.kicker }}</div>
          <div class="header-title">{{ heading.title }}</div>
        </div>
        <div class="header-user">
          <div v-if="!isMobile" class="user-chip">
            <span class="user-avatar">{{ initial }}</span>
            <span class="user-email">{{ email }}</span>
          </div>
          <a-button class="logout-btn" @click="logout">
            <template #icon><LogoutOutlined /></template>
            <span class="logout-label">退出</span>
          </a-button>
        </div>
      </a-layout-header>
      <a-layout-content class="app-content" :class="{ 'is-mobile': isMobile }">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
  <nav v-if="isMobile" class="app-tabbar" aria-label="主导航">
    <button
      v-for="item in nav"
      :key="item.key"
      type="button"
      :class="{ 'is-active': item.key === activeKey }"
      @click="router.push(item.to)"
    >
      <component :is="item.icon" />
      <span>{{ item.label }}</span>
    </button>
  </nav>
</template>
