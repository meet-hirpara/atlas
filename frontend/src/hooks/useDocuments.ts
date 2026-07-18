import { useState, useEffect, useCallback, useRef } from 'react'
import {
  fetchDocuments,
  uploadDocuments,
  deleteDocument,
  type UploadedDocument,
} from '../documents'

export function useDocuments(sessionId: string | null) {
  const [documents, setDocuments] = useState<UploadedDocument[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    if (!sessionId) {
      setDocuments([])
      return
    }
    try {
      const docs = await fetchDocuments(sessionId)
      setDocuments(docs)
    } catch (e) {
      console.error(e)
    }
  }, [sessionId])

  useEffect(() => {
    refresh()
  }, [refresh])

  const hasProcessing = documents.some(
    (d) => d.status === 'pending' || d.status === 'processing',
  )

  useEffect(() => {
    if (hasProcessing && sessionId) {
      pollRef.current = setInterval(refresh, 2000)
    } else if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [hasProcessing, sessionId, refresh])

  const upload = async (files: FileList | File[], overrideSessionId?: string, ocrModel = 'auto') => {
    const sid = overrideSessionId || sessionId
    if (!sid) throw new Error('Start a chat first')
    const pdfFiles = Array.from(files).filter((f) =>
      f.name.toLowerCase().endsWith('.pdf'),
    )
    if (!pdfFiles.length) throw new Error('Only PDF files are supported')

    setUploading(true)
    setError(null)
    try {
      const added = await uploadDocuments(sid, pdfFiles, ocrModel)
      setDocuments((prev) => [...added, ...prev])
      refresh()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      setError(msg)
      throw e
    } finally {
      setUploading(false)
    }
  }

  const remove = async (docId: string) => {
    try {
      await deleteDocument(docId)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
    } catch (e) {
      console.error(e)
      await refresh()
      throw e
    }
  }

  const readyCount = documents.filter((d) => d.status === 'ready').length

  return {
    documents,
    uploading,
    error,
    upload,
    remove,
    refresh,
    readyCount,
    hasProcessing,
  }
}
