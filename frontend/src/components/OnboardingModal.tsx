import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { APP_NAME } from '../brand'
import LampLogo from './LampLogo'

const KEY = 'atlas-onboarding-done'

export type UseCase = 'freelance' | 'code' | 'research'

function onboardingKey(): string {
  try {
    const uid = localStorage.getItem('atlas-user')
    if (uid) {
      const parsed = JSON.parse(uid) as { id?: string }
      if (parsed?.id) return `${KEY}:${parsed.id}`
    }
  } catch {
    /* ignore */
  }
  return KEY
}

export function isOnboardingDone(): boolean {
  try {
    return localStorage.getItem(onboardingKey()) === '1' || localStorage.getItem(KEY) === '1'
  } catch {
    return true
  }
}

export function markOnboardingDone(useCase?: UseCase) {
  try {
    localStorage.setItem(onboardingKey(), '1')
    if (useCase) localStorage.setItem('atlas-use-case', useCase)
  } catch {
    // ignore
  }
}

export function getSavedUseCase(): UseCase | null {
  try {
    const v = localStorage.getItem('atlas-use-case')
    if (v === 'freelance' || v === 'code' || v === 'research') return v
  } catch {
    // ignore
  }
  return null
}

interface Props {
  onClose: (useCase: UseCase) => void
  onOpenIntegrations?: () => void
}

const OPTIONS: { id: UseCase; title: string; blurb: string }[] = [
  { id: 'freelance', title: 'Freelance', blurb: 'Jobs, proposals, Upwork & client work' },
  { id: 'code', title: 'Code & build', blurb: 'Repos, multi-file projects, diagrams' },
  { id: 'research', title: 'Research', blurb: 'Deep reports & scheduled topics' },
]

export default function OnboardingModal({ onClose, onOpenIntegrations }: Props) {
  const [useCase, setUseCase] = useState<UseCase>('freelance')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        markOnboardingDone(useCase)
        onClose(useCase)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, useCase])

  const finish = () => {
    markOnboardingDone(useCase)
    onClose(useCase)
  }

  return (
    <div className="onboarding-overlay" role="dialog" aria-modal="true" aria-label={`Welcome to ${APP_NAME}`}>
      <div className="onboarding-modal">
        <button type="button" className="onboarding-close" onClick={finish} aria-label="Skip">
          <X size={16} />
        </button>
        <div className="onboarding-brand-row">
          <LampLogo size={28} />
        </div>
        <h2 className="onboarding-title">Welcome to {APP_NAME}</h2>
        <p className="onboarding-sub">
          Tell us what you&apos;re here for — we&apos;ll tune suggestions. You can change this anytime.
        </p>
        <div className="onboarding-options">
          {OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={`onboarding-option${useCase === opt.id ? ' active' : ''}`}
              onClick={() => setUseCase(opt.id)}
            >
              <strong>{opt.title}</strong>
              <span>{opt.blurb}</span>
            </button>
          ))}
        </div>
        <p className="onboarding-tip">
          Tip: connect apps like Upwork anytime from Settings → Integrations.
        </p>
        <div className="onboarding-actions">
          {onOpenIntegrations && (
            <button
              type="button"
              className="onboarding-secondary"
              onClick={() => {
                markOnboardingDone(useCase)
                onOpenIntegrations()
                onClose(useCase)
              }}
            >
              Connect an app
            </button>
          )}
          <button type="button" className="onboarding-primary" onClick={finish}>
            Start chatting
          </button>
        </div>
      </div>
    </div>
  )
}
