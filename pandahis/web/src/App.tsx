import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './app/AppLayout'
import { BoxPage } from './pages/BoxPage'
import { ExplorePage } from './pages/ExplorePage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { MemberPage } from './pages/MemberPage'
import { MyPage } from './pages/MyPage'
import { SearchPage } from './pages/SearchPage'
import { TopicDetailPage } from './pages/TopicDetailPage'
import { TopicsPage } from './pages/TopicsPage'
import { UnitPage } from './pages/UnitPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/topics" element={<TopicsPage />} />
          <Route path="/topics/:topicId" element={<TopicDetailPage />} />
          <Route path="/units/:unitId" element={<UnitPage />} />
          <Route path="/boxes/:boxId" element={<BoxPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/member" element={<MemberPage />} />
          <Route path="/my" element={<MyPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

