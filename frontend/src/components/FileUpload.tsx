import { useState, useCallback } from 'react'
import { uploadContract } from '../api'

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
      const msg =
        err instanceof Error && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setError(msg ?? 'Upload failed. Please try again.')
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
        >
          {file ? (
            <div className="file-selected">
              <div className="file-icon">📄</div>
              <div className="file-meta">
                <span className="file-name">{file.name}</span>
                <span className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              <button
                className="file-remove"
                title="Remove file"
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
              <div className="upload-icon">📁</div>
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
        />

        {error && <div className="upload-error">{error}</div>}

        <button
          className="btn btn-primary btn-full"
          onClick={handleSubmit}
          disabled={!file || loading}
        >
          {loading ? (
            <>
              <span className="btn-spinner" /> Uploading...
            </>
          ) : (
            'Analyze Contract'
          )}
        </button>

        <div className="upload-footer">
          🔒 Your contract is processed securely and never stored permanently.
        </div>
        </div>
      </div>
    </div>
  )
}
