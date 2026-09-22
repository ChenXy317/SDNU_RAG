<script setup lang="ts">
import { onMounted, ref } from "vue"
import { message } from "ant-design-vue"
import { FileTextOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons-vue"
import { api, apiJson, formatDetail, type DocumentItem } from "../api"
import { useIsMobile } from "../useIsMobile"

const statusMeta: Record<string, { color: string; label: string }> = {
  pending: { color: "default", label: "待处理" },
  processing: { color: "processing", label: "处理中" },
  succeeded: { color: "success", label: "已就绪" },
  failed: { color: "error", label: "失败" },
}

const isMobile = useIsMobile()
const items = ref<DocumentItem[]>([])
const loading = ref(false)
const uploading = ref(false)

function statusOf(value: string) {
  return statusMeta[value] || { color: "default", label: value }
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const columns = [
  { title: "文件", dataIndex: "filename", key: "filename" },
  { title: "状态", dataIndex: "status", key: "status", width: 110 },
  { title: "说明", dataIndex: "error_message", key: "error_message", ellipsis: true },
  { title: "片段", dataIndex: "chunk_count", key: "chunk_count", width: 80 },
  { title: "上传时间", dataIndex: "created_at", key: "created_at", width: 170 },
]

async function load() {
  loading.value = true
  try {
    const data = await apiJson<{ items: DocumentItem[] }>("/api/v1/documents")
    items.value = data.items
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载失败")
  } finally {
    loading.value = false
  }
}

async function onUpload(file: File) {
  if (!file.name.toLowerCase().endsWith(".txt")) {
    message.error("只接收 txt")
    return false
  }
  const form = new FormData()
  form.append("file", file)
  uploading.value = true
  try {
    const resp = await api("/api/v1/ingest", { method: "POST", body: form })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(formatDetail(data.detail))
    message.success("上传完成")
  } catch (err) {
    message.error(err instanceof Error ? err.message : "上传失败")
  } finally {
    uploading.value = false
    await load()
  }
  return false
}

onMounted(load)
</script>

<template>
  <a-card class="surface-card" :title="`我的文档 · ${items.length} 篇`">
    <template v-if="!isMobile" #extra>
      <a-space wrap class="docs-toolbar">
        <a-button @click="load">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
        <a-upload :show-upload-list="false" accept=".txt" :before-upload="onUpload">
          <a-button type="primary" :loading="uploading">
            <template #icon><UploadOutlined /></template>
            上传 txt
          </a-button>
        </a-upload>
      </a-space>
    </template>
    <div v-if="isMobile" class="docs-toolbar-wrap">
      <a-space wrap class="docs-toolbar">
        <a-button @click="load">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
        <a-upload :show-upload-list="false" accept=".txt" :before-upload="onUpload">
          <a-button type="primary" :loading="uploading">
            <template #icon><UploadOutlined /></template>
            上传 txt
          </a-button>
        </a-upload>
      </a-space>
    </div>
    <p class="hint">这里是当前账号上传的 txt。同名文件会覆盖。公共语料不在这个列表里。</p>
    <div v-if="isMobile" class="doc-list">
      <a-spin :spinning="loading">
        <p v-if="!loading && !items.length" class="hint">暂无文档</p>
        <article v-for="row in items" :key="row.id" class="doc-card">
          <div class="doc-card-title">
            <FileTextOutlined style="color: var(--navy)" />
            <span>{{ row.filename }}</span>
          </div>
          <div class="doc-card-meta">
            <a-tag :color="statusOf(row.status).color">{{ statusOf(row.status).label }}</a-tag>
            <span>片段 {{ row.chunk_count }}</span>
            <span>{{ formatTime(row.created_at) }}</span>
          </div>
          <div v-if="row.status === 'failed'" class="doc-card-error">{{ row.error_message || "入库失败" }}</div>
        </article>
      </a-spin>
    </div>
    <a-table
      v-else
      row-key="id"
      :loading="loading"
      :columns="columns"
      :data-source="items"
      :pagination="false"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'filename'">
          <span class="doc-card-title">
            <FileTextOutlined style="color: var(--navy)" />
            <span>{{ record.filename }}</span>
          </span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="statusOf(record.status).color">{{ statusOf(record.status).label }}</a-tag>
        </template>
        <template v-else-if="column.key === 'error_message'">
          {{ record.status === "failed" ? record.error_message || "入库失败" : "—" }}
        </template>
        <template v-else-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
      </template>
    </a-table>
  </a-card>
</template>
