import { useState, type FormEvent } from 'react'
import { ArrowDown, ArrowUp, Download, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Markdown from 'react-markdown'

import { useLoad, useSession } from '../application/state'
import {
  difficultyNames,
  languageNames,
  moveItem,
  typeNames,
  type AuthorQuestion,
  type Course,
  type CourseCard,
  type CourseFields,
  type Gradebook,
  type Identity,
  type LessonDraft,
  type Role,
  type TaskDraft,
  type TaskMetadata,
} from '../domain/models'
import { api, request } from '../infrastructure/api'
import { LanguageSelect } from './catalog'
import { Data, Empty, ErrorMessage, ForwardLink, PageHeading, useAction } from './ui'

export function Teaching() {
  const { t } = useTranslation()
  const { user } = useSession()
  const courses = useLoad<CourseCard[]>('courses', () => api('/edu/me/courses'))
  const tasks = useLoad<TaskMetadata[]>('tasks', () => api('/edu/tasks'))
  return (
    <>
      <PageHeading title={t('Teaching')} />
      <section>
        <div className="section-heading">
          <h2>{t('My courses')}</h2>
          <ForwardLink to="/teach/courses/new">{t('New course')}</ForwardLink>
        </div>
        <Data state={courses}>
          {(items) =>
            items.length ? (
              <ul className="records">
                {items.map((course) => (
                  <li key={course.slug}>
                    <strong>{course.title}</strong>
                    <span className="chip">{t(course.published ? 'Published' : 'Draft')}</span>
                    <div className="row">
                      <Link to={`/teach/courses/${course.slug}`}>{t('Edit')}</Link>
                      <Link to={`/teach/courses/${course.slug}/gradebook`}>{t('Gradebook')}</Link>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>{t('No courses yet.')}</Empty>
            )
          }
        </Data>
      </section>
      <section className="page-section">
        <div className="section-heading">
          <h2>{t('Task bank')}</h2>
          <ForwardLink to="/teach/tasks/new">{t('New task')}</ForwardLink>
        </div>
        <Data state={tasks}>
          {(items) =>
            items.length ? (
              <ul className="records">
                {items.map((task) => (
                  <li key={task.task_id}>
                    <strong>{task.title}</strong>
                    <span>
                      {t(difficultyNames[task.difficulty])} ·{' '}
                      {task.languages.map((language) => languageNames[language]).join(', ')}
                    </span>
                    <Link to={`/teach/tasks/${task.task_id}`}>{t('Edit')}</Link>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>{t('No tasks yet.')}</Empty>
            )
          }
        </Data>
      </section>
      {user?.role === 'admin' && <Access />}
    </>
  )
}

function Access() {
  const { t } = useTranslation()
  const action = useAction()
  const [query, setQuery] = useState('')
  const [input, setInput] = useState('')
  const users = useLoad<Identity[]>(query, () => api(`/auth/users?q=${encodeURIComponent(query)}`))

  function change(id: string, data: { role?: Role; active?: boolean }) {
    void action.run(async () => {
      await api(`/auth/users/${id}/role`, { method: 'PATCH', body: data })
      users.reload()
    })
  }
  return (
    <section className="page-section">
      <h2>{t('Account access')}</h2>
      <form
        className="search-row row"
        onSubmit={(e) => {
          e.preventDefault()
          setQuery(input.trim())
        }}
      >
        <label>
          {t('Search users')}
          <input type="search" value={input} onChange={(e) => setInput(e.target.value)} />
        </label>
        <button>{t('Search')}</button>
      </form>
      <ErrorMessage error={action.error} />
      <Data state={users}>
        {(items) =>
          items.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('Username')}</th>
                    <th>{t('Email')}</th>
                    <th>{t('Role')}</th>
                    <th>{t('Account access')}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name}</td>
                      <td>{item.email}</td>
                      <td>
                        {item.role === 'admin' ? (
                          t('Admin')
                        ) : (
                          <select
                            aria-label={`${t('Role')}: ${item.name}`}
                            value={item.role}
                            disabled={action.busy}
                            onChange={(e) => change(item.id, { role: e.target.value as Role })}
                          >
                            <option value="student">{t('Student')}</option>
                            <option value="teacher">{t('Teacher')}</option>
                          </select>
                        )}
                      </td>
                      <td>
                        {t(item.active ? 'Active' : 'Blocked')}
                        {item.role !== 'admin' && (
                          <button
                            type="button"
                            disabled={action.busy}
                            onClick={() => {
                              if (
                                !item.active ||
                                confirm(t('Block {{name}}?', { name: item.name }))
                              )
                                change(item.id, { active: !item.active })
                            }}
                          >
                            {t(item.active ? 'Block' : 'Unblock')}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>{t('No users found.')}</Empty>
          )
        }
      </Data>
    </section>
  )
}

function BackToTeaching() {
  const { t } = useTranslation()
  return (
    <Link className="back-link" to="/teach">
      {t('Teaching')}
    </Link>
  )
}

type ModuleDraft = { title: string; lessons: (LessonDraft & { id: string })[] }
type AuthorCourse = CourseFields & { slug: string; modules: ModuleDraft[] }
const blankCourse: AuthorCourse = {
  slug: '',
  title: '',
  description: '',
  language: 'python',
  topics: [],
  modules: [],
  published: false,
}

export function CourseStudio() {
  const { slug = 'new' } = useParams()
  const state = useLoad<AuthorCourse>(
    slug,
    () => api(`/edu/courses/${slug}?author=true`),
    slug !== 'new',
  )
  return slug === 'new' ? (
    <EditCourse key="new" original={blankCourse} />
  ) : (
    <Data state={state}>
      {(course) => <EditCourse key={slug} original={course} reload={state.reload} />}
    </Data>
  )
}

function EditCourse({ original, reload }: { original: AuthorCourse; reload?: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const action = useAction()
  const [draft, setDraft] = useState(original)
  const [topics, setTopics] = useState(original.topics.join('\n'))
  const [lesson, setLesson] = useState<{ module: number; doc?: LessonDraft & { id: string } }>()
  const [saved, setSaved] = useState(false)
  const exists = Boolean(original.slug)
  // After a lesson mutation the server owns IDs. Retain unsaved text and course preferences.
  const [source, setSource] = useState(original)
  if (source !== original) {
    setSource(original)
    setDraft((previous) => ({ ...previous, modules: original.modules }))
  }
  function patch(fields: Partial<AuthorCourse>) {
    setDraft({ ...draft, ...fields })
    setSaved(false)
  }
  function patchModule(index: number, replacement: ModuleDraft) {
    patch({ modules: draft.modules.map((item, i) => (i === index ? replacement : item)) })
  }
  async function save(event: FormEvent) {
    await action.run(async () => {
      const payload = {
        ...draft,
        topics: topics
          .split('\n')
          .map((value) => value.trim())
          .filter(Boolean),
        modules: draft.modules.map((module) => ({
          title: module.title,
          lessons: module.lessons.map((item) => item.id),
        })),
      }
      const course = await api<Course>(exists ? `/edu/courses/${original.slug}` : '/edu/courses', {
        method: exists ? 'PATCH' : 'POST',
        body: payload,
      })
      if (!exists) navigate(`/teach/courses/${course.slug}`, { replace: true })
      else {
        reload?.()
        setSaved(true)
      }
    }, event)
  }

  return (
    <>
      <BackToTeaching />
      <PageHeading title={exists ? original.title : t('New course')}>
        {exists && (
          <Link className="button" to={`/teach/courses/${original.slug}/gradebook`}>
            {t('Gradebook')}
          </Link>
        )}
      </PageHeading>
      <form className="stack panel" onSubmit={(e) => void save(e)}>
        <div className="form-grid">
          {!exists && (
            <label>
              {t('Course URL slug')}
              <input
                required
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
                maxLength={80}
                value={draft.slug}
                onChange={(e) => patch({ slug: e.target.value })}
              />
            </label>
          )}
          <label>
            {t('Title')}
            <input
              required
              maxLength={120}
              value={draft.title}
              onChange={(e) => patch({ title: e.target.value })}
            />
          </label>
          <LanguageSelect value={draft.language} onChange={(language) => patch({ language })} />
          <label>
            {t('Description')}
            <textarea
              required
              value={draft.description}
              onChange={(e) => patch({ description: e.target.value })}
            />
          </label>
          <label>
            {t('Topics (one per line)')}
            <textarea value={topics} onChange={(e) => setTopics(e.target.value)} />
          </label>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={draft.published}
            disabled={!exists}
            onChange={(e) => patch({ published: e.target.checked })}
          />
          {t('Published')}
        </label>
        <h2>{t('Modules')}</h2>
        {draft.modules.map((module, index) => (
          <fieldset key={index} className="stack picker">
            <legend>
              {t('Module title')} {index + 1}
            </legend>
            <div className="row">
              <input
                aria-label={`${t('Module title')} ${index + 1}`}
                required
                value={module.title}
                onChange={(e) => patchModule(index, { ...module, title: e.target.value })}
              />
              <OrderControls
                index={index}
                length={draft.modules.length}
                moveBy={(by) => patch({ modules: moveItem(draft.modules, index, by) })}
              />
              <button
                type="button"
                disabled={module.lessons.length > 0}
                onClick={() => patch({ modules: draft.modules.filter((_, n) => index !== n) })}
              >
                {t('Remove')}
              </button>
            </div>
            <ol className="ordered-items">
              {module.lessons.map((item, position) => (
                <li key={item.id}>
                  <strong>{item.title}</strong>
                  <span>{t(typeNames[item.type])}</span>
                  <select
                    value={index}
                    aria-label={`${t('Move to module')}: ${item.title}`}
                    onChange={(e) => {
                      const next = Number(e.target.value)
                      patch({
                        modules: draft.modules.map((value, i) =>
                          i === index
                            ? {
                                ...value,
                                lessons: value.lessons.filter((entry) => entry.id !== item.id),
                              }
                            : i === next
                              ? { ...value, lessons: [...value.lessons, item] }
                              : value,
                        ),
                      })
                    }}
                  >
                    {draft.modules.map((entry, i) => (
                      <option key={i} value={i}>
                        {entry.title}
                      </option>
                    ))}
                  </select>
                  <OrderControls
                    index={position}
                    length={module.lessons.length}
                    moveBy={(by) =>
                      patchModule(index, {
                        ...module,
                        lessons: moveItem(module.lessons, position, by),
                      })
                    }
                  />
                  <button type="button" onClick={() => setLesson({ doc: item, module: index })}>
                    {t('Edit')}
                  </button>
                </li>
              ))}
            </ol>
            {exists && (
              <button
                type="button"
                className="button"
                disabled={original.modules[index]?.title !== module.title}
                onClick={() => setLesson({ module: index })}
              >
                <Plus size={16} aria-hidden />
                {t('Add lesson')}
              </button>
            )}
          </fieldset>
        ))}
        <button
          type="button"
          className="button"
          onClick={() => patch({ modules: [...draft.modules, { title: '', lessons: [] }] })}
        >
          <Plus size={16} aria-hidden />
          {t('Add module')}
        </button>
        <ErrorMessage error={action.error} />
        <div className="row">
          <button className="button primary" disabled={action.busy}>
            {t('Save')}
          </button>
          {exists && (
            <button
              type="button"
              className="danger"
              disabled={action.busy}
              onClick={() => {
                if (
                  confirm(
                    t('Archive {{name}}? Existing submissions will remain in history.', {
                      name: original.title,
                    }),
                  )
                ) {
                  void action.run(async () => {
                    await api(`/edu/courses/${original.slug}`, { method: 'DELETE' })
                    navigate('/teach')
                  })
                }
              }}
            >
              {t('Delete')}
            </button>
          )}
          {saved && <span role="status">{t('Saved')}</span>}
        </div>
      </form>
      {lesson && (
        <LessonForm
          key={lesson.doc?.id ?? `module-${lesson.module}`}
          course={original}
          module={lesson.module}
          original={lesson.doc}
          close={(changed) => {
            setLesson(undefined)
            if (changed) reload?.()
          }}
        />
      )}
    </>
  )
}

function OrderControls({
  index,
  length,
  moveBy,
}: {
  index: number
  length: number
  moveBy: (by: number) => void
}) {
  const { t } = useTranslation()
  return (
    <>
      <button
        type="button"
        className="icon-button"
        disabled={index === 0}
        aria-label={t('Move up')}
        onClick={() => moveBy(-1)}
      >
        <ArrowUp size={16} />
      </button>
      <button
        type="button"
        className="icon-button"
        disabled={index === length - 1}
        aria-label={t('Move down')}
        onClick={() => moveBy(1)}
      >
        <ArrowDown size={16} />
      </button>
    </>
  )
}

const blankQuestion = (): AuthorQuestion => ({
  text: '',
  options: ['', ''],
  correct: [0],
  multiple: false,
})

function LessonForm({
  course,
  module,
  original,
  close,
}: {
  course: AuthorCourse
  module: number
  original?: LessonDraft & { id: string }
  close: (changed: boolean) => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const bank = useLoad<TaskMetadata[]>('bank', () => api('/edu/tasks'))
  const [lesson, setLesson] = useState<LessonDraft>(
    original ?? {
      title: '',
      topic: course.topics[0] ?? '',
      type: 'theory',
      body: '',
    },
  )
  const path = original ? `/edu/lessons/${original.id}` : '/edu/lessons'
  const [preview, setPreview] = useState(false)
  return (
    <form
      className="panel stack page-section"
      onSubmit={(e) =>
        void action.run(async () => {
          await api(path, {
            method: original ? 'PATCH' : 'POST',
            body: original ? lesson : { course_slug: course.slug, module, lesson },
          })
          close(true)
        }, e)
      }
    >
      <h2>{original ? `${t('Edit')}: ${original.title}` : t('Add lesson')}</h2>
      <div className="form-grid">
        <label>
          {t('Title')}
          <input
            required
            value={lesson.title}
            onChange={(e) => setLesson({ ...lesson, title: e.target.value })}
          />
        </label>
        <label>
          {t('Topic')}
          <select
            required
            value={lesson.topic}
            onChange={(e) => setLesson({ ...lesson, topic: e.target.value })}
          >
            <option value="">{t('Topic')}</option>
            {course.topics.map((topic) => (
              <option key={topic}>{topic}</option>
            ))}
          </select>
        </label>
        <label>
          {t('Lesson type')}
          <select
            value={lesson.type}
            onChange={(e) => {
              const fields = { title: lesson.title, topic: lesson.topic }
              if (e.target.value === 'theory') setLesson({ ...fields, type: 'theory', body: '' })
              if (e.target.value === 'quiz')
                setLesson({ ...fields, type: 'quiz', questions: [blankQuestion()] })
              if (e.target.value === 'practice')
                setLesson({ ...fields, type: 'practice', task_id: '' })
            }}
          >
            {Object.entries(typeNames).map(([key, value]) => (
              <option key={key} value={key}>
                {t(value)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {lesson.type === 'theory' && (
        <>
          <label>
            {t('Markdown')}
            <textarea
              className="code-input"
              required
              value={lesson.body}
              onChange={(e) => setLesson({ ...lesson, body: e.target.value })}
            />
          </label>
          <button type="button" aria-pressed={preview} onClick={() => setPreview(!preview)}>
            {t('Preview')}
          </button>
          {preview && (
            <div className="markdown">
              <Markdown>{lesson.body}</Markdown>
            </div>
          )}
        </>
      )}
      {lesson.type === 'quiz' && (
        <QuestionEditor
          items={lesson.questions}
          onChange={(questions) => setLesson({ ...lesson, questions })}
        />
      )}
      {lesson.type === 'practice' && (
        <Data state={bank}>
          {(items) => (
            <label>
              {t('Select task')}
              <select
                required
                value={lesson.task_id}
                onChange={(e) => setLesson({ ...lesson, task_id: e.target.value })}
              >
                <option value="">{t('Select task')}</option>
                {items.map((item) => (
                  <option key={item.task_id} value={item.task_id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
          )}
        </Data>
      )}
      <ErrorMessage error={action.error} />
      <div className="row">
        <button className="button primary" disabled={action.busy}>
          {t('Save')}
        </button>
        <button type="button" onClick={() => close(false)}>
          {t('Cancel')}
        </button>
        {original && (
          <button
            type="button"
            className="danger"
            disabled={action.busy}
            onClick={() => {
              if (
                confirm(
                  t('Archive {{name}}? Existing submissions will remain in history.', {
                    name: original.title,
                  }),
                )
              ) {
                void action.run(async () => {
                  await api(path, { method: 'DELETE' })
                  close(true)
                })
              }
            }}
          >
            {t('Delete')}
          </button>
        )}
      </div>
    </form>
  )
}

function QuestionEditor({
  items,
  onChange,
}: {
  items: AuthorQuestion[]
  onChange: (items: AuthorQuestion[]) => void
}) {
  const { t } = useTranslation()
  return (
    <>
      <h3>{t('Questions')}</h3>
      {items.map((item, index) => {
        function update(fields: Partial<AuthorQuestion>) {
          onChange(items.map((entry, i) => (i === index ? { ...entry, ...fields } : entry)))
        }
        return (
          <fieldset className="picker stack compact" key={index}>
            <legend>
              {t('Question')} {index + 1}
            </legend>
            <label>
              {t('Question')}
              <input
                required
                value={item.text}
                onChange={(e) => update({ text: e.target.value })}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={item.multiple}
                onChange={(e) =>
                  update({
                    multiple: e.target.checked,
                    correct: e.target.checked ? item.correct : [item.correct[0] ?? 0],
                  })
                }
              />
              {t('Multiple answers')}
            </label>
            {item.options.map((option, choice) => (
              <div className="row" key={choice}>
                <label>
                  {t('Option')} {choice + 1}
                  <input
                    required
                    value={option}
                    onChange={(e) =>
                      update({
                        options: item.options.map((value, i) =>
                          i === choice ? e.target.value : value,
                        ),
                      })
                    }
                  />
                </label>
                <label className="check">
                  <input
                    type={item.multiple ? 'checkbox' : 'radio'}
                    name={`correct-${index}`}
                    checked={item.correct.includes(choice)}
                    onChange={(e) =>
                      update({
                        correct: item.multiple
                          ? e.target.checked
                            ? [...item.correct, choice]
                            : item.correct.filter((n) => n !== choice)
                          : [choice],
                      })
                    }
                  />
                  {t('Correct')}
                </label>
                <button
                  type="button"
                  disabled={item.options.length <= 2}
                  onClick={() =>
                    update({
                      options: item.options.filter((_, n) => n !== choice),
                      correct: item.correct
                        .filter((n) => n !== choice)
                        .map((n) => (n > choice ? n - 1 : n)),
                    })
                  }
                >
                  {t('Remove')}
                </button>
              </div>
            ))}
            <div className="row">
              <button
                type="button"
                disabled={item.options.length >= 12}
                onClick={() => update({ options: [...item.options, ''] })}
              >
                {t('Add option')}
              </button>
              <button
                type="button"
                disabled={items.length <= 1}
                onClick={() => onChange(items.filter((_, n) => n !== index))}
              >
                {t('Remove')}
              </button>
            </div>
          </fieldset>
        )
      })}
      <button
        type="button"
        disabled={items.length >= 30}
        onClick={() => onChange([...items, blankQuestion()])}
      >
        {t('Add question')}
      </button>
    </>
  )
}

const blankTask: TaskDraft = {
  title: '',
  statement: '',
  difficulty: 'easy',
  templates: { python: '# Python\n' },
  time_ms: 1000,
  memory_kb: 65536,
  contest_ready: false,
  tests: [{ stdin: '', expected: '', public: true }],
}

export function TaskStudio() {
  const { id = 'new' } = useParams()
  const tasks = useLoad<TaskDraft>(id, () => api(`/edu/tasks/${id}`), id !== 'new')
  return id === 'new' ? (
    <EditTask key="new" original={blankTask} />
  ) : (
    <Data state={tasks}>{(task) => <EditTask key={id} id={id} original={task} />}</Data>
  )
}

function EditTask({ id, original }: { id?: string; original: TaskDraft }) {
  const { t } = useTranslation()
  const action = useAction()
  const navigate = useNavigate()
  const [draft, setDraft] = useState(original)
  const path = id ? `/edu/tasks/${id}` : '/edu/tasks'
  function patch(fields: Partial<TaskDraft>) {
    setDraft({ ...draft, ...fields })
  }

  return (
    <>
      <BackToTeaching />
      <PageHeading title={id ? original.title : t('New task')} />
      <form
        className="panel stack"
        onSubmit={(e) =>
          void action.run(async () => {
            await api(path, { method: id ? 'PATCH' : 'POST', body: draft })
            navigate('/teach')
          }, e)
        }
      >
        <div className="form-grid">
          <label>
            {t('Title')}
            <input
              required
              maxLength={120}
              value={draft.title}
              onChange={(e) => patch({ title: e.target.value })}
            />
          </label>
          <label>
            {t('Difficulty')}
            <select
              value={draft.difficulty}
              onChange={(e) => patch({ difficulty: e.target.value as TaskDraft['difficulty'] })}
            >
              {Object.entries(difficultyNames).map(([key, value]) => (
                <option key={key} value={key}>
                  {t(value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('Time (ms)')}
            <input
              type="number"
              required
              min={1}
              max={10000}
              value={draft.time_ms}
              onChange={(e) => patch({ time_ms: Number(e.target.value) })}
            />
          </label>
          <label>
            {t('Memory (KiB)')}
            <input
              type="number"
              required
              min={1024}
              max={262144}
              value={draft.memory_kb}
              onChange={(e) => patch({ memory_kb: Number(e.target.value) })}
            />
          </label>
        </div>
        <label>
          {t('Statement')}
          <textarea
            required
            value={draft.statement}
            onChange={(e) => patch({ statement: e.target.value })}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={draft.contest_ready}
            onChange={(e) => patch({ contest_ready: e.target.checked })}
          />
          {t('Eligible for contests')}
        </label>
        <div className="form-grid">
          {(['python', 'cpp'] as const).map((language) => (
            <fieldset key={language} className="stack compact picker">
              <legend>{languageNames[language]}</legend>
              <label className="check">
                <input
                  type="checkbox"
                  checked={language in draft.templates}
                  onChange={(e) => {
                    const templates = { ...draft.templates }
                    if (e.target.checked)
                      templates[language] =
                        language === 'cpp' ? '#include <iostream>\n' : '# Python\n'
                    else delete templates[language]
                    patch({ templates })
                  }}
                />
                {languageNames[language]}
              </label>
              {language in draft.templates && (
                <label>
                  {t('Template')}
                  <textarea
                    className="code-input short"
                    required
                    value={draft.templates[language]}
                    onChange={(e) =>
                      patch({ templates: { ...draft.templates, [language]: e.target.value } })
                    }
                  />
                </label>
              )}
            </fieldset>
          ))}
        </div>
        <h2>{t('Tests')}</h2>
        {draft.tests.map((test, index) => (
          <fieldset key={index} className="picker stack compact">
            <legend>
              {t('Tests')} {index + 1}
            </legend>
            <div className="form-grid">
              <label>
                {t('Input')}
                <textarea
                  value={test.stdin}
                  onChange={(e) =>
                    patch({
                      tests: draft.tests.map((item, i) =>
                        i === index ? { ...item, stdin: e.target.value } : item,
                      ),
                    })
                  }
                />
              </label>
              <label>
                {t('Expected output')}
                <textarea
                  value={test.expected}
                  onChange={(e) =>
                    patch({
                      tests: draft.tests.map((item, i) =>
                        i === index ? { ...item, expected: e.target.value } : item,
                      ),
                    })
                  }
                />
              </label>
            </div>
            <div className="row">
              <label className="check">
                <input
                  type="checkbox"
                  checked={test.public}
                  onChange={(e) =>
                    patch({
                      tests: draft.tests.map((item, i) =>
                        i === index ? { ...item, public: e.target.checked } : item,
                      ),
                    })
                  }
                />
                {t('Public example')}
              </label>
              <OrderControls
                index={index}
                length={draft.tests.length}
                moveBy={(by) => patch({ tests: moveItem(draft.tests, index, by) })}
              />
              <button
                type="button"
                disabled={draft.tests.length <= 1}
                onClick={() => patch({ tests: draft.tests.filter((_, i) => index !== i) })}
              >
                {t('Remove')}
              </button>
            </div>
          </fieldset>
        ))}
        <button
          type="button"
          disabled={draft.tests.length >= 30}
          onClick={() =>
            patch({
              tests: [...draft.tests, { stdin: '', expected: '', public: false }],
            })
          }
        >
          {t('Add test')}
        </button>
        <ErrorMessage error={action.error} />
        <div className="row">
          <button className="button primary" disabled={action.busy}>
            {t('Save')}
          </button>
          {id && (
            <button
              type="button"
              className="danger"
              disabled={action.busy}
              onClick={() => {
                if (
                  confirm(
                    t('Archive {{name}}? Existing submissions will remain in history.', {
                      name: original.title,
                    }),
                  )
                ) {
                  void action.run(async () => {
                    await api(path, { method: 'DELETE' })
                    navigate('/teach')
                  })
                }
              }}
            >
              {t('Delete')}
            </button>
          )}
        </div>
      </form>
    </>
  )
}

export function GradebookPage() {
  const { slug = '' } = useParams()
  const { t } = useTranslation()
  const action = useAction()
  const endpoint = `/edu/courses/${slug}/gradebook`
  const state = useLoad<Gradebook>(slug, () => api(endpoint))
  return (
    <>
      <Link className="back-link" to={`/teach/courses/${slug}`}>
        {t('Back')}
      </Link>
      <PageHeading title={t('Gradebook')}>
        <button
          className="button"
          disabled={action.busy || !state.data}
          onClick={() =>
            void action.run(async () => {
              const response = await request(`${endpoint}?format=csv`)
              const url = URL.createObjectURL(await response.blob())
              const link = document.createElement('a')
              link.href = url
              link.download = `${slug}.csv`
              link.click()
              window.setTimeout(() => URL.revokeObjectURL(url), 1000)
            })
          }
        >
          <Download size={17} aria-hidden />
          {t('Download CSV')}
        </button>
      </PageHeading>
      <ErrorMessage error={action.error} />
      <Data state={state}>
        {(data) => (
          <>
            {!data.columns.length && <p>{t('No published lessons')}</p>}
            {!data.rows.length ? (
              <Empty>{t('No enrolled students.')}</Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t('Participant')}</th>
                      {data.columns.map((column) => (
                        <th key={column.id}>{column.title}</th>
                      ))}
                      <th>{t('Result')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((row) => (
                      <tr key={row.id}>
                        <th scope="row">{row.name}</th>
                        {row.cells.map((cell) => (
                          <td key={cell.lesson_id}>
                            {t(
                              {
                                completed: 'Completed',
                                attempted: 'Attempted',
                                unstarted: 'No attempt',
                              }[cell.status],
                            )}
                            <small>
                              {cell.xp} XP{cell.task_xp ? ` + ${cell.task_xp} XP` : ''}
                            </small>
                          </td>
                        ))}
                        <td>{row.percent === null ? '—' : `${row.percent}%`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </Data>
    </>
  )
}
