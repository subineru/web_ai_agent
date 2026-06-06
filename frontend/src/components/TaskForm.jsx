import { useState } from 'react'
import { submitTask } from '../api.js'

export default function TaskForm({ onSubmitted }) {
  const [instruction, setInstruction] = useState('')
  const [startUrl, setStartUrl] = useState('')
  const [fields, setFields] = useState('')
  const [policy, setPolicy] = useState('ai_then_human')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const { job_id } = await submitTask({
        instruction,
        startUrl,
        fields: fields
          .split(',')
          .map((f) => f.trim())
          .filter(Boolean),
        handoffPolicy: policy,
      })
      onSubmitted({ jobId: job_id, instruction, at: Date.now() })
      setInstruction('')
      setStartUrl('')
      setFields('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="task-form" onSubmit={handleSubmit}>
      <span className="form-section-label">新任務</span>

      <div className="field">
        <label className="field-label">指示</label>
        <textarea
          required
          rows={3}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="例：抓 quotes.toscrape.com 前 3 則名言與作者"
        />
      </div>

      <div className="field">
        <label className="field-label">起始網址（可選）</label>
        <input
          type="url"
          value={startUrl}
          onChange={(e) => setStartUrl(e.target.value)}
          placeholder="https://..."
        />
      </div>

      <div className="field">
        <label className="field-label">抽取欄位（逗號分隔，可選）</label>
        <input
          type="text"
          value={fields}
          onChange={(e) => setFields(e.target.value)}
          placeholder="quote, author"
        />
      </div>

      <div className="field">
        <label className="field-label">遇登入/驗證時</label>
        <select value={policy} onChange={(e) => setPolicy(e.target.value)}>
          <option value="ai_then_human">AI 先試，卡住再交給我</option>
          <option value="human_first">一遇到就交給我</option>
          <option value="ai_only">全自動（不找我）</option>
        </select>
      </div>

      <button type="submit" className="btn-primary btn-full" disabled={busy}>
        {busy ? '提交中…' : '提交任務'}
      </button>

      {error && <p className="error">{error}</p>}
    </form>
  )
}
