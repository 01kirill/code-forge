import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import './infrastructure/i18n'
import { connect, session } from './infrastructure/api'
import './styles.css'
import { SessionProvider } from './application/state'
import { Credentials, ProfilePage } from './presentation/account'
import { Catalog, CoursePage, Leaderboard, PublicProfile } from './presentation/catalog'
import { ContestList, ContestPage, JoinContest, NewContest } from './presentation/contest'
import { Layout, RequireUser } from './presentation/layout'
import { LessonPage } from './presentation/lesson'
import { AttemptPage } from './presentation/practice'
import { CourseStudio, GradebookPage, TaskStudio, Teaching } from './presentation/teaching'
import { ForwardLink, PageHeading } from './presentation/ui'

function NotFound() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeading title={t('Not found')} />
      <ForwardLink to="/">{t('Go to catalog')}</ForwardLink>
    </>
  )
}

createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <SessionProvider transport={{ session, connect }}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Catalog />} />
          <Route path="courses/:slug" element={<CoursePage />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="users/:id" element={<PublicProfile />} />
          <Route path="login" element={<Credentials key="login" register={false} />} />
          <Route path="register" element={<Credentials key="register" register />} />
          <Route element={<RequireUser />}>
            <Route path="lessons/:id" element={<LessonPage />} />
            <Route path="attempts/:id" element={<AttemptPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="contests" element={<ContestList />} />
            <Route path="contests/new" element={<NewContest />} />
            <Route path="contests/:id" element={<ContestPage />} />
            <Route path="join/:token" element={<JoinContest />} />
          </Route>
          <Route element={<RequireUser teaching />}>
            <Route path="teach" element={<Teaching />} />
            <Route path="teach/courses/:slug" element={<CourseStudio />} />
            <Route path="teach/courses/:slug/gradebook" element={<GradebookPage />} />
            <Route path="teach/tasks/:id" element={<TaskStudio />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SessionProvider>
  </BrowserRouter>,
)
