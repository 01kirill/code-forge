import { useState, type FormEvent } from 'react'
import { ArrowRight, CircleCheck, Eye, EyeOff, Flame, Target, Trophy } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useEducation, useLoad, useSession } from '../application/state'
import type { Profile } from '../domain/models'
import { api, ApiError, session } from '../infrastructure/api'
import { AttemptHistory } from './practice'
import { Data, Empty, ErrorMessage, PageHeading, ProgressBar, useAction } from './ui'

function safeReturn(value: unknown) {
  return typeof value === 'string' && value.startsWith('/') && !/^\/[\\/]/.test(value) ? value : '/'
}

export function Credentials({ register }: { register: boolean }) {
  const { t } = useTranslation()
  const { user } = useSession()
  const action = useAction()
  const [show, setShow] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const from = safeReturn(location.state?.from)
  if (user && !register) return <Navigate to={from} replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    const fields = new FormData(event.currentTarget)
    const email = String(fields.get('email'))
    const password = String(fields.get('password'))
    await action.run(async () => {
      if (register) {
        await api('/auth/register', {
          method: 'POST',
          retry: false,
          body: { email, password, name: fields.get('name') },
        })
        navigate('/login', { replace: true, state: { from, registered: true } })
      } else {
        await session.login(email, password)
        navigate(from, { replace: true })
      }
    }, event)
  }

  const errorCode = action.error instanceof ApiError ? action.error.body.code : ''
  const invalid = (field: string) =>
    errorCode === `duplicate_${field}` ||
    (action.error instanceof ApiError &&
      action.error.body.errors?.some((entry) => entry.field === field))
  return (
    <section className="auth-page">
      <PageHeading title={t(register ? 'Create account' : 'Sign in')} />
      {location.state?.registered && (
        <p role="status" className="notice">
          {t('Account created. You can sign in.')}
        </p>
      )}
      <form className="panel stack" onSubmit={(e) => void submit(e)}>
        <label>
          {t('Email')}
          <input
            name="email"
            required
            type="email"
            autoComplete="email"
            aria-invalid={invalid('email') || undefined}
            aria-describedby={invalid('email') ? 'auth-error' : undefined}
          />
        </label>
        {register && (
          <label>
            {t('Username')}
            <input
              name="name"
              required
              autoComplete="username"
              minLength={3}
              maxLength={32}
              pattern="[A-Za-z0-9_]{3,32}"
              aria-invalid={invalid('name') || undefined}
              aria-describedby={invalid('name') ? 'name-help auth-error' : 'name-help'}
            />
            <small id="name-help">{t('Use 3–32 Latin letters, digits or underscores.')}</small>
          </label>
        )}
        <label>
          {t('Password')}
          <span className="password-field">
            <input
              name="password"
              required
              type={show ? 'text' : 'password'}
              autoComplete={register ? 'new-password' : 'current-password'}
              minLength={register ? 8 : undefined}
              maxLength={72}
              aria-describedby={register ? 'password-help' : undefined}
            />
            <button
              type="button"
              className="icon-button"
              aria-label={t(show ? 'Hide password' : 'Show password')}
              onClick={() => setShow(!show)}
            >
              {show ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </span>
          {register && <small id="password-help">{t('Use 8–72 characters.')}</small>}
        </label>
        <div id="auth-error">
          <ErrorMessage error={action.error} />
        </div>
        <button className="button primary" disabled={action.busy}>
          {t(register ? 'Create account' : 'Sign in')}
          <ArrowRight size={18} aria-hidden />
        </button>
        <Link to={register ? '/login' : '/register'} state={{ from }}>
          {t(register ? 'Sign in' : 'Sign up')}
        </Link>
      </form>
    </section>
  )
}

type Topic = { slug: string; title: string; topics: { title: string; percent: number | null }[] }

export function ProfilePage() {
  const { t, i18n } = useTranslation()
  const auth = useSession()
  const user = auth.user!
  const profile = useLoad<Profile>(user.id, () => api('/edu/me/profile'))
  const topics = useLoad<Topic[]>(user.id, () => api('/edu/me/progress'))
  const action = useAction()
  const [saved, setSaved] = useState(false)
  useEducation(() => {
    profile.reload()
    topics.reload()
  })
  return (
    <>
      <PageHeading title={t('Profile')} />
      <Data state={profile}>
        {(value) => (
          <div className="metric-grid">
            <article>
              <Trophy aria-hidden />
              <strong>
                {t('Level')} {value.level}
              </strong>
              <span>
                {value.xp} XP · {value.next_level_xp} {t('XP to next level')}
              </span>
            </article>
            <article>
              <Flame aria-hidden />
              <strong>
                {value.streak} {t('days')}
              </strong>
              <span>
                {t('Best streak')}: {value.best_streak}
              </span>
            </article>
            <article>
              <Target aria-hidden />
              <strong>{value.solved}</strong>
              <span>{t('Tasks solved')}</span>
            </article>
          </div>
        )}
      </Data>
      <div className="profile-grid">
        <form
          className="stack panel"
          onSubmit={(e) => {
            const fields = new FormData(e.currentTarget)
            setSaved(false)
            void action.run(async () => {
              await api('/auth/me', { method: 'PATCH', body: Object.fromEntries(fields) })
              auth.reload()
              setSaved(true)
            }, e)
          }}
        >
          <label>
            {t('Username')}
            <input
              name="name"
              defaultValue={user.name}
              minLength={3}
              maxLength={32}
              pattern="[A-Za-z0-9_]{3,32}"
              required
            />
          </label>
          <label>
            {t('Time zone')}
            <input
              name="timezone"
              defaultValue={user.timezone}
              placeholder="Europe/Minsk"
              required
            />
          </label>
          <ErrorMessage error={action.error} />
          <button className="button primary" disabled={action.busy}>
            {t('Save')}
          </button>
          {saved && <span role="status">{t('Saved')}</span>}
        </form>
        <section className="panel stack">
          <h2>{t('Course progress')}</h2>
          <Data state={topics}>
            {(items) =>
              items.length ? (
                items.map((course) => (
                  <div key={course.slug} className="stack compact">
                    <Link to={`/courses/${course.slug}`}>
                      <strong>{course.title}</strong>
                    </Link>
                    {course.topics.map((topic) => (
                      <div key={topic.title}>
                        <p>{topic.title}</p>
                        {topic.percent === null ? (
                          <small>{t('No lessons yet')}</small>
                        ) : (
                          <ProgressBar value={topic.percent} />
                        )}
                      </div>
                    ))}
                  </div>
                ))
              ) : (
                <Empty>{t('No enrollments yet.')}</Empty>
              )
            }
          </Data>
        </section>
      </div>
      <section className="page-section">
        <h2>{t('Achievements')}</h2>
        <Data state={profile}>
          {(value) => (
            <ul className="achievement-grid">
              {value.achievements.map((item) => (
                <li key={item.id} className="panel">
                  {item.at ? <CircleCheck aria-hidden /> : <Trophy aria-hidden />}
                  <strong>
                    {i18n.language === 'ru' ? item.title : t(`achievement.${item.id}`)}
                  </strong>
                  <small>
                    {item.at
                      ? new Date(item.at).toLocaleDateString(i18n.language, {
                          timeZone: user.timezone,
                        })
                      : t('Not yet earned')}
                  </small>
                </li>
              ))}
            </ul>
          )}
        </Data>
      </section>
      <AttemptHistory base="/edu" query="/edu/me/submissions" />
    </>
  )
}
