import { useState, useEffect, useRef } from 'react'
import { API_BASE_URL, getBrokerProfile, saveBrokerProfile, uploadBrokerLogo } from '../api'

interface Props {
  onClose: () => void
}

export default function BrokerSettings({ onClose }: Props) {
  const [form, setForm] = useState({ broker_name: '', firm_name: '', email: '', phone: '' })
  const [logoUrl, setLogoUrl] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [logoUploading, setLogoUploading] = useState(false)
  const [savedOk, setSavedOk] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  // Cache-busting timestamp for logo preview refreshes
  const [logoTs, setLogoTs] = useState(Date.now())

  useEffect(() => {
    getBrokerProfile()
      .then((p) => {
        setForm({
          broker_name: p.broker_name ?? '',
          firm_name: p.firm_name ?? '',
          email: p.email ?? '',
          phone: p.phone ?? '',
        })
        setLogoUrl(p.logo_url)
      })
      .catch(() => {})
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await saveBrokerProfile(form)
      setSavedOk(true)
      setTimeout(() => setSavedOk(false), 2500)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLogoUploading(true)
    setError(null)
    try {
      const data = await uploadBrokerLogo(file)
      setLogoUrl(data.logo_url)
      setLogoTs(Date.now())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Logo upload failed')
    } finally {
      setLogoUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }))

  return (
    <div
      className="modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="modal-card">
        <div className="modal-header">
          <div>
            <h2 className="modal-title">Broker Profile</h2>
            <p className="modal-subtitle">
              Your firm's branding appears on the cover page and header of every generated PDF report.
            </p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="modal-body">
          <div className="broker-form-row">
            <div className="form-group">
              <label className="form-label">Firm / Company Name</label>
              <input
                className="form-input"
                value={form.firm_name}
                onChange={set('firm_name')}
                placeholder="Smith Benefits Consulting"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Your Name</label>
              <input
                className="form-input"
                value={form.broker_name}
                onChange={set('broker_name')}
                placeholder="Jane Smith"
              />
            </div>
          </div>

          <div className="broker-form-row">
            <div className="form-group">
              <label className="form-label">Email</label>
              <input
                className="form-input"
                type="email"
                value={form.email}
                onChange={set('email')}
                placeholder="jane@smithbenefits.com"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Phone</label>
              <input
                className="form-input"
                value={form.phone}
                onChange={set('phone')}
                placeholder="(555) 123-4567"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Company Logo</label>
            <div className="logo-upload-area">
              {logoUrl && (
                <img
                  src={`${API_BASE_URL}${logoUrl}?t=${logoTs}`}
                  alt="Broker logo"
                  className="logo-preview"
                />
              )}
              <div className="logo-upload-controls">
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => fileRef.current?.click()}
                  disabled={logoUploading}
                >
                  {logoUploading ? 'Uploading…' : logoUrl ? '↑ Replace Logo' : '↑ Upload Logo'}
                </button>
                <span className="logo-hint">PNG or JPG · Shown on PDF cover page</span>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".png,.jpg,.jpeg,.webp"
                style={{ display: 'none' }}
                onChange={handleLogoUpload}
              />
            </div>
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="broker-preview-note">
            When set, your firm name appears in the PDF header and footer. Your contact info
            and logo appear in a "Presented by" panel on the cover page.
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : savedOk ? '✓ Saved!' : 'Save Profile'}
          </button>
        </div>
      </div>
    </div>
  )
}
