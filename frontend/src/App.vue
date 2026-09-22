<script setup lang="ts">
import { computed } from "vue"
import zhCN from "ant-design-vue/es/locale/zh_CN"
import { accent, buildTheme } from "./theme"

const theme = computed(() => buildTheme(accent.value))
</script>

<template>
  <a-config-provider :locale="zhCN" :theme="theme">
    <router-view />
  </a-config-provider>
</template>
