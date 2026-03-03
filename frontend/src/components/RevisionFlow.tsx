import { useState } from 'react'
import FileUpload from './FileUpload'
import AnalysisProgress from './AnalysisProgress'
import RevisionCompareView from './RevisionCompareView'
import type { RevisionCompareData } from '../types'
import { getRevisionComparison } from '../api'

type Step = 'upload' | 'analyzing' | 'result' | 'error'

interface Props {
  originalSessionId: string
  onBack: () => void
}

export default function RevisionFlow({ originalSessionId, onBack }: Props) {
  const [step, setStep] = useState<Step>('upload')
  const [revisedSessionId, setRevisedSessionId] = useState('')
  const [compareData, setCompareData] = useState<RevisionCompareData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleUploadSuccess = (sessionId: string) => {
    setRevisedSessionId(sessionId)
    setStep('analyzing')
  }

  const handleAnalysisComplete = async () => {
    try {
      const data = await getRevisionComparison(originalSessionId, revisedSessionId)
      setCompareData(data)
      setStep('result')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      setError(`Could not load comparison: ${msg}`)
      setStep('error')
    }
  }

  if (step === 'result' && compareData) {
    return <RevisionCompareView data={compareData} onBack={onBack} />
  }

  if (step === 'error') {
    return (
      <div className="revision-error-page">
        <div className="revision-error-card">
          <div className="revision-error-icon">⚠️</div>
          <h3>Could not load comparison</h3>
          <p>{error}</p>
          <div className="revision-error-actions">
            <button className="btn btn-primary" onClick={() => { setStep('upload'); setError(null) }}>
              Try Again
            </button>
            <button className="btn btn-sm btn-secondary" onClick={onBack}>
              Back to Report
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="revision-flow">
      {/* Page header */}
      <div className="revision-flow-header">
        <button className="btn btn-sm btn-secondary" onClick={onBack}>
          ← Back to Report
        </button>
        <div>
          <h2 className="revision-flow-title">Upload Revised Contract</h2>
          <p className="revision-flow-subtitle">
            {step === 'upload'
              ? 'Upload the renegotiated contract to generate a before/after comparison.'
              : 'Analyzing the revised contract terms…'}
          </p>
        </div>
      </div>

      {/* Progress indicator */}
      <div className="revision-steps-row">
        <div className={`revision-step ${step === 'upload' ? 'active' : step === 'analyzing' || step === 'result' ? 'done' : ''}`}>
          <span className="revision-step-circle">{step === 'analyzing' || step === 'result' ? '✓' : '1'}</span>
          Upload Revised Contract
        </div>
        <div className="revision-step-connector" />
        <div className={`revision-step ${step === 'analyzing' ? 'active' : step === 'result' ? 'done' : ''}`}>
          <span className="revision-step-circle">{step === 'result' ? '✓' : '2'}</span>
          AI Analysis
        </div>
        <div className="revision-step-connector" />
        <div className={`revision-step ${step === 'result' ? 'active' : ''}`}>
          <span className="revision-step-circle">3</span>
          Before/After Report
        </div>
      </div>

      {/* Content */}
      {step === 'upload' && (
        <FileUpload onSuccess={handleUploadSuccess} />
      )}

      {step === 'analyzing' && revisedSessionId && (
        <AnalysisProgress
          sessionId={revisedSessionId}
          onComplete={handleAnalysisComplete}
        />
      )}
    </div>
  )
}
