import { ref, watch } from "vue"
import { theme } from "ant-design-vue"

const STORAGE_KEY = "sdnu_rag_accent"
export const DEFAULT_ACCENT = "#E60012"

export const ACCENT_PRESETS = [
  { label: "校红", value: "#E60012" },
  { label: "校蓝", value: "#1B4F8A" },
  { label: "默认蓝", value: "#1677ff" },
  { label: "青绿", value: "#13c2c2" },
  { label: "极光绿", value: "#52c41a" },
  { label: "酱紫", value: "#722ed1" },
] as const

const FONT = `'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif`

function loadAccent(): string {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value && /^#[0-9a-fA-F]{6}$/.test(value)) return value
  } catch {
    /* 读不到时用校红 */
  }
  return DEFAULT_ACCENT
}

export const accent = ref(loadAccent())

export function setAccent(color: string) {
  accent.value = color
  try {
    localStorage.setItem(STORAGE_KEY, color)
  } catch {
    /* 隐私模式写不进去时，本次会话仍然生效 */
  }
}

watch(
  accent,
  (color) => {
    document.documentElement.style.setProperty("--accent", color)
  },
  { immediate: true },
)

export function buildTheme(color: string) {
  return {
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: color,
      colorLink: color,
      colorInfo: color,
      borderRadius: 12,
      colorBgBase: "#fffdf9",
      colorBgLayout: "#f3efe8",
      colorTextBase: "#1c1917",
      colorBorder: "rgba(28,25,23,0.10)",
      colorBorderSecondary: "rgba(28,25,23,0.06)",
      fontFamily: FONT,
      fontSize: 14,
      controlHeight: 36,
    },
    components: {
      Layout: {
        headerBg: "transparent",
        bodyBg: "transparent",
        siderBg: "transparent",
      },
      Card: {
        headerFontSize: 16,
      },
      Menu: {
        itemBorderRadius: 10,
        itemMarginInline: 0,
      },
      Button: {
        fontWeight: 560,
      },
    },
  }
}
