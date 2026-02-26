import { useEffect, useState, useRef } from 'react'
import { getAnalysisStatus } from '../api'

interface Props {
  sessionId: string
  onComplete: () => void
}

function estimateProgress(message: string): number {
  const lower = message.toLowerCase()
  if (lower.includes('initializ')) return 5
  if (lower.includes('uploading')) return 15
  if (lower.includes('reading') || lower.includes('parsing')) return 30
  if (lower.includes('analyzing') || lower.includes('pricing') || lower.includes('contract structure')) return 55
  if (lower.includes('benchmark') || lower.includes('comparing')) return 72
  if (lower.includes('recommendation') || lower.includes('generating')) return 87
  if (lower.includes('complete')) return 100
  return 10
}

export default function AnalysisProgress({ sessionId, onComplete }: Props) {
  const [statusMessage, setStatusMessage] = useState('Initializing...')
  const [progress, setProgress] = useState(5)
  const [error, setError] = useState<string | null>(null)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    let done = false

    const poll = async () => {
      if (done) return
      try {
        const data = await getAnalysisStatus(sessionId)
        setStatusMessage(data.status_message)
        const estimated = estimateProgress(data.status_message)
        setProgress(estimated)

        if (data.status === 'complete') {
          done = true
          setProgress(100)
          setTimeout(() => onCompleteRef.current(), 700)
          return
        }

        if (data.status === 'error') {
          done = true
          setError(data.error_message ?? 'Analysis failed. Please try again.')
          return
        }
      } catch {
        // Network hiccup — keep polling
      }

      if (!done) setTimeout(poll, 3000)
    }

    const timer = setTimeout(poll, 1000)
    return () => {
      done = true
      clearTimeout(timer)
    }
  }, [sessionId])

  if (error) {
    return (
      <div className="progress-section">
        <div className="progress-card error-card">
          <div className="error-icon">⚠️</div>
          <h2 className="progress-title">Analysis Failed</h2>
          <p className="error-message">{error}</p>
          <button className="btn btn-primary" onClick={() => window.location.reload()}>
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="progress-section">
      <div className="progress-card">
        <div className="spinner-wrap">
          <div className="spinner" />
        </div>

        <h2 className="progress-title">Analyzing Your Contract</h2>
        <p className="progress-message">{statusMessage}</p>

        <div className="progress-bar-wrap">
          <div className="progress-bar" style={{ width: `${progress}%` }} />
        </div>
        <p className="progress-pct">{progress}%</p>

        <div className="progress-info">
          <p>
            Claude is performing deep analysis of your PBM contract — extracting all pricing
            terms, identifying cost risk areas, and comparing to current market benchmarks.
          </p>
          <p>This typically takes 30–90 seconds depending on contract length.</p>
        </div>
      </div>
    </div>
  )
}
