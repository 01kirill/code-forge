import type { Identity, LiveEvent } from '../domain/models'

export type ErrorBody = {
  code: string
  detail: string
  context?: Record<string, string>
  errors?: { field: string; type: string }[]
}
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorBody,
  ) {
    super(body.detail)
  }
}

export type SessionTransport = {
  session: {
    subscribe: (listener: () => void) => () => void
    get: () => string | null
    hasSession: () => boolean
    clear: () => void
    refresh: () => Promise<string | null>
    me: () => Promise<Identity>
  }
  connect: (
    path: string,
    onEvent: (event: LiveEvent) => void,
    onState: (online: boolean) => void,
  ) => () => void
}
