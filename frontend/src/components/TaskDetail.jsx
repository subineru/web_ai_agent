import { useEffect, useRef, useState } from 'react'
import {
  answerClarification,
  artifactUrl,
  followUp,
  pauseJob,
  provideCredentials,
  resumeJob,
  steerJob,
  stopJob,
  submitFeedback,
  subscribeEvents,
} from '../api.js'

const TERMINAL = ['succeeded', 'partial', 'failed', 'closed']

const STATUS_LABEL = {
  connecting:       '連線中',
  running:          '執行中',
  paused:           '已暫停',
  waiting_for_user: '等待中',
  succeeded:        '已完成',
  partial:          '部分完成',
  failed:           '失敗',
  closed:           '已關閉',
}

export default function TaskDetail({ jobId, instruction, onFollowup }) {
  const [status, setStatus] = useState('connecting')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [actionErr, setActionErr] = useState(null)
  const [feedbackDone, setFeedbackDone] = useState(false)
  const [showCreds, setShowCreds] = useState(false)
  const [cred, setCred] = useState({ domain: '', user: '', pass: '' })
  const [artifacts, setArtifacts] = useState([])
  const endRef = useRef(null)

  // role: 'user' | 'agent' | 'think' | 'system'
  // kind: optional ('clarify' | 'result' | 'error')
  // extra: data object for think messages
  const add = (role, text, kind, extra) =>
    setMessages((prev) => [...prev, { role, text, kind, extra, id: prev.length }])

  useEffect(() => {
    setStatus('connecting')
    setMessages(instruction ? [{ role: 'user', text: instruction, id: 0 }] : [])
    setFeedbackDone(false)
    setShowCreds(false)
    setArtifacts([])

    const es = subscribeEvents(jobId, {
      onStatus:        (d) => setStatus(d.status),
      onStep:          (d) => add('agent', d.description),
      onThink:         (d) => add('think', null, null, d),   // C1
      onReuse:         (d) => add('system', `💡 重用了 ${d.count} 條在 ${d.domain} 的既有經驗`),
      onClarification: (d) => {
        setStatus('waiting_for_user')
        add('agent', `🙋 ${d.reason}`, 'clarify')
      },
      onDone: (d) => {
        setStatus(d.status)
        if (d.result) add('agent', d.result, 'result')
        if (d.error)  add('agent', `${d.error}`, 'error')
        if (d.artifacts?.length) setArtifacts(d.artifacts)  // C3
      },
      onError: () => {},
    })
    return () => es.close()
  }, [jobId, instruction])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' })
  }, [messages])

  const isRunning  = status === 'running'
  const isPaused   = status === 'paused'
  const isWaiting  = status === 'waiting_for_user'
  const isTerminal = TERMINAL.includes(status)

  async function act(fn) {
    setActionErr(null)
    try { await fn() } catch (e) { setActionErr(e.message) }
  }

  function send() {
    const text = input.trim()
    if (!text) return
    add('user', text)
    setInput('')
    if (isWaiting) {
      act(() => answerClarification(jobId, text))
    } else if (isRunning || isPaused) {
      act(() => steerJob(jobId, text))
    } else {
      act(async () => {
        const { job_id } = await followUp(jobId, text)
        onFollowup?.(job_id, text)
      })
    }
  }

  const placeholder = isWaiting
    ? '完成操作後在此說明（例：已登入）…'
    : isRunning || isPaused
      ? '即時轉向：送出新指示給執行中的 agent…'
      : '針對結果追問或要求下一步…'

  async function sendCreds() {
    await act(async () => {
      await provideCredentials(cred.domain.trim(), {
        x_user: cred.user,
        x_pass: cred.pass,
      })
      add('system', `🔒 已安全提供 ${cred.domain} 帳密（不進日誌；可追問請 AI 登入）`)
      setCred({ domain: '', user: '', pass: '' })
      setShowCreds(false)
    })
  }

  return (
    <div className="task-detail">

      {/* ── Header ─────────────────────────────────── */}
      <div className="task-header">
        <h2 className="task-title">{instruction || '對話'}</h2>
        <span className={`badge ${status}`}>
          {STATUS_LABEL[status] || status}
        </span>
      </div>

      {/* ── Chat ───────────────────────────────────── */}
      <div className="chat">
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role} ${m.kind || ''}`}>
            {m.role === 'think' ? (
              /* C1: collapsible reasoning bubble */
              <details className="think-bubble">
                <summary>
                  <span className="think-arrow">▶</span>
                  💭 推理過程
                </summary>
                <div className="think-content">
                  {m.extra?.next_goal && (
                    <div className="think-row">
                      <span className="think-label">下一步</span>
                      <span className="think-value">{m.extra.next_goal}</span>
                    </div>
                  )}
                  {m.extra?.evaluation && (
                    <div className="think-row">
                      <span className="think-label">評估</span>
                      <span className="think-value">{m.extra.evaluation}</span>
                    </div>
                  )}
                  {m.extra?.thought && (
                    <div className="think-row">
                      <span className="think-label">擴展思考</span>
                      <pre className="thought">{m.extra.thought}</pre>
                    </div>
                  )}
                </div>
              </details>
            ) : (
              <div className="msg-bubble">
                <pre>{m.text}</pre>
                {/* B5: export buttons on result messages */}
                {m.kind === 'result' && (
                  <div className="export-row">
                    <span className="export-label">匯出：</span>
                    {['txt', 'json', 'csv', 'xlsx'].map((fmt) => (
                      <a
                        key={fmt}
                        href={`/jobs/${jobId}/export/${fmt}`}
                        download
                        className="chip"
                      >
                        {fmt.toUpperCase()}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {!messages.length && (
          <p className="muted" style={{ fontSize: '13px', margin: '8px 0' }}>
            等待 agent 動作…
          </p>
        )}
        <div ref={endRef} />
      </div>

      {/* ── Footer ─────────────────────────────────── */}
      <div className="task-footer">

        {/* C3: browser-downloaded artifacts */}
        {artifacts.length > 0 && (
          <div className="artifacts">
            <h3>📎 下載產出檔案</h3>
            <ul>
              {artifacts.map((name) => (
                <li key={name}>
                  <a
                    href={artifactUrl(jobId, name)}
                    download={name}
                    className="artifact-link"
                  >
                    ↓ {name}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Execution controls */}
        {(isRunning || isPaused) && (
          <div className="steer-controls">
            {isPaused ? (
              <button onClick={() => act(() => resumeJob(jobId))}>▶ 繼續</button>
            ) : (
              <button onClick={() => act(() => pauseJob(jobId))}>⏸ 暫停</button>
            )}
            <button className="btn-danger" onClick={() => act(() => stopJob(jobId))}>
              ⏹ 停止
            </button>
          </div>
        )}

        {/* Credentials toggle */}
        {isWaiting && (
          <div className="creds-toggle">
            <button
              className="btn-sm btn-ghost"
              onClick={() => setShowCreds((s) => !s)}
            >
              🔑 提供帳密給 AI 登入
            </button>
          </div>
        )}

        {showCreds && (
          <div className="creds-box">
            <input
              placeholder="網域（如 site.com）"
              value={cred.domain}
              onChange={(e) => setCred({ ...cred, domain: e.target.value })}
            />
            <input
              placeholder="帳號"
              autoComplete="off"
              value={cred.user}
              onChange={(e) => setCred({ ...cred, user: e.target.value })}
            />
            <input
              type="password"
              placeholder="密碼"
              autoComplete="new-password"
              value={cred.pass}
              onChange={(e) => setCred({ ...cred, pass: e.target.value })}
            />
            <button
              className="btn-sm"
              onClick={sendCreds}
              disabled={!cred.domain.trim() || !cred.user}
            >
              安全送出
            </button>
            <p className="muted small">
              帳密僅送後端、不進 LLM 原值、不寫日誌。
            </p>
          </div>
        )}

        {/* Unified input */}
        {status !== 'closed' && (
          <div className="chat-input">
            <textarea
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send()
              }}
              placeholder={placeholder}
            />
            <button
              className="btn-primary"
              onClick={send}
              disabled={!input.trim()}
            >
              送出
            </button>
          </div>
        )}

        {/* Feedback */}
        {isTerminal && status !== 'closed' && !feedbackDone && (
          <div className="feedback-box">
            <span className="feedback-label">結果如何？</span>
            <div className="feedback-row">
              <button
                className="btn-sm"
                onClick={() => act(async () => { await submitFeedback(jobId, 'good'); setFeedbackDone(true) })}
              >
                👍 好
              </button>
              <button
                className="btn-sm"
                onClick={() => act(async () => { await submitFeedback(jobId, 'edited', '需修正'); setFeedbackDone(true) })}
              >
                ✏️ 需修正
              </button>
              <button
                className="btn-sm btn-danger"
                onClick={() => act(async () => { await submitFeedback(jobId, 'rejected', '重來'); setFeedbackDone(true) })}
              >
                👎 重來
              </button>
            </div>
          </div>
        )}

        {feedbackDone && (
          <p className="muted small" style={{ padding: '6px 22px' }}>
            已收到回饋，謝謝！
          </p>
        )}

        {actionErr && (
          <p className="error-msg">{actionErr}</p>
        )}
      </div>
    </div>
  )
}
