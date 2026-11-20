import { useEffect, useState } from 'react'
import {
  BookOpen,
  Braces,
  ChevronDown,
  CodeXml,
  Flame,
  Globe,
  Menu,
  Monitor,
  Trophy,
  UserRound,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'

import { sendEducation, useLive, useLoad, useSession } from '../application/state'
import type { Profile } from '../domain/models'
import { api, session } from '../infrastructure/api'
import { ErrorMessage, Loading, useAction } from './ui'

type Theme = 'system' | 'light' | 'dark'

export function Layout() {
  const { t, i18n } = useTranslation()
  const { user, reload } = useSession()
  const action = useAction()
  const location = useLocation()
  const [menu, setMenu] = useState(false)
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('cf.theme')
    return saved === 'dark' || saved === 'light' ? saved : 'system'
  })
  const [notice, setNotice] = useState('')
  const profile = useLoad<Profile>(user?.id ?? '', () => api('/edu/me/profile'), !!user)
  const online = useLive(
    user ? '/ws/edu' : null,
    (event) => {
      sendEducation(event)
      if (event.type === 'identity.updated') reload()
      if (event.type === 'achievement.unlocked') setNotice(event.title)
      if (event.type === 'level.up') setNotice(`${t('Level')} ${event.level}`)
      if (event.type === 'contest.reward') setNotice(`+${event.xp} XP`)
      if (event.type !== 'submission.result' || !event.practice) profile.reload()
    },
    () => {
      sendEducation()
      profile.reload()
    },
  )

  useEffect(() => {
    const pref = window.matchMedia('(prefers-color-scheme: dark)')
    function apply() {
      document.documentElement.dataset.theme =
        theme === 'system' ? (pref.matches ? 'dark' : 'light') : theme
    }
    apply()
    localStorage.setItem('cf.theme', theme)
    pref.addEventListener('change', apply)
    return () => pref.removeEventListener('change', apply)
  }, [theme])
  useEffect(() => {
    setMenu(false)
  }, [location.pathname])
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 5000)
    return () => window.clearTimeout(timer)
  }, [notice])

  return (
    <>
      <a className="skip" href="#main">
        {t('Skip to content')}
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Link to="/" className="brand">
            <span>
              <Braces size={20} aria-hidden />
            </span>
            CodeForge
          </Link>
          <button
            type="button"
            className="icon-button mobile-menu"
            onClick={() => setMenu(!menu)}
            aria-expanded={menu}
            aria-controls="navigation"
            aria-label={t('Main navigation')}
          >
            <Menu size={22} />
          </button>
          <nav
            id="navigation"
            className={menu ? 'navigation expanded' : 'navigation'}
            aria-label={t('Main navigation')}
          >
            <NavLink to="/" end>
              <BookOpen size={17} aria-hidden />
              {t('Catalog')}
            </NavLink>
            <NavLink to="/leaderboard">
              <Trophy size={17} aria-hidden />
              {t('Leaderboard')}
            </NavLink>
            {user && (
              <NavLink to="/contests">
                <CodeXml size={17} aria-hidden />
                {t('My contests')}
              </NavLink>
            )}
            {user && user.role !== 'student' && <NavLink to="/teach">{t('Teaching')}</NavLink>}
          </nav>
          <div className="header-actions">
            <label className="select-icon">
              <Globe size={16} aria-hidden />
              <select
                aria-label={t('Language')}
                value={i18n.language}
                onChange={(e) => void i18n.changeLanguage(e.target.value)}
              >
                <option value="ru">RU</option>
                <option value="en">EN</option>
              </select>
            </label>
            <label className="select-icon theme-select">
              <Monitor size={17} aria-hidden />
              <select
                aria-label={t('Theme')}
                value={theme}
                onChange={(e) => setTheme(e.target.value as Theme)}
              >
                <option value="system">{t('System')}</option>
                <option value="light">{t('Light')}</option>
                <option value="dark">{t('Dark')}</option>
              </select>
            </label>
            {user ? (
              <>
                {profile.data && (
                  <Link
                    className="streak"
                    to="/profile"
                    title={t('Current streak')}
                    aria-label={`${t('Current streak')}: ${profile.data.streak}`}
                  >
                    <Flame size={17} aria-hidden />
                    {profile.data.streak}
                  </Link>
                )}
                <details className="account">
                  <summary>
                    <UserRound size={17} aria-hidden />
                    <span>{user.name}</span>
                    <ChevronDown size={13} aria-hidden />
                  </summary>
                  <div className="account-menu">
                    <Link to="/profile">
                      {t('Profile')}
                      {profile.data && ` · ${t('Level')} ${profile.data.level}`}
                    </Link>
                    <button
                      type="button"
                      disabled={action.busy}
                      onClick={() => void action.run(session.logout)}
                    >
                      {t('Sign out')}
                    </button>
                  </div>
                </details>
              </>
            ) : (
              <Link className="button header-login" to="/login">
                {t('Sign in')}
              </Link>
            )}
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="shell">
        <ErrorMessage error={action.error} />
        <Outlet />
      </main>
      <footer className="site-footer">
        <span className="brand">
          <Braces size={18} aria-hidden />
          CodeForge
        </span>
        <Link to="/leaderboard">{t('Leaderboard')}</Link>
      </footer>
      <aside className="live-notice" aria-live="polite">
        {notice && <span>{notice}</span>}
        {!online && user && <span>{t('Connection lost. Reconnecting…')}</span>}
      </aside>
    </>
  )
}

export function RequireUser({ teaching = false }: { teaching?: boolean }) {
  const { t } = useTranslation()
  const { user, ready, error, reload } = useSession()
  const location = useLocation()
  if (!ready) return <Loading />
  if (error) return <ErrorMessage error={error} retry={reload} />
  if (!user)
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (teaching && user.role === 'student')
    return <p className="notice error">{t('errors.forbidden')}</p>
  return <Outlet />
}
