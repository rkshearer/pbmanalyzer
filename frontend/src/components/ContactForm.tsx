import { useState } from 'react'
import { submitContactForm, type ContactFormData } from '../api'
import type { AnalysisReport } from '../types'

interface Props {
  sessionId: string
  onSubmit: (analysis: AnalysisReport, downloadUrl: string) => void
}

type FormErrors = Partial<Record<keyof ContactFormData, string>>

const EMPTY_FORM: ContactFormData = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  company: '',
}

function validate(form: ContactFormData): FormErrors {
  const errors: FormErrors = {}
  if (!form.first_name.trim()) errors.first_name = 'Required'
  if (!form.last_name.trim()) errors.last_name = 'Required'
  if (!form.email.trim()) {
    errors.email = 'Required'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = 'Enter a valid email address'
  }
  if (!form.phone.trim()) errors.phone = 'Required'
  if (!form.company.trim()) errors.company = 'Required'
  return errors
}

export default function ContactForm({ sessionId, onSubmit }: Props) {
  const [form, setForm] = useState<ContactFormData>(EMPTY_FORM)
  const [errors, setErrors] = useState<FormErrors>({})
  const [loading, setLoading] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const handleChange = (field: keyof ContactFormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validationErrors = validate(form)
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      return
    }
    setLoading(true)
    setServerError(null)
    try {
      const result = await submitContactForm(sessionId, form)
      onSubmit(result.analysis, result.download_url)
    } catch (err: unknown) {
      const msg =
        err instanceof Error && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined
      setServerError(msg ?? 'Something went wrong. Please try again.')
      setLoading(false)
    }
  }

  const field = (
    id: keyof ContactFormData,
    label: string,
    type: string = 'text',
    placeholder: string = '',
  ) => (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>
        {label} *
      </label>
      <input
        id={id}
        className={`form-input${errors[id] ? ' error' : ''}`}
        type={type}
        placeholder={placeholder}
        value={form[id]}
        onChange={(e) => handleChange(id, e.target.value)}
        autoComplete={id === 'email' ? 'email' : id === 'phone' ? 'tel' : 'on'}
      />
      {errors[id] && <span className="form-error">{errors[id]}</span>}
    </div>
  )

  return (
    <div className="contact-section">
      <div className="contact-card">
        <div className="contact-accent" />
        <div className="contact-inner">
        <div className="contact-header">
          <div className="success-badge">✓ Analysis Complete</div>
          <h2 className="contact-title">Get Your Full Report</h2>
          <p className="contact-subtitle">
            Your PBM contract analysis is ready. Enter your contact information to access the
            complete report and download a professional PDF summary.
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-row">
            {field('first_name', 'First Name', 'text', 'Jane')}
            {field('last_name', 'Last Name', 'text', 'Smith')}
          </div>
          {field('email', 'Work Email', 'email', 'jane@company.com')}
          {field('phone', 'Phone Number', 'tel', '(555) 555-5555')}
          {field('company', 'Company', 'text', 'Acme Benefits Consulting')}

          {serverError && <div className="server-error">{serverError}</div>}

          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
            {loading ? (
              <>
                <span className="btn-spinner" /> Generating Report...
              </>
            ) : (
              'View Full Report →'
            )}
          </button>
        </form>
        </div>
      </div>
    </div>
  )
}
