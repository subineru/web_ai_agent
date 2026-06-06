import { useState } from 'react'
import TaskForm from './components/TaskForm.jsx'
import TaskList from './components/TaskList.jsx'
import TaskDetail from './components/TaskDetail.jsx'

const STORAGE_KEY = 'wagent.jobs'

function loadJobs() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

export default function App() {
  const [jobs, setJobs] = useState(loadJobs)
  const [selected, setSelected] = useState(null)

  function addJob(entry) {
    const next = [entry, ...jobs.filter((j) => j.jobId !== entry.jobId)]
    setJobs(next)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setSelected(entry.jobId)
  }

  function handleFollowup(newJobId, message) {
    addJob({ jobId: newJobId, instruction: message, at: Date.now() })
  }

  function deleteJob(jobId) {
    const next = jobs.filter((j) => j.jobId !== jobId)
    setJobs(next)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    if (selected === jobId) setSelected(null)
  }

  const selectedJob = jobs.find((j) => j.jobId === selected)

  return (
    <div className="app-shell">
      {/* ── Sidebar ─────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">W</div>
          <div>
            <span className="brand-name">wagent</span>
            <span className="brand-sub">瀏覽器自動化 Agent</span>
          </div>
        </div>
        <div className="sidebar-scroll">
          <TaskForm onSubmitted={addJob} />
          <TaskList jobs={jobs} selected={selected} onSelect={setSelected} onDelete={deleteJob} />
        </div>
      </aside>

      {/* ── Main panel ──────────────────────────────── */}
      <main className="main-panel">
        {selected ? (
          <TaskDetail
            key={selected}
            jobId={selected}
            instruction={selectedJob?.instruction}
            onFollowup={handleFollowup}
          />
        ) : (
          <div className="main-empty">
            <span className="empty-icon">⌘</span>
            <p>從左側提交任務或選擇一個既有任務<br />以查看即時執行進度。</p>
          </div>
        )}
      </main>
    </div>
  )
}
