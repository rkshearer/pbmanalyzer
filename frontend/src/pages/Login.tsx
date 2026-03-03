import { useState } from 'react'
import { authLogin, authRegister, setStoredToken } from '../api'
import type { AuthUser } from '../types'

interface Props {
  onLogin: (user: AuthUser) => void
}

type Mode = 'login' | 'register'

export default function Login({ onLogin }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

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
          <h2>{mode === 'login' ? 'Sign In' : 'Create Account'}</h2>

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

            <div className="form-group">
              <label className="form-label" htmlFor="password">Password</label>
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

            {error && <div className="server-error">{error}</div>}

            <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
              {loading ? (
                <><span className="btn-spinner" /> {mode === 'login' ? 'Signing in...' : 'Creating account...'}</>
              ) : (
                mode === 'login' ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>

          <p className="login-toggle">
            {mode === 'login' ? (
              <>Don't have an account?{' '}<button type="button" onClick={() => { setMode('register'); setError(null) }}>Create one</button></>
            ) : (
              <>Already have an account?{' '}<button type="button" onClick={() => { setMode('login'); setError(null) }}>Sign in</button></>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
