import { useState } from 'react'
import { CircleCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import Markdown from 'react-markdown'

import { sendEducation, useEducation, useLoad, useSession } from '../application/state'
import { typeNames, type Lesson, type Question } from '../domain/models'
import { api, ApiError } from '../infrastructure/api'
import { AttemptHistory, Practice } from './practice'
import { Data, ErrorMessage, PageHeading, useAction } from './ui'

export function LessonPage() {
  const { id = '' } = useParams()
  const { user } = useSession()
  const { t } = useTranslation()
  const state = useLoad<Lesson>(id, () => api(`/edu/lessons/${id}`))
  const action = useAction()
  const [revision, setRevision] = useState(0)
  useEducation((event) => {
    if (!event || (event.type === 'submission.result' && !event.practice)) state.reload()
  })
  if (state.error instanceof ApiError && state.error.body.code === 'enrollment') {
    const slug = state.error.body.context?.course_slug
    return (
      <div className="stack">
        <ErrorMessage error={state.error} />
        <Link to={slug ? `/courses/${slug}` : '/'}>
          {t(slug ? 'Return to course' : 'Go to catalog')}
        </Link>
      </div>
    )
  }
  return (
    <Data state={state}>
      {(lesson) => (
        <>
          <Link className="back-link" to={`/courses/${lesson.course_slug}`}>
            {lesson.course_title}
          </Link>
          <PageHeading title={lesson.title}>
            <span className="chip">
              {t(typeNames[lesson.type])} · {lesson.topic}
            </span>
            {lesson.completed && (
              <span className="status positive">
                <CircleCheck size={16} aria-hidden />
                {t('Completed')}
              </span>
            )}
          </PageHeading>
          {lesson.type === 'theory' && (
            <article className="panel theory stack">
              <div className="markdown">
                <Markdown>{lesson.body}</Markdown>
              </div>
              <button
                type="button"
                className="button primary"
                disabled={lesson.completed || action.busy}
                onClick={() =>
                  void action.run(async () => {
                    await api(`/edu/lessons/${id}/complete`, { method: 'POST' })
                    state.reload()
                    sendEducation()
                  })
                }
              >
                {t('Mark as read')}
              </button>
              <ErrorMessage error={action.error} />
            </article>
          )}
          {lesson.type === 'quiz' && (
            <QuizForm key={id} id={id} questions={lesson.questions} done={state.reload} />
          )}
          {lesson.type === 'practice' && (
            <>
              <Practice
                key={id}
                task={lesson.task}
                preferredLanguage={lesson.course_language}
                draftKey={`cf.edu.${user?.id}.${id}`}
                base="/edu"
                submitUrl={`/edu/tasks/${lesson.task.task_id}/submissions`}
                lessonId={id}
                onSubmit={() => setRevision((n) => n + 1)}
              />
              <AttemptHistory
                base="/edu"
                query={`/edu/tasks/${lesson.task.task_id}/submissions`}
                revision={revision}
              />
            </>
          )}
        </>
      )}
    </Data>
  )
}

function QuizForm({
  id,
  questions,
  done,
}: {
  id: string
  questions: Question[]
  done: () => void
}) {
  const { t } = useTranslation()
  const action = useAction()
  const [selected, setSelected] = useState<Record<number, number[]>>({})
  const [feedback, setFeedback] = useState<{ passed: boolean; errors: number[] }>()
  return (
    <form
      className="stack theory"
      onSubmit={(e) =>
        void action.run(async () => {
          const result = await api<{ passed: boolean; errors: number[] }>(
            `/edu/lessons/${id}/quiz`,
            {
              method: 'POST',
              body: { answers: questions.map((_, index) => selected[index] ?? []) },
            },
          )
          setFeedback(result)
          if (result.passed) {
            done()
            sendEducation()
          }
        }, e)
      }
    >
      {questions.map((question, index) => (
        <fieldset
          key={index}
          className="panel stack compact"
          aria-describedby={feedback?.errors.includes(index) ? `quiz-${index}-error` : undefined}
        >
          <legend>
            {index + 1}. {question.text}
          </legend>
          {question.options.map((option, choice) => (
            <label className="check" key={choice}>
              <input
                name={`q-${index}`}
                type={question.multiple ? 'checkbox' : 'radio'}
                checked={selected[index]?.includes(choice) ?? false}
                onChange={(e) => {
                  const previous = selected[index] ?? []
                  setSelected({
                    ...selected,
                    [index]: question.multiple
                      ? e.target.checked
                        ? [...previous, choice]
                        : previous.filter((item) => item !== choice)
                      : [choice],
                  })
                }}
              />
              {option}
            </label>
          ))}
          {feedback?.errors.includes(index) && (
            <small id={`quiz-${index}-error`} className="negative">
              {t('Check the marked questions.')}
            </small>
          )}
        </fieldset>
      ))}
      <button className="button primary" disabled={action.busy}>
        {t('Check answers')}
      </button>
      <ErrorMessage error={action.error} />
      {feedback && (
        <p role="status">
          {t(
            feedback.passed ? 'Correct answers. Lesson completed.' : 'Check the marked questions.',
          )}
        </p>
      )}
    </form>
  )
}
