import { useState } from 'react'
import { ArrowRight, BookOpen, Braces, CodeXml, ListChecks, Terminal } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { useLoad, useSession } from '../application/state'
import {
  languageNames,
  languages,
  typeNames,
  type Course,
  type CourseCard,
  type Language,
} from '../domain/models'
import { api } from '../infrastructure/api'
import { Data, Empty, ErrorMessage, ForwardLink, PageHeading, ProgressBar, useAction } from './ui'

const lessonIcons = { theory: BookOpen, quiz: ListChecks, practice: CodeXml }

export function Catalog() {
  const { t } = useTranslation()
  const [query, setQuery] = useSearchParams()
  const { user } = useSession()
  const current = query.get('language')
  const language = languages.find((value) => value === current) ?? ''
  const courses = useLoad<CourseCard[]>(`${language}:${user?.id ?? ''}`, () =>
    api(`/edu/courses${language ? `?language=${language}` : ''}`),
  )

  return (
    <>
      <section className="catalog-hero">
        <div className="hero-copy">
          <h1>
            {t('Learn to code.')}
            <br />
            <span>{t('Solve real tasks.')}</span>
          </h1>
          <p>{t('Read short lessons, test your knowledge and get feedback on every solution.')}</p>
          <a className="button primary" href="#courses">
            {t('Browse courses')}
            <ArrowRight size={18} aria-hidden />
          </a>
        </div>
        <div className="hero-code" aria-hidden="true">
          <div className="code-tab">
            <Terminal size={16} />
            Python
          </div>
          <div className="code-grid">
            <span className="line-numbers">
              1<br />2<br />3<br />4<br />5
            </span>
            <pre>
              <code>
                <span className="code-keyword">def</span> <span className="code-fn">add</span>
                {'(a, b):\n    '}
                <span className="code-keyword">return</span>
                {' a + b\n\n'}
                <span className="code-fn">print</span>
                {'(add('}
                <span className="code-number">2</span>
                {', '}
                <span className="code-number">3</span>
                {'))\n'}
                <span className="code-comment"># 5</span>
              </code>
            </pre>
          </div>
        </div>
      </section>
      <section id="courses" className="catalog-section">
        <div className="section-heading">
          <h2>{t('Course catalog')}</h2>
          <label>
            {t('Programming language')}
            <select
              value={language}
              onChange={(e) => setQuery(e.target.value ? { language: e.target.value } : {}, { replace: true })}
            >
              <option value="">{t('All languages')}</option>
              {languages.map((value) => (
                <option key={value} value={value}>{languageNames[value]}</option>
              ))}
            </select>
          </label>
        </div>
        <Data state={courses}>
          {(items) =>
            items.length ? (
              <div className="course-grid">
                {items.map((course) => (
                  <article className="course-card" key={course.slug}>
                    <div className="card-top">
                      <span className="tile-icon">
                        {course.language === 'python' ? (
                          <Terminal aria-hidden />
                        ) : (
                          <Braces aria-hidden />
                        )}
                      </span>
                      <span className="chip">{languageNames[course.language] ?? course.language}</span>
                    </div>
                    <h3>
                      <Link to={`/courses/${course.slug}`}>{course.title}</Link>
                    </h3>
                    <p>{course.description}</p>
                    {course.enrolled && !!course.lesson_count && (
                      <ProgressBar
                        value={Math.round((100 * course.completed_count) / course.lesson_count)}
                      />
                    )}
                    <div className="card-bottom">
                      <span>
                        <BookOpen size={16} aria-hidden />
                        {course.lesson_count} · {t('Lessons')}
                      </span>
                      <Link
                        aria-label={`${t('Open course')}: ${course.title}`}
                        to={`/courses/${course.slug}`}
                      >
                        {t('Open course')}
                        <ArrowRight size={17} aria-hidden />
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <Empty>
                <p>{t('No courses match this filter.')}</p>
                {language && (
                  <button type="button" onClick={() => setQuery({})}>
                    {t('Reset filter')}
                  </button>
                )}
              </Empty>
            )
          }
        </Data>
      </section>
    </>
  )
}

export function CoursePage() {
  const { slug = '' } = useParams()
  const { t } = useTranslation()
  const { user } = useSession()
  const action = useAction()
  const state = useLoad<Course>(`${slug}:${user?.id ?? ''}`, () => api(`/edu/courses/${slug}`))
  return (
    <Data state={state}>
      {(course) => (
        <>
          <Link className="back-link" to="/">
            {t('Catalog')}
          </Link>
          <PageHeading title={course.title}>
            <span className="chip">{languageNames[course.language] ?? course.language}</span>
          </PageHeading>
          <p className="lead">{course.description}</p>
          <div className="row course-actions">
            {course.enrolled ? (
              <span className="status positive">{t('Enrolled')}</span>
            ) : user ? (
              <button
                className="button primary"
                type="button"
                disabled={action.busy}
                onClick={() =>
                  void action.run(async () => {
                    await api(`/edu/courses/${slug}/enroll`, { method: 'POST' })
                    state.reload()
                  })
                }
              >
                {t('Enroll')}
                <ArrowRight size={17} aria-hidden />
              </button>
            ) : (
              <Link className="button primary" to="/login" state={{ from: `/courses/${slug}` }}>
                {t('Start learning')}
              </Link>
            )}
            <ErrorMessage error={action.error} />
          </div>
          <div className="lesson-list">
            {course.modules.map((module, index) => (
              <section key={index} className="module">
                <h2>{module.title}</h2>
                {module.lessons.map((lesson) => {
                  const Icon = lessonIcons[lesson.type]
                  return (
                    <Link className="lesson-link" key={lesson.id} to={`/lessons/${lesson.id}`}>
                      <Icon size={20} aria-hidden />
                      <strong>{lesson.title}</strong>
                      <small>
                        {t(typeNames[lesson.type])} · {lesson.topic}
                      </small>
                      {course.completed?.includes(lesson.id) && (
                        <span className="status positive">{t('Completed')}</span>
                      )}
                      <ArrowRight className="end" size={17} aria-hidden />
                    </Link>
                  )
                })}
                {!module.lessons.length && <p className="muted">{t('No lessons yet')}</p>}
              </section>
            ))}
          </div>
        </>
      )}
    </Data>
  )
}

export function Leaderboard() {
  const { t } = useTranslation()
  const [offset, setOffset] = useState(0)
  const rows = useLoad<{ id: string; name: string; xp: number; rank: number }[]>(
    String(offset),
    () => api(`/edu/leaderboard?offset=${offset}`),
  )
  return (
    <>
      <PageHeading title={t('Overall leaderboard')} />
      <Data state={rows}>
        {(items) => (
          <>
            {items.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t('Place')}</th>
                      <th>{t('Participant')}</th>
                      <th>XP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr key={row.id}>
                        <td>{row.rank}</td>
                        <td>
                          <Link to={`/users/${row.id}`}>{row.name}</Link>
                        </td>
                        <td>{row.xp}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>{t('No ranked users yet.')}</Empty>
            )}
            {(offset > 0 || items.length === 50) && (
              <div className="row pagination">
                <button disabled={!offset} onClick={() => setOffset(offset - 50)}>
                  {t('Previous page')}
                </button>
                <button disabled={items.length < 50} onClick={() => setOffset(offset + 50)}>
                  {t('Next page')}
                </button>
              </div>
            )}
          </>
        )}
      </Data>
    </>
  )
}

export function PublicProfile() {
  const { id = '' } = useParams()
  const { t } = useTranslation()
  const state = useLoad<{ name: string }>(id, () => api(`/auth/users/${id}`))
  return (
    <Data state={state}>
      {(data) => (
        <>
          <PageHeading title={data.name} />
          <ForwardLink to="/leaderboard">{t('Leaderboard')}</ForwardLink>
        </>
      )}
    </Data>
  )
}

export function LanguageSelect({
  value,
  onChange,
  options = languages,
}: {
  value: Language
  onChange: (value: Language) => void
  options?: Language[]
}) {
  const { t } = useTranslation()
  return (
    <label>
      {t('Programming language')}
      <select required value={options.includes(value) ? value : ''} onChange={(e) => onChange(e.target.value as Language)}>
        {!options.includes(value) && <option value="" disabled>{t('Choose a supported language')}</option>}
        {options.map((item) => (
          <option key={item} value={item}>
            {languageNames[item]}
          </option>
        ))}
      </select>
    </label>
  )
}
