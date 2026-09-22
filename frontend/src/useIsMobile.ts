import { onMounted, onUnmounted, ref } from "vue"

export function useIsMobile() {
  const query = "(max-width: 959px)"
  const isMobile = ref(typeof window !== "undefined" && window.matchMedia(query).matches)

  function sync() {
    isMobile.value = window.matchMedia(query).matches
  }

  onMounted(() => {
    sync()
    window.addEventListener("resize", sync)
  })
  onUnmounted(() => {
    window.removeEventListener("resize", sync)
  })

  return isMobile
}
