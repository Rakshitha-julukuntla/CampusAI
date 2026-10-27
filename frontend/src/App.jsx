import { Navigate, Route, Routes, Link, useNavigate } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Chat from './pages/Chat.jsx'
import Admin from './pages/Admin.jsx'

export const getUser = () => {
  try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
}

function Protected({ children, admin }) {
  const user = getUser()
  if (!user) return <Navigate to="/login" replace />
  if (admin && user.role !== 'admin') return <Navigate to="/" replace />
  return children
}

function Header() {
  const user = getUser()
  const nav = useNavigate()
  if (!user) return null
  return (
    <header className="header">
      <Link to="/" className="brand">🎓 CampusAI</Link>
      <nav>
        <Link to="/">Chat</Link>
        {user.role === 'admin' && <Link to="/admin">Admin</Link>}
        <span className="who">{user.name} · {user.role}</span>
        <button className="ghost" onClick={() => { localStorage.clear(); nav('/login') }}>Logout</button>
      </nav>
    </header>
  )
}

export default function App() {
  return (
    <>
      <Header />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<Protected><Chat /></Protected>} />
        <Route path="/admin" element={<Protected admin><Admin /></Protected>} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </>
  )
}
