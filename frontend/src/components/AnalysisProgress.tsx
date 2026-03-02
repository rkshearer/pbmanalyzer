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
  const [networkRetries, setNetworkRetries] = useState(0)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    let done = false
    let pollInterval = 2000
    const MAX_INTERVAL = 5000
    const MAX_NETWORK_RETRIES = 5

    const poll = async () => {
      if (done) return
      try {
        const data = await getAnalysisStatus(sessionId)
        setNetworkRetries(0)
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

        // Adaptive polling: slow down as analysis progresses
        if (estimated > 50) {
          pollInterval = Math.min(pollInterval + 500, MAX_INTERVAL)
        }
      } catch {
        setNetworkRetries((prev) => {
          const next = prev + 1
          if (next >= MAX_NETWORK_RETRIES) {
            done = true
            setError('Lost connection to the server. Please refresh the page and try again.')
          }
          return next
        })
      }

      if (!done) setTimeout(poll, pollInterval)
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
        <div className="progress-card error-card" role="alert">
          <div className="error-icon" aria-hidden="true">!</div>
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
      <div className="progress-card" role="status" aria-live="polite">
        <div className="spinner-wrap">
          <div className="spinner" aria-hidden="true" />
        </div>

        <h2 className="progress-title">Analyzing Your Contract</h2>
        <p className="progress-message">{statusMessage}</p>

        <div
          className="progress-bar-wrap"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Analysis progress: ${progress}%`}
        >
          <div className="progress-bar" style={{ width: `${progress}%` }} />
        </div>
        <p className="progress-pct">{progress}%</p>

        {networkRetries > 0 && (
          <p className="progress-retry-notice">
            Reconnecting to server... (attempt {networkRetries})
          </p>
        )}

        <div className="progress-info">
          <p>
            Claude is performing deep analysis of your PBM contract — extracting all pricing
            terms, identifying cost risk areas, and comparing to current market benchmarks.
          </p>
          <p>This typically takes 15–45 seconds depending on contract length.</p>
        </div>
      </div>
    </div>
  )
}
