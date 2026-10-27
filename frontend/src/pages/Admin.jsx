import { useEffect, useState } from 'react'
import api, { errMsg } from '../api'

export default function Admin() {
  const [docs, setDocs] = useState([])
  const [categories, setCategories] = useState([])
  const [file, setFile] = useState(null)
  const [category, setCategory] = useState('general')
  const [stats, setStats] = useState(null)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    api.get('/documents').then((r) => setDocs(r.data))
    api.get('/documents/stats').then((r) => setStats(r.data)).catch(() => {})
  }
  useEffect(() => {
    api.get('/documents/categories').then((r) => setCategories(r.data))
    load()
  }, [])

  const upload = async (e) => {
    e.preventDefault()
    if (!file) return
    setBusy(true); setStatus('Uploading and indexing… (first time loads the embedding model)')
    const fd = new FormData()
    fd.append('file', file); fd.append('category', category)
    try {
      const { data } = await api.post('/documents/upload', fd)
      setStatus(`✅ ${data.filename} indexed into ${data.chunks} chunks`)
      setFile(null); e.target.reset(); load()
    } catch (e) { setStatus(`❌ ${errMsg(e)}`) } finally { setBusy(false) }
  }

  const reindex = async () => {
    setBusy(true); setStatus('Re-indexing data folder…')
    try {
      const { data } = await api.post('/documents/reindex')
      setStatus(`✅ Re-indexed ${data.files} files → ${data.chunks} chunks`); load()
    } catch (e) { setStatus(`❌ ${errMsg(e)}`) } finally { setBusy(false) }
  }

  const remove = async (id) => {
    if (!confirm('Delete this document from the knowledge base?')) return
    await api.delete(`/documents/${id}`); load()
  }

  return (
    <main className="admin">
      <h2>Knowledge Base</h2>
      {stats && <p className="muted">{stats.total_chunks} chunks indexed across {Object.keys(stats.per_source).length} files</p>}

      <form className="card upload" onSubmit={upload}>
        <input type="file" accept=".pdf,.txt,.md" onChange={(e) => setFile(e.target.files[0])} />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <button disabled={busy || !file}>Upload & index</button>
        <button type="button" className="ghost" disabled={busy} onClick={reindex}>Re-index data folder</button>
      </form>
      {status && <p>{status}</p>}

      <table>
        <thead><tr><th>File</th><th>Category</th><th>Chunks</th><th>Uploaded</th><th></th></tr></thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td>{d.filename}</td><td><span className="tag">{d.category}</span></td><td>{d.chunks}</td>
              <td>{new Date(d.uploaded_at).toLocaleString()}</td>
              <td><button className="ghost danger" onClick={() => remove(d.id)}>Delete</button></td>
            </tr>
          ))}
          {docs.length === 0 && <tr><td colSpan="5" className="muted">No documents yet</td></tr>}
        </tbody>
      </table>
    </main>
  )
}
