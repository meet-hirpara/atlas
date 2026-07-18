import { apiFetch } from './utils/apiFetch'
export interface UploadedDocument {
  id: string
  session_id: string
  filename: string
  file_size: number
  page_count: number
  chunk_count: number
  status: 'pending' | 'processing' | 'ready' | 'failed'
  error_message: string
  created_at: string
  processed_at: string | null
}

export async function fetchDocuments(sessionId: string): Promise<UploadedDocument[]> {
  const res = await apiFetch(`/api/documents/${sessionId}`)
  if (!res.ok) throw new Error('Failed to fetch documents')
  return res.json()
}

export async function uploadDocuments(
  sessionId: string,
  files: File[],
  ocrModel: string = 'auto',
): Promise<UploadedDocument[]> {
  const form = new FormData()
  form.append('session_id', sessionId)
  form.append('ocr_model', ocrModel)
  for (const file of files) {
    form.append('files', file)
  }
  const res = await apiFetch('/api/documents/upload', {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Upload failed')
  }
  return res.json()
}

export function getDocumentFileUrl(docId: string): string {
  return `/api/documents/file/${docId}`
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await apiFetch(`/api/documents/${docId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete document')
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
