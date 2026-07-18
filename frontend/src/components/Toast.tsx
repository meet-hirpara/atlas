import { useEffect } from 'react'
import { Check } from 'lucide-react'

export interface ToastItem {
  id: number
  message: string
}

interface Props {
  toasts: ToastItem[]
  onDismiss: (id: number) => void
}

function ToastBubble({
  toast,
  onDismiss,
}: {
  toast: ToastItem
  onDismiss: (id: number) => void
}) {
  useEffect(() => {
    const t = window.setTimeout(() => onDismiss(toast.id), 2600)
    return () => window.clearTimeout(t)
  }, [toast.id, onDismiss])

  return (
    <div className="atlas-toast" role="status">
      <span className="atlas-toast-icon" aria-hidden>
        <Check size={14} strokeWidth={2.5} />
      </span>
      <span>{toast.message}</span>
    </div>
  )
}

export default function ToastStack({ toasts, onDismiss }: Props) {
  if (toasts.length === 0) return null
  return (
    <div className="atlas-toast-stack" aria-live="polite" aria-relevant="additions">
      {toasts.map((t) => (
        <ToastBubble key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

let toastSeq = 0

export function nextToastId() {
  toastSeq += 1
  return toastSeq
}
