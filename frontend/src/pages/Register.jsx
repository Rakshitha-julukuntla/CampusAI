import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api, { errMsg } from '../api'

export default function Register() {
  const [f, setF] = useState({ name: '', email: '', password: '', role: 'student' })
  const [error, setError] = useState('')
  const nav = useNavigate()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault(); setError('')
    try {
      const { data } = await api.post('/auth/register', f)
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))
      nav('/')
    } catch (e) { setError(errMsg(e)) }
  }

  return (
    <div className="auth-wrap">
      <form className="card auth" onSubmit={submit}>
        <h1>Create account</h1>
        <input placeholder="Full name" value={f.name} onChange={set('name')} required />
        <input type="email" placeholder="Email" value={f.email} onChange={set('email')} required />
        <input type="password" placeholder="Password (min 6 chars)" value={f.password} onChange={set('password')} required minLength={6} />
        <select value={f.role} onChange={set('role')}>
          <option value="student">Student</option>
          <option value="parent">Parent</option>
          <option value="faculty">Faculty</option>
        </select>
        {error && <div className="error">{error}</div>}
        <button>Register</button>
        <p className="muted">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  )
}
