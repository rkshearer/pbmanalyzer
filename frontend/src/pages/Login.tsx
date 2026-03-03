import { useEffect, useState } from 'react'
import { authLogin, authRegister, authForgotPassword, authResetPassword, setStoredToken } from '../api'
import type { AuthUser } from '../types'

interface Props {
  onLogin: (user: AuthUser) => void
}

type Mode = 'login' | 'register' | 'forgot' | 'reset'

export default function Login({ onLogin }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // On mount: detect ?reset_token= in URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('reset_token')
    if (token) {
      setResetToken(token)
      setMode('reset')
      // Clean the URL
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessMsg(null)

    if (mode === 'forgot') {
      if (!email.trim()) {
        setError('Email is required.')
        return
      }
      setLoading(true)
      try {
        await authForgotPassword(email)
        setSuccessMsg('If an account exists with that email, you\'ll receive a password reset link shortly.')
      } catch {
        setSuccessMsg('If an account exists with that email, you\'ll receive a password reset link shortly.')
      }
      setLoading(false)
      return
    }

    if (mode === 'reset') {
      if (!password.trim()) {
        setError('Password is required.')
        return
      }
      if (password.length < 6) {
        setError('Password must be at least 6 characters.')
        return
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match.')
        return
      }
      setLoading(true)
      try {
        const res = await authResetPassword(resetToken, password)
        setStoredToken(res.token)
        onLogin(res.user)
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(axiosErr.response?.data?.detail ?? 'Invalid or expired reset link. Please request a new one.')
        setLoading(false)
      }
      return
    }

    // Login / Register
    if (!email.trim() || !password.trim()) {
      setError('Email and password are required.')
      return
    }
    if (mode === 'register' && (!firstName.trim() || !lastName.trim())) {
      setError('First and last name are required.')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }

    setLoading(true)
    try {
      const res =
        mode === 'login'
          ? await authLogin(email, password)
          : await authRegister(email, password, firstName, lastName)
      setStoredToken(res.token)
      onLogin(res.user)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail ?? 'Something went wrong. Please try again.')
      setLoading(false)
    }
  }

  const switchMode = (newMode: Mode) => {
    setMode(newMode)
    setError(null)
    setSuccessMsg(null)
  }

  const heading =
    mode === 'login' ? 'Sign In' :
    mode === 'register' ? 'Create Account' :
    mode === 'forgot' ? 'Reset Password' :
    'Set New Password'

  const submitLabel =
    mode === 'login' ? 'Sign In' :
    mode === 'register' ? 'Create Account' :
    mode === 'forgot' ? 'Send Reset Link' :
    'Set Password'

  const loadingLabel =
    mode === 'login' ? 'Signing in...' :
    mode === 'register' ? 'Creating account...' :
    mode === 'forgot' ? 'Sending...' :
    'Updating...'

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <span className="header-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="1" y="14" width="5" height="9" rx="1.5" fill="white" opacity="0.9"/>
              <rect x="9.5" y="8" width="5" height="15" rx="1.5" fill="white" opacity="0.9"/>
              <rect x="18" y="3" width="5" height="20" rx="1.5" fill="white" opacity="0.7"/>
              <path d="M3.5 14 L12 8 L20.5 3" stroke="#e8ad15" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
          <h1>PBM Contract Analyzer</h1>
          <p>AI-Powered Pharmacy Benefit Analysis</p>
        </div>

        <div className="login-body">
          <h2>{heading}</h2>

          {successMsg && <div className="login-success">{successMsg}</div>}

          {!successMsg && (
            <form onSubmit={handleSubmit} noValidate>
              {mode === 'register' && (
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label" htmlFor="firstName">First Name</label>
                    <input
                      id="firstName"
                      className="form-input"
                      type="text"
                      placeholder="Jane"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="lastName">Last Name</label>
                    <input
                      id="lastName"
                      className="form-input"
                      type="text"
                      placeholder="Smith"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                    />
                  </div>
                </div>
              )}

              {(mode === 'login' || mode === 'register' || mode === 'forgot') && (
                <div className="form-group">
                  <label className="form-label" htmlFor="email">Email</label>
                  <input
                    id="email"
                    className="form-input"
                    type="email"
                    placeholder="jane@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                </div>
              )}

              {(mode === 'login' || mode === 'register' || mode === 'reset') && (
                <div className="form-group">
                  <label className="form-label" htmlFor="password">
                    {mode === 'reset' ? 'New Password' : 'Password'}
                  </label>
                  <input
                    id="password"
                    className="form-input"
                    type="password"
                    placeholder="At least 6 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  />
                </div>
              )}

              {mode === 'reset' && (
                <div className="form-group">
                  <label className="form-label" htmlFor="confirmPassword">Confirm Password</label>
                  <input
                    id="confirmPassword"
                    className="form-input"
                    type="password"
                    placeholder="Re-enter your password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
              )}

              {mode === 'login' && (
                <div className="forgot-link">
                  <button type="button" onClick={() => switchMode('forgot')}>Forgot password?</button>
                </div>
              )}

              {error && <div className="server-error">{error}</div>}

              <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                {loading ? (
                  <><span className="btn-spinner" /> {loadingLabel}</>
                ) : (
                  submitLabel
                )}
              </button>
            </form>
          )}

          <p className="login-toggle">
            {(mode === 'login' || mode === 'forgot' || mode === 'reset') ? (
              <>
                {mode === 'forgot' && (
                  <><button type="button" onClick={() => switchMode('login')}>Back to sign in</button></>
                )}
                {mode === 'reset' && (
                  <><button type="button" onClick={() => switchMode('login')}>Back to sign in</button></>
                )}
                {mode === 'login' && (
                  <>Don't have an account?{' '}<button type="button" onClick={() => switchMode('register')}>Create one</button></>
                )}
              </>
            ) : (
              <>Already have an account?{' '}<button type="button" onClick={() => switchMode('login')}>Sign in</button></>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
