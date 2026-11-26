import type { Identity, LiveEvent } from '../domain/models'

import { ApiError, type ErrorBody } from '../application/transport'
export { ApiError }

const channel = new BroadcastChannel('codeforge.session')
const listeners = new Set<() => void>()
let access: string | null = null
let pending: Promise<string | null> | undefined
let revision = 0

function update(token: string | null, broadcast = false) {
  access = token
  if (token) localStorage.setItem('cf.session', '1')
  else localStorage.removeItem('cf.session')
  revision += 1
  if (broadcast) channel.postMessage(token)
  listeners.forEach((listener) => listener())
}
channel.onmessage = (message: MessageEvent<string | null>) => update(message.data)

export const session = {
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  },
  get: () => access,
  hasSession: () => localStorage.getItem('cf.session') === '1',
  clear: () => update(null, true),
  refresh,
  async login(email: string, password: string) {
    const result = await lock(() =>
      api<{ access_token: string }>('/auth/login', {
        method: 'POST',
        body: { email, password },
        retry: false,
      }).then((value) => {
        update(value.access_token, true)
        return value
      }),
    )
    return result.access_token
  },
  async logout() {
    await lock(async () => {
      await api<void>('/auth/logout', { method: 'POST', retry: false })
      update(null, true)
    })
  },
  me: () => api<Identity>('/auth/me'),
}

function lock<T>(task: () => Promise<T>): Promise<T> {
  return navigator.locks
    ? navigator.locks.request('codeforge.session', task).then((value) => value)
    : task()
}

function refresh(): Promise<string | null> {
  if (pending) return pending
  const requested = revision
  pending = lock(async () => {
    if (revision !== requested) return access
    const response = await fetch('/api/auth/refresh', { method: 'POST', cache: 'no-store' })
    if (response.status >= 500)
      throw new ApiError(response.status, {
        code: 'unavailable',
        detail: 'Service unavailable',
      })
    const token = response.ok
      ? ((await response.json()) as { access_token: string }).access_token
      : null
    update(token, true)
    return token
  }).finally(() => {
    pending = undefined
  })
  return pending
}

type Options = {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  retry?: boolean
  signal?: AbortSignal
}
export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const response = await request(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function request(path: string, options: Options = {}): Promise<Response> {
  const used = access
  const fetchWith = (token: string | null) =>
    fetch(`/api${path}`, {
      method: options.method ?? 'GET',
      signal: options.signal,
      cache: 'no-store',
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
        ...(options.body !== undefined && { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  let response = await fetchWith(used)
  if (response.status === 401 && options.retry !== false && (used || session.hasSession())) {
    const token = used !== access ? access : await refresh()
    if (token) response = await fetchWith(token)
  }
  if (!response.ok) {
    const body: ErrorBody = await response.json().catch(() => ({
      code: 'unavailable',
      detail: 'Service unavailable',
    }))
    throw new ApiError(response.status, body)
  }
  return response
}

export function connect(
  path: string,
  onEvent: (event: LiveEvent) => void,
  onState: (online: boolean) => void,
) {
  let closed = false
  let delay = 1000
  let timer: number | undefined
  let socket: WebSocket | undefined

  function reconnect() {
    if (closed) return
    onState(false)
    timer = window.setTimeout(() => {
      void open()
    }, delay)
    delay = Math.min(delay * 2, 30_000)
  }

  async function open() {
    try {
      let token = access
      if (token) {
        const body = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
        if (body.exp * 1000 <= Date.now() + 15_000) token = await refresh()
      }
      if (closed || !token) return
      const { ticket } = await api<{ ticket: string }>('/auth/socket-ticket', { method: 'POST' })
      if (closed) return
      const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(
        `${scheme}//${location.host}${path}?ticket=${encodeURIComponent(ticket)}`,
      )
      socket.onopen = () => {
        delay = 1000
        onState(true)
      }
      socket.onmessage = (message: MessageEvent<string>) =>
        onEvent(JSON.parse(message.data) as LiveEvent)
      socket.onclose = reconnect
    } catch {
      reconnect()
    }
  }

  void open()
  return () => {
    closed = true
    window.clearTimeout(timer)
    socket?.close()
  }
}
