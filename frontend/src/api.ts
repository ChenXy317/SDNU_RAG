export type Citation = {
  filename: string
  chunk_index: number
  text: string
  score: number
  source: "public" | "user" | string
}

export type SessionItem = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export type MessageItem = {
  id: string
  role: "user" | "assistant" | string
  content: string
  citations: Citation[] | null
  created_at?: string
}

export type DocumentItem = {
  id: string
  filename: string
  status: string
  chunk_count: number
  created_at: string
  error_message?: string | null
}

export function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) return String(item.msg)
        return String(item)
      })
      .join("；")
  }
  if (detail == null) return "请求失败"
  return String(detail)
}

export async function api(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers)
  const token = localStorage.getItem("access_token")
  if (token) headers.set("Authorization", `Bearer ${token}`)
  const resp = await fetch(path, { ...options, headers })
  if (resp.status === 401) {
    localStorage.removeItem("access_token")
    if (!location.pathname.startsWith("/login")) location.assign("/login")
    throw new Error("未登录")
  }
  return resp
}

export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set("Content-Type", "application/json")
  const resp = await api(path, { ...options, headers })
  if (resp.status === 204) return undefined as T
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(formatDetail(data.detail))
  return data as T
}

function emitFrame(frame: string, onEvent: (event: string, data: any) => void) {
  let event = "message"
  const dataLines: string[] = []
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim()
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return
  onEvent(event, JSON.parse(dataLines.join("\n")))
}

export async function streamChat(
  sessionId: string,
  message: string,
  onEvent: (event: string, data: any) => void,
  signal?: AbortSignal,
) {
  const resp = await api("/api/v1/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  })
  if (!resp.ok || !resp.body) {
    const data = await resp.json().catch(() => ({}))
    throw new Error(formatDetail(data.detail))
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = buffer.replace(/\r\n/g, "\n")
    const frames = buffer.split("\n\n")
    buffer = frames.pop() ?? ""
    for (const frame of frames) {
      if (frame.trim()) emitFrame(frame, onEvent)
    }
  }
  if (buffer.trim()) emitFrame(buffer, onEvent)
}
