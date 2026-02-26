import { useState, useEffect } from 'react'
import { getKnowledgeStatus, triggerKnowledgeUpdate } from '../api'
import type { KnowledgeStatus as KStatus } from '../types'

function formatDate(iso: string): string {
  if (!iso || iso === 'Never') return 'Never'
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

export default function KnowledgeStatus() {
  const [status, setStatus] = useState<KStatus | null>(null)
  const [updating, setUpdating] = useState(false)
  const [justUpdated, setJustUpdated] = useState(false)

  useEffect(() => {
    getKnowledgeStatus()
      .then(setStatus)
      .catch(() => {/* backend may not be up yet */})
  }, [])

  const handleUpdate = async () => {
    setUpdating(true)
    try {
      await triggerKnowledgeUpdate()
      const newStatus = await getKnowledgeStatus()
      setStatus(newStatus)
      setJustUpdated(true)
      setTimeout(() => setJustUpdated(false), 3000)
    } catch {
      // silently fail
    } finally {
      setUpdating(false)
    }
  }

  return (
    <div className="knowledge-status">
      <div className="knowledge-info">
        <span className="knowledge-dot" title="AI knowledge is active" />
        <span className="knowledge-label">
          {justUpdated
            ? 'Knowledge updated!'
            : status
              ? `AI Knowledge: ${formatDate(status.last_updated)}`
              : 'AI Knowledge: Loading...'}
        </span>
        {status && status.analyses_count > 0 && (
          <span className="knowledge-meta">
            · {status.analyses_count} contract{status.analyses_count !== 1 ? 's' : ''} analyzed
          </span>
        )}
      </div>
      <button
        className="knowledge-refresh-btn"
        onClick={handleUpdate}
        disabled={updating}
        title="Fetch latest PBM rules and legislation from public sources"
      >
        {updating ? '↻ Updating...' : '↻ Refresh'}
      </button>
    </div>
  )
}
