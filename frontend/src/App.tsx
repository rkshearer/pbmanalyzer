import { useState, Fragment } from 'react'
import FileUpload from './components/FileUpload'
import AnalysisProgress from './components/AnalysisProgress'
import ContactForm from './components/ContactForm'
import ReportView from './components/ReportView'
import KnowledgeStatus from './components/KnowledgeStatus'
import CompareView from './components/CompareView'
import RevisionFlow from './components/RevisionFlow'
import History from './pages/History'
import type { AnalysisReport } from './types'

type Step = 1 | 2 | 3 | 4
type Page = 'main' | 'history' | 'compare' | 'revision'

const STEP_LABELS: Record<number, string> = {
  1: 'Upload Contract',
  2: 'Analysis',
  3: 'Contact Info',
  4: 'Your Report',
}

export default function App() {
  const [page, setPage] = useState<Page>('main')
  const [step, setStep] = useState<Step>(1)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisReport | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [compareSessionId, setCompareSessionId] = useState<string>('')

  const handleOpenReport = (sid: string, a: AnalysisReport, url: string | null) => {
    setSessionId(sid)
    setAnalysis(a)
    setDownloadUrl(url)
    setStep(4)
    setPage('main')
  }

  const handleCompare = (sid: string) => {
    setCompareSessionId(sid)
    setPage('compare')
  }

  const handleStartRevision = (sid: string) => {
    setSessionId(sid)
    setPage('revision')
  }

  return (
    <div className="app">
      <header className="header">
        <div className="container">
          <div className="header-inner">
            <div className="header-brand">
              <span className="header-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect x="1" y="14" width="5" height="9" rx="1.5" fill="white" opacity="0.9"/>
                  <rect x="9.5" y="8" width="5" height="15" rx="1.5" fill="white" opacity="0.9"/>
                  <rect x="18" y="3" width="5" height="20" rx="1.5" fill="white" opacity="0.7"/>
                  <path d="M3.5 14 L12 8 L20.5 3" stroke="#e8ad15" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </span>
              <div>
                <h1 className="header-title">PBM Contract Analyzer</h1>
                <p className="header-subtitle">AI-Powered Pharmacy Benefit Analysis</p>
              </div>
            </div>
            <div className="header-right">
              <nav className="header-nav">
                <button
                  className={`header-nav-link${page === 'main' ? ' active' : ''}`}
                  onClick={() => setPage('main')}
                >
                  Analyzer
                </button>
                <button
                  className={`header-nav-link${page === 'history' ? ' active' : ''}`}
                  onClick={() => setPage('history')}
                >
                  History
                </button>
              </nav>
              <KnowledgeStatus />
            </div>
          </div>
        </div>
      </header>

      <main className="main">
        <div className="container">

          {/* History page */}
          {page === 'history' && (
            <div className="step-content wide">
              <History onOpenReport={handleOpenReport} onCompare={handleCompare} />
            </div>
          )}

          {/* Compare page */}
          {page === 'compare' && compareSessionId && (
            <div className="step-content wide">
              <CompareView
                sessionIdA={compareSessionId}
                onBack={() => setPage(step === 4 ? 'main' : 'history')}
              />
            </div>
          )}

          {/* Revision page */}
          {page === 'revision' && sessionId && (
            <div className="step-content wide">
              <RevisionFlow
                originalSessionId={sessionId}
                onBack={() => setPage('main')}
              />
            </div>
          )}

          {/* Main wizard */}
          {page === 'main' && (
            <>
              <div className="steps-bar">
                {[1, 2, 3, 4].map((s) => (
                  <Fragment key={s}>
                    <div className={`step-item${step === s ? ' active' : ''}${step > s ? ' done' : ''}`}>
                      <div className="step-circle">{step > s ? '✓' : s}</div>
                      <span className="step-text">{STEP_LABELS[s]}</span>
                    </div>
                    {s < 4 && <div className={`step-connector${step > s ? ' done' : ''}`} />}
                  </Fragment>
                ))}
              </div>

              <div className={`step-content${step === 4 ? ' wide' : ''}`}>
                {step === 1 && (
                  <FileUpload
                    onSuccess={(id) => {
                      setSessionId(id)
                      setStep(2)
                    }}
                  />
                )}

                {step === 2 && sessionId && (
                  <AnalysisProgress
                    sessionId={sessionId}
                    onComplete={() => setStep(3)}
                  />
                )}

                {step === 3 && sessionId && (
                  <ContactForm
                    sessionId={sessionId}
                    onSubmit={(a, url) => {
                      setAnalysis(a)
                      setDownloadUrl(url)
                      setStep(4)
                    }}
                  />
                )}

                {step === 4 && analysis && sessionId && (
                  <ReportView
                    analysis={analysis}
                    downloadUrl={downloadUrl}
                    sessionId={sessionId}
                    onCompare={handleCompare}
                    onStartRevision={handleStartRevision}
                  />
                )}
              </div>
            </>
          )}

        </div>
      </main>

      <footer className="footer">
        <div className="container">
          <p>© 2026 PBM Contract Analyzer · Powered by Claude AI · Confidential</p>
        </div>
      </footer>
    </div>
  )
}
