import axios from 'axios'
import type { AnalysisStatus, AnalysisReport, KnowledgeStatus, AuthUser, AuthResponse } from './types'

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''

// ── Token helpers ────────────────────────────────────────────────────────────

const TOKEN_KEY = 'pbm_auth_token'

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// ── Axios instance + interceptors ────────────────────────────────────────────

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
})

// Attach Bearer token to every request
api.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401 response, clear token and dispatch logout event
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredToken()
      window.dispatchEvent(new Event('auth:logout'))
    }
    return Promise.reject(error)
  },
)

// ── Auth API functions ───────────────────────────────────────────────────────

export async function authRegister(
  email: string,
  password: string,
  first_name: string,
  last_name: string,
): Promise<AuthResponse> {
  const response = await api.post('/api/auth/register', { email, password, first_name, last_name })
  return response.data
}

export async function authLogin(email: string, password: string): Promise<AuthResponse> {
  const response = await api.post('/api/auth/login', { email, password })
  return response.data
}

export async function authMe(): Promise<AuthUser> {
  const response = await api.get('/api/auth/me')
  return response.data
}

export async function uploadContract(file: File): Promise<{ session_id: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/api/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function getAnalysisStatus(sessionId: string): Promise<AnalysisStatus> {
  const response = await api.get(`/api/status/${sessionId}`)
  return response.data
}

export interface ContactFormData {
  first_name: string
  last_name: string
  email: string
  phone: string
  company: string
}

export async function submitContactForm(
  sessionId: string,
  contact: ContactFormData,
): Promise<{ success: boolean; download_url: string; analysis: AnalysisReport }> {
  const response = await api.post(`/api/report/${sessionId}`, contact)
  return response.data
}

export async function getKnowledgeStatus(): Promise<KnowledgeStatus> {
  const response = await api.get('/api/knowledge/status')
  return response.data
}

export async function triggerKnowledgeUpdate(): Promise<{
  success: boolean
  updates_found: number
}> {
  const response = await api.post('/api/knowledge/update')
  return response.data
}

export async function getContractLibrary(
  page = 1,
  limit = 20,
): Promise<import('./types').ContractListResponse> {
  const response = await api.get('/api/library', { params: { page, limit } })
  return response.data
}

export async function getLibraryStats(): Promise<import('./types').LibraryStats> {
  const response = await api.get('/api/library/stats')
  return response.data
}

export async function getStoredAnalysis(
  sessionId: string,
): Promise<import('./types').StoredAnalysisResponse> {
  const response = await api.get(`/api/session/${sessionId}/analysis`)
  return response.data
}

export async function getCompareData(
  a: string,
  b: string,
): Promise<import('./types').CompareData> {
  const response = await api.get('/api/compare', { params: { a, b } })
  return response.data
}

export async function getRevisionComparison(
  originalId: string,
  revisedId: string,
): Promise<import('./types').RevisionCompareData> {
  const response = await api.get('/api/compare-revisions', {
    params: { original: originalId, revised: revisedId },
  })
  return response.data
}

/** Download the negotiation letter DOCX and trigger browser save. */
export async function downloadNegotiationLetter(sessionId: string): Promise<void> {
  const headers: Record<string, string> = {}
  const token = getStoredToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const response = await fetch(`${API_BASE_URL}/api/negotiate/${sessionId}`, {
    method: 'POST',
    headers,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || 'Failed to generate negotiation letter')
  }
  const disposition = response.headers.get('content-disposition') ?? ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : 'PBM_Negotiation_Letter.docx'
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── Broker Profile ──────────────────────────────────────────────────────────

export async function getBrokerProfile(): Promise<import('./types').BrokerProfile> {
  const response = await api.get('/api/broker')
  return response.data
}

export async function saveBrokerProfile(data: {
  broker_name: string
  firm_name: string
  email: string
  phone: string
}): Promise<void> {
  await api.post('/api/broker', data)
}

export async function uploadBrokerLogo(file: File): Promise<{ logo_url: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/api/broker/logo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

/** Download the RFP question bank XLSX and trigger browser save. */
export async function downloadRfpExport(sessionId: string): Promise<void> {
  const headers: Record<string, string> = {}
  const token = getStoredToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const response = await fetch(`${API_BASE_URL}/api/rfp/${sessionId}`, {
    method: 'POST',
    headers,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || 'Failed to generate RFP export')
  }
  const disposition = response.headers.get('content-disposition') ?? ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : 'PBM_RFP_Questions.xlsx'
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
