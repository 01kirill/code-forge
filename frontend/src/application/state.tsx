import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react'

import type { Identity, LiveEvent } from '../domain/models'
import { ApiError, type SessionTransport } from './transport'

type SessionState = { user: Identity | null; ready: boolean; error: unknown; reload: () => void }
const SessionContext = createContext<(SessionState & SessionTransport) | null>(null)

export function SessionProvider({
  children,
  transport,
}: {
  children: ReactNode
  transport: SessionTransport
}) {
  const { session } = transport
  const token = useSyncExternalStore(session.subscribe, session.get)
  const [ready, setReady] = useState(false)
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [sessionError, setSessionError] = useState<unknown>(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let current = true
    setSessionError(null)
    async function load() {
      try {
        if (token || (!ready && session.hasSession() && (await session.refresh()))) {
          const user = await session.me()
          if (current) setIdentity(user)
        }
      } catch (error) {
        if (!current) return
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          setIdentity(null)
          if (session.get()) session.clear()
        } else setSessionError(error)
      } finally {
        if (current) setReady(true)
      }
    }
    void load()
    return () => {
      current = false
    }
    // Ready marks the initial refresh. It must not trigger a second refresh after logout.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, revision, session])

  return (
    <SessionContext.Provider
      value={{
        ...transport,
        user: token ? identity : null,
        ready: ready && (!token || identity !== null || sessionError !== null),
        error: sessionError,
        reload: () => {
          setReady(false)
          setRevision((n) => n + 1)
        },
      }}
    >
      {children}
    </SessionContext.Provider>
  )
}

export function useSession(): SessionState {
  return useSessionContext()
}

function useSessionContext(): SessionState & SessionTransport {
  const context = useContext(SessionContext)
  if (!context) throw new Error('SessionProvider is required')
  return context
}

type Loading<T> = { data?: T; error?: unknown }
export function useLoad<T>(key: string, load: () => Promise<T>, enabled = true) {
  const [state, setState] = useState<Loading<T> & { key?: string }>({})
  const [revision, setRevision] = useState(0)
  const loader = useRef(load)
  loader.current = load
  useEffect(() => {
    if (!enabled) return
    let current = true
    loader.current().then(
      (data) => {
        if (current) setState({ key, data })
      },
      (error: unknown) => {
        if (current)
          setState((old) => ({
            key,
            data: old.key === key ? old.data : undefined,
            error,
          }))
      },
    )
    return () => {
      current = false
    }
  }, [key, revision, enabled])
  return {
    ...(state.key === key && enabled ? state : {}),
    reload: () => setRevision((n) => n + 1),
    set: (data: T) => setState({ key, data }),
  }
}

export function useLive(
  path: string | null,
  onEvent: (event: LiveEvent) => void,
  onReconnect?: () => void,
) {
  const { session, connect } = useSessionContext()
  const token = useSyncExternalStore(session.subscribe, session.get)
  const [online, setOnline] = useState(true)
  const event = useRef(onEvent)
  const restore = useRef(onReconnect)
  event.current = onEvent
  restore.current = onReconnect
  useEffect(() => {
    if (!path || !token) return
    return connect(
      path,
      (message) => event.current(message),
      (connected) => {
        setOnline(connected)
        if (connected) restore.current?.()
      },
    )
  }, [path, token, connect])
  return online
}

const education = new EventTarget()

export function sendEducation(event?: LiveEvent) {
  education.dispatchEvent(new CustomEvent('update', { detail: event }))
}

export function useEducation(handler: (event?: LiveEvent) => void) {
  const latest = useRef(handler)
  latest.current = handler
  useEffect(() => {
    const listener = (event: Event) => latest.current((event as CustomEvent<LiveEvent>).detail)
    education.addEventListener('update', listener)
    return () => education.removeEventListener('update', listener)
  }, [])
}
