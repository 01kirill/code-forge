import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ArrowDown, ArrowUp, Clock3, Copy, Plus, Trophy, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'

import { useLive, useLoad, useSession } from '../application/state'
import {
  difficultyNames,
  languageNames,
  moveItem,
  roomStates,
  type LiveEvent,
  type Problem,
  type Room,
  type RoomDetail,
  type RoomDraft,
  type Standings,
  type TaskMetadata,
} from '../domain/models'
import { api } from '../infrastructure/api'
import { AttemptHistory, Practice } from './practice'
import { Data, Empty, ErrorMessage, ForwardLink, Loading, PageHeading, useAction } from './ui'

export function ContestList() {
  const { t } = useTranslation()
  const rooms = useLoad<Room[]>('rooms', () => api('/contest/contests'))
  const { user } = useSession()
  return (
    <>
      <PageHeading title={t('My contests')}>
        <ForwardLink to="/contests/new">{t('New contest')}</ForwardLink>
      </PageHeading>
      <Data state={rooms}>
        {(items) =>
          items.length ? (
            <div className="course-grid">
              {items.map((room) => (
                <article className="course-card" key={room.id}>
                  <div className="card-top">
                    <span className="tile-icon">
                      <Trophy aria-hidden />
                    </span>
                    <span className="chip">{t(roomStates[room.state])}</span>
                  </div>
                  <h3>
                    <Link to={`/contests/${room.id}`}>{room.title}</Link>
                  </h3>
                  <p>{room.description}</p>
                  <div className="card-bottom">
                    <span>
                      {room.duration} {t('minutes')}
                    </span>
                    <span>{t(room.owner_id === user?.id ? 'Owner' : 'Participant')}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty>{t('No contests yet. Create one or open an invitation.')}</Empty>
          )
        }
      </Data>
    </>
  )
}

function RoomFields({
  value,
  onChange,
}: {
  value: RoomDraft
  onChange: (value: RoomDraft) => void
}) {
  const { t } = useTranslation()
  return (
    <>
      <label>
        {t('Title')}
        <input
          required
          maxLength={120}
          value={value.title}
          onChange={(e) => onChange({ ...value, title: e.target.value })}
        />
      </label>
      <label>
        {t('Description')}
        <textarea
          maxLength={4000}
          value={value.description}
          onChange={(e) => onChange({ ...value, description: e.target.value })}
        />
      </label>
      <label>
        {t('Duration (minutes)')}
        <input
          type="number"
          min={5}
          max={600}
          required
          value={value.duration}
          onChange={(e) => onChange({ ...value, duration: Number(e.target.value) })}
        />
      </label>
    </>
  )
}

function TaskPicker({
  ids,
  onChange,
  known = [],
}: {
  ids: string[]
  onChange: (ids: string[]) => void
  known?: { task_id: string; title: string }[]
}) {
  const { t } = useTranslation()
  const tasks = useLoad<TaskMetadata[]>('bank', () => api('/edu/contest-tasks'))
  const [choice, setChoice] = useState('')
  return (
    <fieldset className="stack compact picker">
      <legend>{t('Contest tasks')}</legend>
      <Data state={tasks}>
        {(items) => (
          <label>
            {t('Add task')}
            <select
              value={choice}
              onChange={(e) => {
                const id = e.target.value
                if (id) onChange([...ids, id])
                setChoice('')
              }}
            >
              <option value="">{t('Select task')}</option>
              {items
                .filter((item) => !ids.includes(item.task_id))
                .map((task) => (
                  <option key={task.task_id} value={task.task_id} disabled={ids.length >= 26}>
                    {task.title} · {t(difficultyNames[task.difficulty])} ·{' '}
                    {task.languages.map((language) => languageNames[language]).join(', ')}
                  </option>
                ))}
            </select>
          </label>
        )}
      </Data>
      <ol className="ordered-items" type="A">
        {ids.map((id, index) => (
          <li key={id}>
            <span>
              {String.fromCharCode(65 + index)} ·{' '}
              {[...known, ...(tasks.data ?? [])].find((item) => item.task_id === id)?.title ?? id}
            </span>
            <button
              type="button"
              className="icon-button"
              disabled={index === 0}
              aria-label={t('Move up')}
              onClick={() => onChange(moveItem(ids, index, -1))}
            >
              <ArrowUp size={16} />
            </button>
            <button
              type="button"
              className="icon-button"
              disabled={index === ids.length - 1}
              aria-label={t('Move down')}
              onClick={() => onChange(moveItem(ids, index, 1))}
            >
              <ArrowDown size={16} />
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={t('Remove')}
              onClick={() => onChange(ids.filter((item) => item !== id))}
            >
              <X size={16} />
            </button>
          </li>
        ))}
      </ol>
    </fieldset>
  )
}

export function NewContest() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const action = useAction()
  const [draft, setDraft] = useState<RoomDraft>({ title: '', description: '', duration: 30 })
  const [ids, setIds] = useState<string[]>([])
  const [created, setCreated] = useState<string>()
  function submit(event: FormEvent) {
    void action.run(async () => {
      const id =
        created ?? (await api<Room>('/contest/contests', { method: 'POST', body: draft })).id
      setCreated(id)
      if (ids.length)
        await api(`/contest/contests/${id}/problems`, { method: 'PUT', body: { task_ids: ids } })
      navigate(`/contests/${id}`)
    }, event)
  }
  return (
    <>
      <Link className="back-link" to="/contests">
        {t('My contests')}
      </Link>
      <PageHeading title={t('New contest')} />
      <form className="stack panel form-width" onSubmit={submit}>
        <RoomFields value={draft} onChange={setDraft} />
        <TaskPicker ids={ids} onChange={setIds} />
        <ErrorMessage error={action.error} />
        <button className="button primary" disabled={action.busy}>
          <Plus size={18} aria-hidden />
          {t('New contest')}
        </button>
      </form>
    </>
  )
}

export function JoinContest() {
  const { token = '' } = useParams()
  const { t } = useTranslation()
  const state = useLoad<{ id: string }>(token, () =>
    api(`/contest/join/${encodeURIComponent(token)}`, { method: 'POST' }),
  )
  if (state.data) return <Navigate to={`/contests/${state.data.id}`} replace />
  return state.error ? (
    <div className="stack">
      <ErrorMessage error={state.error} />
      <Link to="/contests">{t('My contests')}</Link>
    </div>
  ) : (
    <Loading />
  )
}

export function ContestPage() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const { user } = useSession()
  const base = `/contest/contests/${id}`
  const room = useLoad(id, async () => {
    const start = Date.now()
    const data = await api<RoomDetail>(base)
    return { ...data, clockOffset: Date.parse(data.server_time) - (start + Date.now()) / 2 }
  })
  const standings = useLoad<Standings>(id, () => api(`${base}/standings`), !!room.data)
  const [event, setEvent] = useState<LiveEvent>()
  const [leader, setLeader] = useState<string>()
  const [attempts, setAttempts] = useState(0)
  const [tick, setTick] = useState(Date.now)
  const sync = () => {
    room.reload()
    standings.reload()
    setAttempts((n) => n + 1)
  }
  const online = useLive(
    room.data ? `/ws/contest/${id}` : null,
    (live) => {
      if (live.type === 'submission.result') {
        setEvent(live)
        setAttempts((n) => n + 1)
      }
      if (live.type === 'leader_changed') setLeader(live.name)
      if (live.type === 'standings' && live.version >= (standings.data?.version ?? 0)) {
        standings.set({
          version: live.version,
          rows: live.rows,
          pending: standings.data?.pending ?? 0,
          final: false,
        })
        standings.reload()
      }
      if (
        live.type === 'countdown' ||
        live.type === 'started' ||
        live.type === 'finished' ||
        live.type === 'room.updated'
      )
        sync()
    },
    sync,
  )
  useEffect(() => {
    const timer = window.setInterval(() => setTick(Date.now()), 500)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    if (!leader) return
    const timer = window.setTimeout(() => setLeader(undefined), 5000)
    return () => window.clearTimeout(timer)
  }, [leader])

  const at = tick + (room.data?.clockOffset ?? 0)
  const start = room.data?.start_at ? Date.parse(room.data.start_at) : null
  const end = room.data?.end_at ? Date.parse(room.data.end_at) : null
  const phase =
    start === null || end === null
      ? 'draft'
      : at < start
        ? 'countdown'
        : at < end
          ? 'running'
          : 'finished'
  const problems = useLoad<Problem[]>(
    id,
    () => api(`${base}/problems`),
    phase === 'running' || phase === 'finished',
  )
  const [label, setLabel] = useState('A')
  const active = problems.data?.find((item) => item.label === label) ?? problems.data?.[0]
  const countdown = phase === 'countdown' ? start : phase === 'running' ? end : null
  const remaining = countdown === null ? 0 : Math.max(0, Math.ceil((countdown - at) / 1000))
  useEffect(() => {
    if (room.data && phase !== room.data.state) sync()
  }, [phase, room.data?.state])
  useEffect(() => {
    if (online && !(phase === 'finished' && !standings.data?.final)) return
    const timer = window.setInterval(sync, 3000)
    return () => window.clearInterval(timer)
  }, [online, phase, id, standings.data?.final])

  return (
    <Data state={room}>
      {(value) => (
        <>
          <Link className="back-link" to="/contests">
            {t('My contests')}
          </Link>
          <PageHeading title={value.title}>
            <span className="chip">{t(roomStates[phase])}</span>
            {countdown !== null && (
              <span className="timer">
                <Clock3 size={20} aria-hidden />
                {String(Math.floor(remaining / 3600)).padStart(2, '0')}:
                {String(Math.floor(remaining / 60) % 60).padStart(2, '0')}:
                {String(remaining % 60).padStart(2, '0')}
              </span>
            )}
          </PageHeading>
          {value.description && <p className="lead">{value.description}</p>}
          <div role="status">
            {!online && <p className="notice">{t('Connection lost. Reconnecting…')}</p>}
            {leader && (
              <p className="notice positive">{t('{{name}} takes the lead!', { name: leader })}</p>
            )}
          </div>
          {phase === 'draft' || phase === 'countdown' ? (
            <>
              <div className="lobby-grid">
                <section className="panel stack">
                  <h2>{t('Participants')}</h2>
                  <ul>
                    {value.participants.map((person) => (
                      <li key={person.id}>
                        {person.name}
                        {person.id === value.owner_id && ` · ${t('Owner')}`}
                      </li>
                    ))}
                  </ul>
                  <p className="muted">{t('Problems unlock when the contest starts.')}</p>
                  <p>
                    {t(
                      'Prize XP go to places 1–3 with an accepted solution. Contest attempts do not count toward course progress.',
                    )}
                  </p>
                  {value.invite && (
                    <Invitation
                      base={base}
                      value={value.invite}
                      editable={phase === 'draft'}
                      reload={room.reload}
                    />
                  )}
                </section>
                {value.invite && phase === 'draft' && (
                  <RoomSettings key={id} base={base} room={value} reload={room.reload} />
                )}
              </div>
            </>
          ) : (
            <>
              <Data state={problems}>
                {(items) => (
                  <>
                    <div className="row task-tabs" aria-label={t('Contest tasks')}>
                      {items.map((problem) => (
                        <button
                          type="button"
                          key={problem.label}
                          aria-pressed={active?.label === problem.label}
                          onClick={() => setLabel(problem.label)}
                        >
                          {problem.label} · {problem.title}
                        </button>
                      ))}
                    </div>
                    {active && (
                      <Practice
                        key={`${id}:${active.label}`}
                        task={active}
                        draftKey={`cf.contest.${user?.id}.${id}.${active.label}`}
                        base={base}
                        canSubmit={phase === 'running'}
                        live={event}
                        submitUrl={`${base}/problems/${active.label}/submissions`}
                        onSubmit={() => {
                          setAttempts((n) => n + 1)
                          standings.reload()
                        }}
                      />
                    )}
                  </>
                )}
              </Data>
              <AttemptHistory
                base={base}
                query={`${base}/submissions`}
                revision={attempts}
                contest
              />
            </>
          )}
          <section className="page-section">
            <h2>{t('Standings')}</h2>
            <Data state={standings}>
              {(data) => (
                <>
                  {phase === 'finished' && !data.final && (
                    <p role="status" className="notice">
                      {t('Provisional standings')} · {t('Pending submissions')}: {data.pending}
                    </p>
                  )}
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>{t('Place')}</th>
                          <th>{t('Participant')}</th>
                          {value.problems.map((problem) => (
                            <th key={problem.label} title={problem.title}>
                              {problem.label}
                            </th>
                          ))}
                          <th>{t('Solved')}</th>
                          <th>{t('Penalty (min)')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.rows.map((person) => (
                          <tr key={person.id}>
                            <td>{person.place}</td>
                            <td>{person.name}</td>
                            {value.problems.map((problem) => {
                              const cell = person.cells[problem.label]
                              return (
                                <td key={problem.label}>
                                  {cell?.accepted
                                    ? `AC · ${cell.penalty}`
                                    : cell?.failures
                                      ? `−${cell.failures}`
                                      : '—'}
                                </td>
                              )
                            })}
                            <td>
                              <b>{person.solved}</b>
                            </td>
                            <td>{person.penalty}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </Data>
          </section>
        </>
      )}
    </Data>
  )
}

function Invitation({
  base,
  value,
  editable,
  reload,
}: {
  base: string
  value: string
  editable: boolean
  reload: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const [copied, setCopied] = useState(false)
  const link = `${location.origin}/join/${value}`
  return (
    <div className="stack compact">
      <label>
        {t('Invitation link')}
        <input type="url" readOnly value={link} onFocus={(e) => e.target.select()} />
      </label>
      <div className="row">
        <button
          type="button"
          onClick={() =>
            void action.run(async () => {
              await navigator.clipboard.writeText(link)
              setCopied(true)
            })
          }
        >
          <Copy size={16} aria-hidden />
          {t(copied ? 'Link copied' : 'Copy link')}
        </button>
        {editable && (
          <button
            type="button"
            disabled={action.busy}
            onClick={() =>
              void action.run(async () => {
                await api(`${base}/invite`, { method: 'POST' })
                setCopied(false)
                reload()
              })
            }
          >
            {t('Renew invitation')}
          </button>
        )}
      </div>
      <ErrorMessage error={action.error} />
    </div>
  )
}

function RoomSettings({
  base,
  room,
  reload,
}: {
  base: string
  room: RoomDetail
  reload: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const [draft, setDraft] = useState<RoomDraft>(room)
  const initial = useMemo(() => room.problems.map((item) => item.task_id), [room.problems])
  const [ids, setIds] = useState(initial)
  const changed = JSON.stringify(initial) !== JSON.stringify(ids)
  async function save() {
    await api(base, { method: 'PATCH', body: draft })
    if (changed) await api(`${base}/problems`, { method: 'PUT', body: { task_ids: ids } })
    reload()
  }
  return (
    <form className="panel stack" onSubmit={(e) => void action.run(save, e)}>
      <h2>{t('Edit')}</h2>
      <RoomFields value={draft} onChange={setDraft} />
      <TaskPicker ids={ids} onChange={setIds} known={room.problems} />
      <ErrorMessage error={action.error} />
      <div className="row">
        <button type="submit" disabled={action.busy}>
          {t('Save')}
        </button>
        <button
          type="button"
          className="button primary"
          disabled={
            action.busy ||
            !ids.length ||
            !draft.title.trim() ||
            draft.duration < 5 ||
            draft.duration > 600
          }
          onClick={() =>
            void action.run(async () => {
              await save()
              await api(`${base}/start`, { method: 'POST' })
              reload()
            })
          }
        >
          {t('Start contest')}
        </button>
      </div>
    </form>
  )
}
