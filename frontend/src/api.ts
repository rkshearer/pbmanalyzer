import axios from 'axios'
import type { AnalysisStatus, AnalysisReport, KnowledgeStatus } from './types'

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
})

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
