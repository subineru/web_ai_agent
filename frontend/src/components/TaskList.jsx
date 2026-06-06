function fmt(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now - d
  if (diff < 60_000) return '剛剛'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export default function TaskList({ jobs, selected, onSelect, onDelete }) {
  return (
    <div className="task-list">
      <div className="list-section-label">
        <span>任務</span>
        {jobs.length > 0 && <span className="list-count">{jobs.length}</span>}
      </div>

      {jobs.length === 0 ? (
        <p className="no-jobs">尚無任務</p>
      ) : (
        <ul>
          {jobs.map((j) => (
            <li
              key={j.jobId}
              className={j.jobId === selected ? 'active' : ''}
              onClick={() => onSelect(j.jobId)}
            >
              <span className="instr">{j.instruction || '(無指示)'}</span>
              <div className="job-meta">
                <span className="jid">{j.jobId.slice(0, 8)}</span>
                <span className="at">{fmt(j.at)}</span>
                <button
                  className="job-delete"
                  title="從清單移除"
                  onClick={(e) => { e.stopPropagation(); onDelete?.(j.jobId) }}
                >×</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
