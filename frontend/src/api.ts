import axios, { type AxiosError } from 'axios'
import type { AnalysisStatus, AnalysisReport, KnowledgeStatus } from './types'

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
})

/**
 * Extract a user-friendly error message from an Axios error.
 */
export function extractErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const axiosErr = err as AxiosError<{ detail?: string }>
    if (axiosErr.response?.data?.detail) {
      return axiosErr.response.data.detail
    }
    if (axiosErr.code === 'ECONNABORTED') {
      return 'Request timed out. Please try again.'
    }
    if (!axiosErr.response) {
      return 'Unable to reach the server. Please check your connection.'
    }
    if (axiosErr.response.status === 429) {
      return 'Too many requests. Please wait a moment before trying again.'
    }
    if (axiosErr.response.status >= 500) {
      return 'Server error. Please try again in a few moments.'
    }
  }
  return fallback
}

/**
 * Retry wrapper with exponential backoff for transient failures.
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 2,
  baseDelay = 1000,
): Promise<T> {
  let lastError: unknown
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastError = err
      if (axios.isAxiosError(err)) {
        const status = err.response?.status
        // Don't retry client errors (4xx except 429) or 503 (misconfigured)
        if (status && ((status >= 400 && status < 500 && status !== 429) || status === 503)) {
          throw err
        }
      }
      if (attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, baseDelay * Math.pow(2, attempt)))
      }
    }
  }
  throw lastError
}

export async function uploadContract(file: File): Promise<{ session_id: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await withRetry(() =>
    api.post('/api/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  )
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
  const response = await withRetry(() => api.post(`/api/report/${sessionId}`, contact))
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
