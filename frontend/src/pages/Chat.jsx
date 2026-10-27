import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import api, { errMsg } from '../api'

const SUGGESTIONS = [
  'What is the attendance requirement?',
  'What are the library timings?',
  'What is the fee structure for B.Tech CSE?',
  'How do I apply for revaluation?',
]

function Sources({ sources }) {
  const [open, setOpen] = useState(false)
  if (!sources?.length) return null
  return (
    <div className="sources">
      <button className="link" onClick={() => setOpen(!open)}>
        {open ? '▾' : '▸'} {sources.length} sources
      </button>
      {open && sources.map((s) => (
        <div key={s.id} className="source">
          <b>[{s.id}] {s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.source}</a> : s.source}{s.page ? `, p.${s.page}` : ''}</b>
          <span className="tag">{s.category}</span>
          <div className="muted">{s.snippet}</div>
        </div>
      ))}
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [category, setCategory] = useState('all')
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(false)
  const bottom = useRef(null)

  useEffect(() => {
    api.get('/documents/categories').then((r) => setCategories(r.data)).catch(() => {})
    api.get('/chat/history').then((r) => {
      setMessages(r.data.flatMap((h) => [
        { role: 'user', text: h.question },
        { role: 'bot', text: h.answer, sources: h.sources },
      ]))
    }).catch(() => {})
  }, [])

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  const send = async (q) => {
    const question = (q ?? input).trim()
    if (!question || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: question }])
    setLoading(true)
    try {
      const { data } = await api.post('/chat', { question, category })
      setMessages((m) => [...m, { role: 'bot', text: data.answer, sources: data.sources }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'bot', text: `⚠️ ${errMsg(e)}`, error: true }])
    } finally { setLoading(false) }
  }

  const clear = async () => {
    await api.delete('/chat/history'); setMessages([])
  }

  return (
    <main className="chat">
      <div className="chat-tools">
        <label>Topic:&nbsp;
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="all">All</option>
            {categories.map((c) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
          </select>
        </label>
        {messages.length > 0 && <button className="ghost" onClick={clear}>Clear chat</button>}
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">
            <h2>Hi! Ask me about admissions, fees, exams, placements…</h2>
            <div className="chips">
              {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role} ${m.error ? 'err' : ''}`}>
            {m.role === 'bot' ? <ReactMarkdown>{m.text}</ReactMarkdown> : m.text}
            {m.role === 'bot' && <Sources sources={m.sources} />}
          </div>
        ))}
        {loading && <div className="msg bot typing">Searching college documents…</div>}
        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send() }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your question…" />
        <button disabled={loading || !input.trim()}>Send</button>
      </form>
    </main>
  )
}
