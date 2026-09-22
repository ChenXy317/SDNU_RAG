<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import { message } from "ant-design-vue"
import { CheckOutlined, ReloadOutlined } from "@ant-design/icons-vue"
import { apiJson } from "../api"
import { ACCENT_PRESETS, accent, setAccent } from "../theme"

type LLMConfig = {
  base_url: string
  model: string
  api_key_set: boolean
  embedding_model: string
  local_models: string[]
}

const loading = ref(false)
const saving = ref(false)
const current = ref<LLMConfig | null>(null)
const form = reactive({
  base_url: "",
  model: "",
  api_key: "",
})

async function load() {
  loading.value = true
  try {
    const data = await apiJson<LLMConfig>("/api/v1/llm/config")
    current.value = data
    form.base_url = data.base_url
    form.model = data.model
    form.api_key = ""
  } catch (err) {
    message.error(err instanceof Error ? err.message : "加载配置失败")
  } finally {
    loading.value = false
  }
}

async function save(clearKey = false) {
  saving.value = true
  try {
    const body: { base_url: string; model: string; api_key?: string } = {
      base_url: form.base_url.trim(),
      model: form.model.trim(),
    }
    if (clearKey) body.api_key = ""
    else if (form.api_key) body.api_key = form.api_key
    const data = await apiJson<LLMConfig>("/api/v1/llm/config", {
      method: "PUT",
      body: JSON.stringify(body),
    })
    current.value = data
    form.base_url = data.base_url
    form.model = data.model
    form.api_key = ""
    message.success("对话模型已切换")
  } catch (err) {
    message.error(err instanceof Error ? err.message : "保存失败")
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <a-card class="surface-card" title="外观">
      <p class="hint">暖色纸感底。强调色作用于按钮、链接、菜单选中态和自己的对话气泡。</p>
      <div class="accent-label">强调色</div>
      <div class="accent-row">
        <button
          v-for="item in ACCENT_PRESETS"
          :key="item.value"
          type="button"
          :title="item.label"
          class="accent-swatch"
          :class="{ 'is-selected': accent.toLowerCase() === item.value.toLowerCase() }"
          :style="{ background: item.value }"
          @click="setAccent(item.value)"
        >
          <CheckOutlined v-if="accent.toLowerCase() === item.value.toLowerCase()" />
        </button>
      </div>
    </a-card>

    <a-card class="surface-card" title="对话模型">
      <template #extra>
        <a-button :loading="loading" @click="load">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </template>
      <p class="hint">
        只改当前账号的对话接口，下一次提问就用新模型。配置留在进程内存里，重启服务后回到环境变量。
        向量模型是 {{ current?.embedding_model || "—" }}，这里不能改。
      </p>
      <a-descriptions class="settings-desc" bordered :column="1" size="small">
        <a-descriptions-item label="当前地址">{{ current?.base_url || "—" }}</a-descriptions-item>
        <a-descriptions-item label="当前模型">{{ current?.model || "—" }}</a-descriptions-item>
        <a-descriptions-item label="密钥">
          {{ current ? (current.api_key_set ? "已设置" : "未设置") : "—" }}
        </a-descriptions-item>
        <a-descriptions-item label="向量模型">{{ current?.embedding_model || "—" }}</a-descriptions-item>
      </a-descriptions>
      <a-form layout="vertical" style="margin-top: 16px" @finish="() => save(false)">
        <a-form-item label="base_url" required>
          <a-input v-model:value="form.base_url" placeholder="http://127.0.0.1:11434/v1" />
        </a-form-item>
        <a-form-item label="api_key" extra="不填表示保持原值。本机 Ollama 可以不填。">
          <a-input-password v-model:value="form.api_key" placeholder="不修改请留空" />
        </a-form-item>
        <a-form-item label="model" required>
          <a-input v-model:value="form.model" placeholder="qwen2.5:1.5b" />
          <div v-if="current?.local_models.length" class="models">
            <span class="hint">本机 Ollama：</span>
            <a-button v-for="name in current.local_models" :key="name" size="small" @click="form.model = name">
              {{ name }}
            </a-button>
          </div>
        </a-form-item>
        <a-space wrap>
          <a-button type="primary" html-type="submit" :loading="saving">应用配置</a-button>
          <a-button :loading="saving" @click="save(true)">清除密钥</a-button>
        </a-space>
      </a-form>
    </a-card>
  </div>
</template>
