import { useState, type FormEvent, type ReactNode } from 'react'
import { ArrowRight, CircleAlert, LoaderCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '../infrastructure/api'

export function Loading() {
  const { t } = useTranslation()
  return (
    <p className="notice" role="status">
      <LoaderCircle size={18} className="spin" aria-hidden />
      {t('Loading…')}
    </p>
  )
}

export function ErrorMessage({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t, i18n } = useTranslation()
  if (!error) return null
  const key = error instanceof ApiError ? `errors.${error.body.code}` : ''
  const message =
    error instanceof ApiError
      ? i18n.exists(key)
        ? t(key)
        : i18n.language === 'ru'
          ? error.message
          : t('Network error. Try again.')
      : error instanceof Error && error.message
        ? error.message
        : t('Network error. Try again.')
  return (
    <div className="notice error" role="alert">
      <CircleAlert size={18} aria-hidden />
      <span>{message}</span>
      {retry && (
        <button type="button" className="text-button" onClick={retry}>
          {t('Retry')}
        </button>
      )}
    </div>
  )
}

export function Data<T>({
  state,
  children,
}: {
  state: { data?: T; error?: unknown; reload?: () => void }
  children: (data: T) => ReactNode
}) {
  if (state.error && state.data === undefined)
    return <ErrorMessage error={state.error} retry={state.reload} />
  if (state.data === undefined) return <Loading />
  return (
    <>
      <ErrorMessage error={state.error} retry={state.reload} />
      {children(state.data)}
    </>
  )
}

export function useAction() {
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  async function run(action: () => Promise<unknown>, event?: FormEvent) {
    event?.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await action()
    } catch (cause) {
      setError(cause)
    } finally {
      setBusy(false)
    }
  }
  return { error, busy, run }
}

export function PageHeading({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="page-heading">
      <h1>{title}</h1>
      {children}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>
}

export function ForwardLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link className="button primary" to={to}>
      {children}
      <ArrowRight size={17} aria-hidden />
    </Link>
  )
}

export function ProgressBar({ value }: { value: number }) {
  const { t } = useTranslation()
  return (
    <div className="progress-line">
      <progress value={value} max={100} aria-label={t('Course progress')} />
      <b>{value}%</b>
    </div>
  )
}
