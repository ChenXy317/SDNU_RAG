<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { message } from "ant-design-vue"
import { apiJson } from "../api"

const router = useRouter()
const loading = ref(false)
const loginForm = reactive({ email: "", password: "" })
const registerForm = reactive({ email: "", password: "" })

async function enter(path: string, body: { email: string; password: string }, okText: string) {
  loading.value = true
  try {
    const data = await apiJson<{ access_token: string }>(path, {
      method: "POST",
      body: JSON.stringify(body),
    })
    localStorage.setItem("access_token", data.access_token)
    message.success(okText)
    router.push("/chat")
  } catch (err) {
    message.error(err instanceof Error ? err.message : "失败")
  } finally {
    loading.value = false
  }
}

function onLogin() {
  return enter("/api/v1/auth/login", loginForm, "登录成功")
}

function onRegister() {
  return enter("/api/v1/auth/register", registerForm, "注册成功")
}
</script>

<template>
  <div class="login-shell">
    <aside class="login-brand">
      <img class="login-brand-art" src="/login-art.jpg" alt="" />
      <div class="login-brand-scrim" />
      <div class="login-brand-inner">
        <img class="login-emblem" src="/sdnu-emblem-128.png" alt="山东师范大学校徽" width="72" height="72" />
        <h1>山东师范大学</h1>
        <p class="login-motto">弘德明志 · 博学笃行</p>
        <p class="login-en">Shandong Normal University · Knowledge Base</p>
        <ul class="login-points">
          <li>公共语料与个人文档分开检索，答案带来源</li>
          <li>流式对话，引用先于回答出现</li>
          <li>上传 txt，并按账号切换对话模型</li>
        </ul>
      </div>
    </aside>
    <main class="login-panel">
      <a-card class="login-card" :bordered="false">
        <div class="login-card-head">
          <h2>欢迎回来</h2>
          <p class="hint">注册或登录后即可提问。密码至少 8 位。</p>
        </div>
        <a-tabs>
          <a-tab-pane key="login" tab="登录">
            <a-form layout="vertical" :model="loginForm" @finish="onLogin">
              <a-form-item label="邮箱" name="email" :rules="[{ required: true, type: 'email', message: '请填写邮箱' }]">
                <a-input v-model:value="loginForm.email" size="large" placeholder="you@example.com" />
              </a-form-item>
              <a-form-item label="密码" name="password" :rules="[{ required: true, min: 8, message: '密码至少 8 位' }]">
                <a-input-password v-model:value="loginForm.password" size="large" />
              </a-form-item>
              <a-button type="primary" html-type="submit" block size="large" :loading="loading">登录</a-button>
            </a-form>
          </a-tab-pane>
          <a-tab-pane key="register" tab="注册">
            <a-form layout="vertical" :model="registerForm" @finish="onRegister">
              <a-form-item label="邮箱" name="email" :rules="[{ required: true, type: 'email', message: '请填写邮箱' }]">
                <a-input v-model:value="registerForm.email" size="large" placeholder="you@example.com" />
              </a-form-item>
              <a-form-item label="密码" name="password" :rules="[{ required: true, min: 8, message: '密码至少 8 位' }]">
                <a-input-password v-model:value="registerForm.password" size="large" />
              </a-form-item>
              <a-button type="primary" html-type="submit" block size="large" :loading="loading">注册并进入</a-button>
            </a-form>
          </a-tab-pane>
        </a-tabs>
      </a-card>
    </main>
  </div>
</template>
