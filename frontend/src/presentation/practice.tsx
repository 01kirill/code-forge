import { lazy, Suspense, useEffect, useState } from 'react'
import { CircleCheck, CircleX, Clock3, Play, Send } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import Markdown from 'react-markdown'
import hljs from 'highlight.js/lib/core'
import cpp from 'highlight.js/lib/languages/cpp'
import python from 'highlight.js/lib/languages/python'

import { useEducation, useLoad, useSession } from '../application/state'
import {
  languageNames,
  verdictLabels,
  type Attempt,
  type Language,
  type LiveEvent,
  type Result,
  type Task,
} from '../domain/models'
import { api } from '../infrastructure/api'
import { LanguageSelect } from './catalog'
import { Data, Empty, ErrorMessage, Loading, PageHeading, useAction } from './ui'

const Monaco = lazy(() => import('./monaco'))
hljs.registerLanguage('python', python)
hljs.registerLanguage('cpp', cpp)

function Highlighted({ code, language }: { code: string; language: Language }) {
  const highlighted = hljs.highlight(code, { language }).value
  return (
    <pre className="output">
      <code dangerouslySetInnerHTML={{ __html: highlighted }} />
    </pre>
  )
}

export function VerdictText({ attempt }: { attempt: Attempt }) {
  const { t } = useTranslation()
  const result = attempt.result
  if (!result)
    return (
      <span className="status">
        <Clock3 size={14} aria-hidden />
        {t('Queued')}
      </span>
    )
  const Icon = result.verdict === 'AC' ? CircleCheck : CircleX
  return (
    <span className={`status ${result.verdict === 'AC' ? 'positive' : 'negative'}`}>
      <Icon size={15} aria-hidden />
      {result.verdict !== 'TECHNICAL' && `${result.verdict} · `}
      {t(verdictLabels[result.verdict])}
    </span>
  )
}

export function ResultPanel({ attempt, run = false }: { attempt: Attempt; run?: boolean }) {
  const { t, i18n } = useTranslation()
  const result = attempt.result
  return (
    <section className="result-panel">
      <h3>{t(run ? 'Run result' : 'Result')}</h3>
      <div role="status" aria-live="polite">
        <VerdictText attempt={attempt} />
      </div>
      {result && result.verdict !== 'TECHNICAL' && (
        <>
          <p className="result-metrics">
            {t('Passed tests')}: {result.passed}/{result.total}
            {result.first_failed !== null && ` · ${t('Failed test')}: ${result.first_failed}`}
            {result.time_ms !== null && ` · ${result.time_ms} ${t('ms')}`}
            {result.memory_kb !== null && ` · ${result.memory_kb} ${t('KiB')}`}
          </p>
          {result.details
            .filter((detail) => run || detail.verdict !== 'AC')
            .map((detail) => (
              <details key={detail.number} open={run || detail.number === result.first_failed}>
                <summary>
                  #{detail.number} · {t(verdictLabels[detail.verdict])}
                </summary>
                {detail.stdin !== undefined && (
                  <CodeOutput label={t('Input')} value={detail.stdin} />
                )}
                {detail.expected != null && (
                  <CodeOutput label={t('Expected output')} value={detail.expected} />
                )}
                {detail.stdout !== undefined && (
                  <CodeOutput label={t('Output')} value={detail.stdout} />
                )}
                {detail.diagnostic && (
                  <CodeOutput label={t('Diagnostics')} value={detail.diagnostic} />
                )}
                {detail.hint && (
                  <p>
                    {i18n.language === 'ru' ? detail.hint : t('Review your code and try again.')}
                  </p>
                )}
              </details>
            ))}
        </>
      )}
    </section>
  )
}

function CodeOutput({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <strong>{label}</strong>
      <pre className="output">{value || '—'}</pre>
    </div>
  )
}

export function AttemptHistory({
  base,
  query,
  revision = 0,
  contest = false,
}: {
  base: string
  query: string
  revision?: number
  contest?: boolean
}) {
  const { t, i18n } = useTranslation()
  const { user } = useSession()
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState('')
  const state = useLoad<Attempt[]>(`${query}:${offset}`, () => api(`${query}?offset=${offset}`))
  const attempt = useLoad<Attempt>(
    selected,
    () => api(`${base}/submissions/${selected}`),
    !!selected,
  )
  useEducation((event) => {
    if (!contest && (!event || (event.type === 'submission.result' && !event.practice))) {
      state.reload()
      if (selected && (!event || event.id === selected)) attempt.reload()
    }
  })
  useEffect(() => {
    state.reload()
    if (selected) attempt.reload()
  }, [revision, query])
  return (
    <section className="page-section" aria-labelledby={`history-${contest ? 'contest' : 'edu'}`}>
      <h2 id={`history-${contest ? 'contest' : 'edu'}`}>{t('Attempt history')}</h2>
      <Data state={state}>
        {(items) => (
          <>
            {items.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t('Date')}</th>
                      <th>{t('Task')}</th>
                      <th>{t('Programming language')}</th>
                      <th>{t('Result')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <button
                            type="button"
                            className="text-button"
                            onClick={() => setSelected(item.id)}
                          >
                            {new Date(item.submitted_at).toLocaleString(i18n.language, {
                              timeZone: user?.timezone,
                            })}
                          </button>
                        </td>
                        <td>{item.task_title ?? item.label}</td>
                        <td>{languageNames[item.language]}</td>
                        <td>
                          <VerdictText attempt={item} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>{t('No submissions yet.')}</Empty>
            )}
            {(offset > 0 || items.length === 30) && (
              <div className="row pagination">
                <button disabled={!offset} onClick={() => setOffset(offset - 30)}>
                  {t('Previous page')}
                </button>
                <button disabled={items.length < 30} onClick={() => setOffset(offset + 30)}>
                  {t('Next page')}
                </button>
              </div>
            )}
          </>
        )}
      </Data>
      {selected && (
        <div className="panel stack">
          <div className="row spread">
            <h3>{t('Source code')}</h3>
            <button onClick={() => setSelected('')}>{t('Close')}</button>
          </div>
          <Data state={attempt}>
            {(item) => (
              <>
                <Highlighted code={item.code ?? ''} language={item.language} />
                <ResultPanel attempt={item} />
                {!contest && <Link to={`/attempts/${item.id}`}>{t('Open attempt')}</Link>}
              </>
            )}
          </Data>
        </div>
      )}
    </section>
  )
}

export function AttemptPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const state = useLoad<Attempt>(id, () => api(`/edu/submissions/${id}`))
  useEducation((event) => {
    if (!event || (event.type === 'submission.result' && event.id === id)) state.reload()
  })
  return (
    <Data state={state}>
      {(item) => (
        <>
          <PageHeading title={item.task_title ?? t('Source code')} />
          <Highlighted code={item.code ?? ''} language={item.language} />
          <ResultPanel attempt={item} />
          <Link to="/profile">{t('Attempt history')}</Link>
        </>
      )}
    </Data>
  )
}

export function Practice({
  task,
  draftKey,
  base,
  submitUrl,
  lessonId,
  canSubmit = true,
  live,
  onSubmit,
  preferredLanguage,
}: {
  task: Task
  draftKey: string
  base: string
  submitUrl: string
  lessonId?: string
  canSubmit?: boolean
  live?: LiveEvent
  onSubmit: () => void
  preferredLanguage?: Language
}) {
  const { t } = useTranslation()
  const languages = (['python', 'cpp'] as const).filter((language) => language in task.templates)
  const [language, setLanguage] = useState<Language>(() =>
    preferredLanguage && languages.includes(preferredLanguage) ? preferredLanguage : languages[0],
  )
  const [drafts, setDrafts] = useState<Partial<Record<Language, string>>>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(draftKey) ?? '{}')
    } catch {
      return {}
    }
  })
  const [narrow, setNarrow] = useState(
    () => matchMedia('(max-width: 639px), (pointer: coarse)').matches,
  )
  const [custom, setCustom] = useState(false)
  const [input, setInput] = useState('')
  const [attempt, setAttempt] = useState<Attempt>()
  const [isRun, setIsRun] = useState(false)
  const action = useAction()
  const code = drafts[language] ?? task.templates[language] ?? ''

  useEffect(() => {
    const media = matchMedia('(max-width: 639px), (pointer: coarse)')
    const update = () => setNarrow(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    sessionStorage.setItem(draftKey, JSON.stringify(drafts))
  }, [draftKey, drafts])

  function result(id: string, outcome: Result) {
    setAttempt((previous) =>
      previous && previous.id === id && !previous.result
        ? { ...previous, result: outcome, state: 'done' }
        : previous,
    )
  }
  useEducation((event) => {
    if (lessonId && event?.type === 'submission.result') result(event.id, event.result)
  })
  useEffect(() => {
    if (live?.type === 'submission.result') result(live.id, live.result)
  }, [live])
  useEffect(() => {
    if (!attempt || attempt.state !== 'queued') return
    const id = attempt.id
    let disposed = false
    const timer = window.setInterval(async () => {
      try {
        const saved = await api<Attempt>(`${base}/submissions/${id}`)
        if (!disposed && saved.result) result(id, saved.result)
      } catch {
        // The durable attempt can also be reopened from history.
      }
    }, 1500)
    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [attempt, base])
  useEffect(() => {
    const saved = sessionStorage.getItem(`${draftKey}.attempt`)
    let alive = true
    if (saved)
      void api<Attempt>(`${base}/submissions/${saved}`).then(
        (value) => {
          if (alive) setAttempt((current) => current ?? value)
        },
        () => {},
      )
    return () => {
      alive = false
    }
  }, [base, draftKey])

  function send(run: boolean) {
    void action.run(async () => {
      const url = run ? `/edu/tasks/${task.task_id}/run` : submitUrl
      const saved = await api<Attempt>(url, {
        method: 'POST',
        body: {
          language,
          code,
          ...(lessonId && { lesson_id: lessonId }),
          ...(run && { stdin: custom ? input : null }),
        },
      })
      setIsRun(run)
      setAttempt(saved)
      if (!run) {
        sessionStorage.setItem(`${draftKey}.attempt`, saved.id)
        onSubmit()
      }
    })
  }
  const edit = (value: string) => setDrafts((current) => ({ ...current, [language]: value }))
  return (
    <div className="workspace">
      <section className="statement panel">
        <h2>{t('Statement')}</h2>
        <div className="markdown">
          <Markdown>{task.statement}</Markdown>
        </div>
        <p className="muted">
          {t('Limits')}: {task.time_ms} {t('ms')} · {task.memory_kb} {t('KiB')}
        </p>
        <h3>{t('Examples')}</h3>
        {task.examples.map((example, index) => (
          <div className="example" key={index}>
            <CodeOutput label={t('Input')} value={example.stdin} />
            <CodeOutput label={t('Expected output')} value={example.expected} />
          </div>
        ))}
      </section>
      <section className="panel editor-panel">
        <div className="row spread">
          <h2>{t('Source code')}</h2>
          <LanguageSelect value={language} onChange={setLanguage} options={languages} />
        </div>
        {narrow ? (
          <>
            <textarea
              className="code-input"
              aria-label={t('Source code')}
              spellCheck={false}
              value={code}
              onChange={(e) => edit(e.target.value)}
            />
            <details>
              <summary>{t('Show highlighted preview')}</summary>
              <Highlighted code={code} language={language} />
            </details>
          </>
        ) : (
          <Suspense fallback={<Loading />}>
            <Monaco value={code} onChange={edit} language={language} label={t('Source code')} />
          </Suspense>
        )}
        {canSubmit && (
          <>
            {lessonId && (
              <>
                <p className="muted">
                  {t(
                    'Runs check examples or your custom input. Submissions count toward progress.',
                  )}
                </p>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={custom}
                    onChange={(e) => setCustom(e.target.checked)}
                  />
                  {t('Use custom input')}
                </label>
                {custom && (
                  <label>
                    {t('Input')}
                    <textarea value={input} onChange={(e) => setInput(e.target.value)} />
                  </label>
                )}
              </>
            )}
            <div className="row">
              {lessonId && (
                <button
                  className="button"
                  type="button"
                  disabled={action.busy || !code.trim()}
                  onClick={() => send(true)}
                >
                  <Play size={17} aria-hidden />
                  {t('Run')}
                </button>
              )}
              <button
                className="button primary"
                type="button"
                disabled={action.busy || !code.trim()}
                onClick={() => send(false)}
              >
                <Send size={17} aria-hidden />
                {t('Submit')}
              </button>
            </div>
          </>
        )}
        <ErrorMessage error={action.error} />
        {attempt && <ResultPanel attempt={attempt} run={isRun} />}
      </section>
    </div>
  )
}
