import { useState, type FormEvent } from 'react'
import { ArrowDown, ArrowUp, Download, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Markdown from 'react-markdown'

import { useLoad, useSession } from '../application/state'
import {
  difficultyNames,
  languageNames,
  languages,
  type Language,
  moveItem,
  typeNames,
  type AuthorQuestion,
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
                      {task.languages.map((language) => languageNames[language] ?? language).join(', ')}
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
type AuthorCourse = CourseFields & { slug: string; revision: string; modules: ModuleDraft[] }
type TaskChoice = Pick<TaskMetadata, 'task_id' | 'title'>
const blankCourse: AuthorCourse = {
  slug: '',
  revision: '',
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
      {(course) => (
        <EditCourse key={slug} original={course} reload={state.reload} onSave={state.set} />
      )}
    </Data>
  )
}

function EditCourse({
  original,
  reload,
  onSave,
}: {
  original: AuthorCourse
  reload?: () => void
  onSave?: (course: AuthorCourse) => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const action = useAction()
  const [draft, setDraft] = useState(original)
  const [topicName, setTopicName] = useState('')
  const [lesson, setLesson] = useState<{
    module: number
    doc?: LessonDraft & { id: string }
    practice?: boolean
  }>()
  const [saved, setSaved] = useState(false)
  const exists = Boolean(original.slug)
  const topicsChanged = JSON.stringify(draft.topics) !== JSON.stringify(original.topics)
  const newTopic = topicName.trim()
  const canAddTopic =
    Boolean(newTopic) && !draft.topics.includes(newTopic) && draft.topics.length < 30
  const usedTopics = new Set(
    original.modules.flatMap((module) => module.lessons.map((item) => item.topic)),
  )
  // After a lesson mutation the server owns IDs. Retain unsaved text and course preferences.
  const [source, setSource] = useState(original)
  if (source !== original) {
    setSource(original)
    setDraft((previous) =>
      previous.revision === original.revision ? { ...previous, modules: original.modules } : previous,
    )
  }
  function patch(fields: Partial<AuthorCourse>) {
    setDraft({ ...draft, ...fields })
    setSaved(false)
  }
  function canAddLesson(index: number) {
    return (
      !action.busy &&
      !lesson &&
      draft.revision === original.revision &&
      !topicsChanged &&
      original.topics.length > 0 &&
      original.modules[index]?.title === draft.modules[index].title
    )
  }
  function patchModule(index: number, replacement: ModuleDraft) {
    patch({ modules: draft.modules.map((item, i) => (i === index ? replacement : item)) })
  }
  function addTopic() {
    if (!canAddTopic) return
    patch({ topics: [...draft.topics, newTopic] })
    setTopicName('')
  }
  async function save(event: FormEvent) {
    await action.run(async () => {
      const payload = {
        ...draft,
        modules: draft.modules.map((module) => ({
          title: module.title,
          lessons: module.lessons.map((item) => item.id),
        })),
      }
      const course = await api<AuthorCourse>(exists ? `/edu/courses/${original.slug}` : '/edu/courses', {
        method: exists ? 'PATCH' : 'POST',
        body: payload,
        headers: exists ? { 'If-Match': `"${draft.revision}"` } : undefined,
      })
      if (!exists) navigate(`/teach/courses/${course.slug}`, { replace: true })
      else {
        setDraft(course)
        onSave?.(course)
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
        <fieldset className="stack course-fields" disabled={action.busy || Boolean(lesson)}>
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
          </div>
          <fieldset className="stack picker">
            <legend>{t('Lesson topics')}</legend>
            <div className="row">
              <label>
                {t('Topic name')}
                <input
                  value={topicName}
                  maxLength={120}
                  onChange={(e) => setTopicName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addTopic()
                    }
                  }}
                />
              </label>
              <button type="button" disabled={!canAddTopic} onClick={addTopic}>
                {t('Add topic')}
              </button>
            </div>
            {draft.topics.length > 0 && (
              <ul className="ordered-items">
                {draft.topics.map((topic) => (
                  <li key={topic}>
                    <strong>{topic}</strong>
                    {usedTopics.has(topic) ? (
                      <span>{t('Used in lessons')}</span>
                    ) : (
                      <button
                        type="button"
                        aria-label={t('Remove topic {{name}}', { name: topic })}
                        onClick={() => patch({ topics: draft.topics.filter((item) => item !== topic) })}
                      >
                        {t('Remove')}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {topicsChanged ? (
              <p role="status">{t('Save the course to apply topic changes.')}</p>
            ) : !original.topics.length ? (
              <p>{t('Add a topic and save the course before adding lessons.')}</p>
            ) : null}
          </fieldset>
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
                    <span>{item.topic}</span>
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
                    <button
                      type="button"
                      disabled={action.busy}
                      onClick={() => setLesson({ doc: item, module: index })}
                    >
                      {t('Edit')}
                    </button>
                  </li>
                ))}
              </ol>
              {exists && (
                <div className="row">
                  <button
                    type="button"
                    className="button"
                    disabled={!canAddLesson(index)}
                    onClick={() => setLesson({ module: index })}
                  >
                    <Plus size={16} aria-hidden />
                    {t('Add lesson')}
                  </button>
                  <button
                    type="button"
                    className="button"
                    disabled={!canAddLesson(index)}
                    onClick={() => setLesson({ module: index, practice: true })}
                  >
                    <Plus size={16} aria-hidden />
                    {t('Add practice lesson')}
                  </button>
                </div>
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
            <button className="button primary" disabled={draft.revision !== original.revision}>
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
        </fieldset>
      </form>
      {lesson && (
        <LessonForm
          key={lesson.doc?.id ?? `${lesson.module}-${lesson.practice}`}
          course={original}
          module={lesson.module}
          original={lesson.doc}
          practice={lesson.practice}
          close={(revision) => {
            setLesson(undefined)
            if (revision) {
              setDraft((previous) => ({ ...previous, revision }))
              reload?.()
            }
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
  practice,
  close,
}: {
  course: AuthorCourse
  module: number
  original?: LessonDraft & { id: string }
  practice?: boolean
  close: (revision?: string) => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const [initial] = useState<LessonDraft>(
    original ??
      (practice
        ? { title: '', topic: '', type: 'practice', task_id: '' }
        : { title: '', topic: '', type: 'theory', body: '' }),
  )
  const [lesson, setLesson] = useState(initial)
  const headers = { 'If-Match': `"${course.revision}"` }
  const bank = useLoad<TaskChoice[]>('bank', () => api('/edu/tasks'), lesson.type === 'practice')
  const path = original ? `/edu/lessons/${original.id}` : '/edu/lessons'
  const [preview, setPreview] = useState(false)
  const [creatingTask, setCreatingTask] = useState(false)
  if (creatingTask && lesson.type === 'practice') {
    return (
      <section className="page-section">
        <h2>
          {t('New task')} · {lesson.topic}
        </h2>
        <EditTask
          original={blankTask}
          onCancel={() => setCreatingTask(false)}
          onCreate={(task) => {
            bank.set([...(bank.data ?? []), task])
            setLesson({ ...lesson, title: lesson.title || task.title, task_id: task.task_id })
            setCreatingTask(false)
          }}
        />
      </section>
    )
  }
  return (
    <form
      className="panel stack page-section"
      onSubmit={(e) =>
        void action.run(async () => {
          const change = await api<{ revision: string }>(path, {
            headers,
            method: original ? 'PATCH' : 'POST',
            body: original ? lesson : { course_slug: course.slug, module, lesson },
          })
          close(change.revision)
        }, e)
      }
    >
      <h2>
        {original ? `${t('Edit')}: ${original.title}` : t(practice ? 'Add practice lesson' : 'Add lesson')}
      </h2>
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
            <option value="">{t('Select a topic')}</option>
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
        <>
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
          <button
            type="button"
            disabled={!lesson.topic || !bank.data || action.busy}
            onClick={() => setCreatingTask(true)}
          >
            {t('Create task for this lesson')}
          </button>
        </>
      )}
      <ErrorMessage error={action.error} />
      <div className="row">
        <button
          className="button primary"
          disabled={action.busy || (lesson.type === 'practice' && !lesson.task_id)}
        >
          {t('Save')}
        </button>
        <button
          type="button"
          disabled={action.busy}
          onClick={() => {
            if (lesson === initial || confirm(t('Discard unsaved changes?'))) close()
          }}
        >
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
                  const response = await request(path, { method: 'DELETE', headers })
                  close(response.headers.get('ETag')?.replace(/"/g, ''))
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

const starterCode: Partial<Record<Language, string>> = {
  python: '# Python\n',
  cpp: '#include <iostream>\n\nint main() {\n    return 0;\n}\n',
  javascript: "const fs = require('fs');\nconst input = fs.readFileSync(0, 'utf8');\n",
  java: 'public class Main {\n    public static void main(String[] args) {\n    }\n}\n',
  go: 'package main\n\nfunc main() {\n}\n',
  rust: 'fn main() {\n}\n',
}

const blankTask: TaskDraft = {
  title: '',
  statement: '',
  difficulty: 'easy',
  templates: { python: starterCode.python },
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

function EditTask({
  id,
  original,
  onCreate,
  onCancel,
}: {
  id?: string
  original: TaskDraft
  onCreate?: (task: TaskChoice) => void
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const navigate = useNavigate()
  const [draft, setDraft] = useState(original)
  const path = id ? `/edu/tasks/${id}` : '/edu/tasks'
  const templateLanguages = Object.keys(draft.templates) as Language[]
  const hasRetiredTemplates = templateLanguages.some((language) => !languages.includes(language))
  function patch(fields: Partial<TaskDraft>) {
    setDraft({ ...draft, ...fields })
  }

  return (
    <>
      {!onCreate && (
        <>
          <BackToTeaching />
          <PageHeading title={id ? original.title : t('New task')} />
          {!id && <p>{t('To choose a course topic, add a practice lesson in the course editor.')}</p>}
        </>
      )}
      <form
        className="panel stack"
        onSubmit={(e) =>
          void action.run(async () => {
            const task = await api<TaskChoice>(path, {
              method: id ? 'PATCH' : 'POST',
              body: draft,
              headers: id ? { 'If-Match': `"${original.version}"` } : undefined,
            })
            if (onCreate) onCreate(task)
            else navigate('/teach')
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
        <label>
          {t('Add programming language')}
          <select
            value=""
            disabled={languages.every((language) => language in draft.templates)}
            onChange={(e) => {
              const language = e.target.value as Language
              patch({ templates: { ...draft.templates, [language]: starterCode[language] ?? '' } })
            }}
          >
            <option value="" disabled>{t('Add programming language')}</option>
            {languages.filter((language) => !(language in draft.templates)).map((language) => (
              <option key={language} value={language}>{languageNames[language]}</option>
            ))}
          </select>
        </label>
        <div className="form-grid">
          {templateLanguages.map((language) => (
            <fieldset key={language} className="stack compact picker">
              <legend>{languageNames[language] ?? language}</legend>
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
              <button
                type="button"
                disabled={templateLanguages.length === 1 && languages.includes(language)}
                onClick={() => {
                  const templates = { ...draft.templates }
                  delete templates[language]
                  patch({ templates })
                }}
              >
                {t('Remove')}
              </button>
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
          <button className="button primary" disabled={action.busy || hasRetiredTemplates || !templateLanguages.length}>
            {t(onCreate ? 'Save task to bank' : 'Save')}
          </button>
          {onCancel && (
            <button type="button" disabled={action.busy} onClick={() => {
              if (draft === original || confirm(t('Discard unsaved changes?'))) onCancel()
            }}>
              {t('Cancel')}
            </button>
          )}
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
        {hasRetiredTemplates && <p>{t('Remove unsupported language templates before saving.')}</p>}
      </form>
    </>
  )
}

export function GradebookPage() {
  const { slug = '' } = useParams()
  const { t } = useTranslation()
  const action = useAction()
  const endpoint = `/edu/courses/${slug}/gradebook`
  const [page, setPage] = useState({ slug, offset: 0 })
  const offset = page.slug === slug ? page.offset : 0
  const state = useLoad<Gradebook>(`${slug}:${offset}`, () => api(`${endpoint}?offset=${offset}`))
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
            {(offset > 0 || data.next_offset !== null) && (
              <div className="row">
                <button type="button" disabled={offset === 0}
                  onClick={() => setPage({ slug, offset: Math.max(0, offset - 50) })}
                >
                  {t('Previous page')}
                </button>
                <button type="button" disabled={data.next_offset === null}
                  onClick={() => {
                    if (data.next_offset !== null) setPage({ slug, offset: data.next_offset })
                  }}
                >
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
