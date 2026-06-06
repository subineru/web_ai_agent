// 與後端 API 溝通的薄封裝。

export async function submitTask({ instruction, startUrl, fields, handoffPolicy }) {
  const resp = await fetch('/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      instruction,
      start_url: startUrl || null,
      fields: fields && fields.length ? fields : null,
      handoff_policy: handoffPolicy || null,
    }),
  })
  if (!resp.ok) {
    const detail = await resp.text()
    throw new Error(`提交失敗 (${resp.status}): ${detail}`)
  }
  return resp.json() // { task_id, job_id }
}

export async function getTask(jobId) {
  const resp = await fetch(`/tasks/${jobId}`)
  if (!resp.ok) throw new Error(`查詢失敗 (${resp.status})`)
  return resp.json()
}

async function postJob(jobId, action, body) {
  const resp = await fetch(`/jobs/${jobId}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null,
  })
  if (!resp.ok) {
    const detail = await resp.text()
    throw new Error(`${action} 失敗 (${resp.status}): ${detail}`)
  }
  return resp.json()
}

export const steerJob = (jobId, message) => postJob(jobId, 'steer', { message })
export const pauseJob = (jobId) => postJob(jobId, 'pause')
export const resumeJob = (jobId) => postJob(jobId, 'resume')
export const stopJob = (jobId) => postJob(jobId, 'stop')
export const answerClarification = (jobId, answer) => postJob(jobId, 'answer', { answer })
export const followUp = (jobId, message) => postJob(jobId, 'followup', { message })
export const submitFeedback = (jobId, rating, note) =>
  postJob(jobId, 'feedback', { rating, note })

// 安全提供帳密（依網域）。帳密只送後端、不留前端狀態。
export async function provideCredentials(siteDomain, fields) {
  const resp = await fetch('/credentials', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ site_domain: siteDomain, fields }),
  })
  if (!resp.ok) throw new Error(`提供帳密失敗 (${resp.status})`)
  return resp.json()
}

// 訂閱 SSE 事件；回傳 EventSource 以便呼叫端關閉。
export function subscribeEvents(
  jobId,
  { onStatus, onStep, onThink, onDone, onReuse, onClarification, onError },
) {
  const es = new EventSource(`/tasks/${jobId}/events`)
  es.addEventListener('status', (e) => onStatus?.(JSON.parse(e.data)))
  es.addEventListener('step', (e) => onStep?.(JSON.parse(e.data)))
  es.addEventListener('think', (e) => onThink?.(JSON.parse(e.data)))  // C1
  es.addEventListener('reuse', (e) => onReuse?.(JSON.parse(e.data)))
  es.addEventListener('clarification', (e) => onClarification?.(JSON.parse(e.data)))
  es.addEventListener('done', (e) => {
    onDone?.(JSON.parse(e.data))
    es.close()
  })
  es.onerror = () => onError?.()
  return es
}

// C3: 取得 artifact 下載 URL。
export function artifactUrl(jobId, filename) {
  return `/jobs/${jobId}/artifacts/${encodeURIComponent(filename)}`
}
