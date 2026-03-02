import { useState, useCallback } from 'react'
import { uploadContract, extractErrorMessage } from '../api'

interface Props {
  onSuccess: (sessionId: string) => void
}

const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'doc']
const MAX_SIZE_MB = 50

export default function FileUpload({ onSuccess }: Props) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const validateAndSetFile = useCallback((f: File) => {
    setError(null)
    const ext = f.name.toLowerCase().split('.').pop() ?? ''
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError('Please upload a PDF or DOCX file.')
      return
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File size must not exceed ${MAX_SIZE_MB}MB.`)
      return
    }
    if (f.size === 0) {
      setError('The selected file is empty.')
      return
    }
    setFile(f)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const dropped = e.dataTransfer.files[0]
      if (dropped) validateAndSetFile(dropped)
    },
    [validateAndSetFile],
  )

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) validateAndSetFile(f)
    e.target.value = ''
  }

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const { session_id } = await uploadContract(file)
      onSuccess(session_id)
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Upload failed. Please try again.'))
      setLoading(false)
    }
  }

  const openFilePicker = () => document.getElementById('pbm-file-input')?.click()

  return (
    <div className="upload-section">
      <div className="upload-card">
        <div className="upload-accent" />
        <div className="upload-card-inner">
        <div className="upload-header">
          <h2>Upload PBM Contract</h2>
          <p>
            Upload your Pharmacy Benefit Manager contract for AI-powered analysis. We'll identify
            pricing issues, risk areas, and negotiation opportunities — in seconds.
          </p>
        </div>

        <div
          className={`upload-zone${dragging ? ' drag-over' : ''}${file ? ' has-file' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !file && openFilePicker()}
          role={file ? undefined : 'button'}
          tabIndex={file ? undefined : 0}
          aria-label={file ? undefined : 'Upload a PBM contract file'}
          onKeyDown={(e) => {
            if (!file && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault()
              openFilePicker()
            }
          }}
        >
          {file ? (
            <div className="file-selected">
              <div className="file-icon" aria-hidden="true">
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="#1e3a5f" strokeWidth="1.5" fill="#e8f0fe"/>
                  <polyline points="14,2 14,8 20,8" stroke="#1e3a5f" strokeWidth="1.5" fill="none"/>
                </svg>
              </div>
              <div className="file-meta">
                <span className="file-name">{file.name}</span>
                <span className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              <button
                className="file-remove"
                title="Remove file"
                aria-label={`Remove ${file.name}`}
                onClick={(e) => {
                  e.stopPropagation()
                  setFile(null)
                  setError(null)
                }}
              >
                ×
              </button>
            </div>
          ) : (
            <>
              <div className="upload-icon" aria-hidden="true">
                <svg width="42" height="42" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  <polyline points="17,8 12,3 7,8" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  <line x1="12" y1="3" x2="12" y2="15" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <p className="upload-heading">Drop your PBM contract here</p>
              <p className="upload-subtext">PDF or DOCX &nbsp;·&nbsp; Max {MAX_SIZE_MB}MB</p>
              <div className="upload-divider">
                <span>or</span>
              </div>
              <button
                className="browse-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  openFilePicker()
                }}
              >
                Browse Files
              </button>
            </>
          )}
        </div>

        <input
          id="pbm-file-input"
          type="file"
          accept=".pdf,.docx,.doc"
          onChange={handleFileInput}
          style={{ display: 'none' }}
          aria-label="Select a PBM contract file"
        />

        {error && <div className="upload-error" role="alert">{error}</div>}

        <button
          className="btn btn-primary btn-full"
          onClick={handleSubmit}
          disabled={!file || loading}
        >
          {loading ? (
            <>
              <span className="btn-spinner" aria-hidden="true" /> Uploading...
            </>
          ) : (
            'Analyze Contract'
          )}
        </button>

        <div className="upload-footer">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{display:'inline', verticalAlign:'middle', marginRight: 4}}>
            <rect x="3" y="11" width="18" height="11" rx="2" stroke="#64748b" strokeWidth="1.5"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Your contract is processed securely and never stored permanently.
        </div>
        </div>
      </div>
    </div>
  )
}
