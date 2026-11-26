import judgeLanguages from "../../../app/codeforge/common/judge_languages.json"

export type Role = 'student' | 'teacher' | 'admin'
export type Identity = {
  id: string
  name: string
  email: string
  role: Role
  timezone: string
  active: boolean
}

export type Language = keyof typeof judgeLanguages
export const languages = Object.keys(judgeLanguages) as Language[]
export const languageNames = Object.fromEntries(
  languages.map((key) => [key, judgeLanguages[key].name]),
) as Record<Language, string>
export const languageSyntax = (language: Language) => judgeLanguages[language]?.syntax ?? 'plaintext'
export const difficultyNames = { easy: 'Easy', medium: 'Medium', hard: 'Hard' } as const
export const roleNames = { student: 'Student', teacher: 'Teacher', admin: 'Admin' } as const
export const typeNames = { theory: 'Theory', quiz: 'Quiz', practice: 'Practice' } as const
export const roomStates = {
  draft: 'Draft',
  countdown: 'Countdown',
  running: 'Running',
  finished: 'Finished',
} as const

export type CourseFields = {
  title: string
  description: string
  language: Language
  topics: string[]
  published: boolean
}
export type CourseCard = CourseFields & {
  slug: string
  author_id: string
  lesson_count: number
  completed_count: number
  enrolled: boolean
}
export type SummaryLesson = {
  id: string
  title: string
  topic: string
  type: keyof typeof typeNames
}
export type Course = CourseFields & {
  slug: string
  modules: { title: string; lessons: SummaryLesson[] }[]
  enrolled?: boolean
  completed?: string[]
}

export type Question = { text: string; options: string[]; multiple: boolean }
export type AuthorQuestion = Question & { correct: number[] }
export type LessonDraft = { title: string; topic: string } & (
  | { type: 'theory'; body: string }
  | { type: 'quiz'; questions: AuthorQuestion[] }
  | { type: 'practice'; task_id: string }
)
export type Lesson = SummaryLesson & {
  course_slug: string
  course_title: string
  course_language: Language
  completed: boolean
} & (
    | { type: 'theory'; body: string }
    | { type: 'quiz'; questions: Question[] }
    | { type: 'practice'; task: Task }
  )

export type TestCase = { stdin: string; expected: string; public: boolean }
export type TaskFields = {
  title: string
  statement: string
  difficulty: keyof typeof difficultyNames
  templates: Partial<Record<Language, string>>
  time_ms: number
  memory_kb: number
  contest_ready: boolean
}
export type Task = TaskFields & {
  task_id: string
  version: string
  examples: TestCase[]
}
export type TaskDraft = TaskFields & { tests: TestCase[] }
export type TaskMetadata = Pick<Task, 'task_id' | 'title' | 'difficulty'> & {
  languages: Language[]
}

export const verdictLabels = {
  AC: 'Accepted',
  WA: 'Wrong answer',
  TLE: 'Time limit exceeded',
  MLE: 'Memory limit exceeded',
  RE: 'Runtime error',
  CE: 'Compilation error',
  TECHNICAL: 'Judge unavailable',
} as const
export type Verdict = keyof typeof verdictLabels
export type Result = {
  verdict: Verdict
  passed: number
  total: number
  first_failed: number | null
  time_ms: number | null
  memory_kb: number | null
  details: {
    number: number
    public: boolean
    verdict: Verdict
    stdin?: string
    expected?: string | null
    stdout?: string
    diagnostic?: string
    hint?: string
  }[]
}
export type Attempt = {
  id: string
  task_title?: string
  task_id?: string
  label?: string
  code?: string
  language: Language
  state: 'queued' | 'done'
  submitted_at: string
  result?: Result | null
}
export type Profile = {
  xp: number
  level: number
  next_level_xp: number
  streak: number
  best_streak: number
  solved: number
  achievements: { id: string; title: string; description: string; at: string | null }[]
}
export type Gradebook = {
  next_offset: number | null
  columns: SummaryLesson[]
  rows: {
    id: string
    name: string
    percent: number | null
    cells: {
      lesson_id: string
      status: 'completed' | 'attempted' | 'unstarted'
      xp: number
      task_xp: number
    }[]
  }[]
}

export type RoomDraft = { title: string; duration: number; description: string }
export type Room = RoomDraft & {
  id: string
  owner_id: string
  state: keyof typeof roomStates
  start_at: string | null
  end_at: string | null
  server_time: string
  invite?: string
  version: number
  final: boolean
}
export type RoomDetail = Room & {
  participants: { id: string; name: string }[]
  problems: (Pick<Task, 'task_id' | 'title'> & { label: string })[]
}
export type Problem = Task & { label: string }
export type Standings = {
  version: number
  pending: number
  final: boolean
  rows: {
    id: string
    name: string
    place: number
    solved: number
    penalty: number
    cells: Record<string, { accepted: boolean; failures: number; penalty: number }>
  }[]
}
export type LiveEvent =
  | { type: 'submission.result'; id: string; result: Result; practice?: boolean }
  | { type: 'achievement.unlocked'; id: string; title: string; description: string }
  | { type: 'level.up'; level: number; xp: number }
  | { type: 'contest.reward'; id: string; place: number; xp: number }
  | ({ type: 'standings' } & Pick<Standings, 'rows' | 'version'>)
  | { type: 'leader_changed'; name: string; version: number }
  | { type: 'countdown'; start_at: string; server_time: string }
  | { type: 'started' | 'finished' | 'room.updated' | 'identity.updated' }

export function moveItem<T>(values: T[], index: number, direction: number): T[] {
  const next = index + direction
  if (next < 0 || next >= values.length) return values
  const list = [...values]
  list[index] = values[next]
  list[next] = values[index]
  return list
}
