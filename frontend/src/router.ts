import { createRouter, createWebHistory } from "vue-router"
import AppLayout from "./layout/AppLayout.vue"
import Login from "./pages/Login.vue"
import Chat from "./pages/Chat.vue"
import Docs from "./pages/Docs.vue"
import Settings from "./pages/Settings.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login },
    {
      path: "/",
      component: AppLayout,
      children: [
        { path: "", redirect: "/chat" },
        { path: "chat", component: Chat },
        { path: "docs", component: Docs },
        { path: "settings", component: Settings },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/chat" },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem("access_token")
  if (to.path !== "/login" && !token) return "/login"
  if (to.path === "/login" && token) return "/chat"
  return true
})

export default router
