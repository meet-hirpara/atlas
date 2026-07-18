import { useEffect, useRef, useState } from 'react'
import { Check } from 'lucide-react'
import { COMPOSER_MODELS, getComposerModelDisplay, resolveComposerModelId } from '../models'
import ModelLabel from './ModelLabel'

interface Props {
  selectedId: string
  onSelect: (id: string) => void
  displayName?: string | null
  disabled?: boolean
}

export default function ModelPicker({ selectedId, onSelect, displayName, disabled }: Props) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (wrapRef.current?.contains(e.target as Node)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

  const chipName = displayName ?? getComposerModelDisplay(selectedId)
  const effectiveSelectedId = resolveComposerModelId(selectedId)

  const handleSelect = (id: string) => {
    onSelect(id)
    setOpen(false)
  }

  return (
    <div className="composer-model-picker-wrap" ref={wrapRef}>
      <ModelLabel
        name={chipName}
        open={open}
        onClick={disabled ? undefined : () => setOpen((v) => !v)}
      />
      {open && (
        <div className="composer-model-menu" role="menu" aria-label="Choose model">
          {COMPOSER_MODELS.map((model) => {
            const selected = model.id === effectiveSelectedId
            return (
              <button
                key={model.id}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                className={`composer-model-menu-item${selected ? ' selected' : ''}`}
                onClick={() => handleSelect(model.id)}
              >
                <span className="composer-model-menu-text">
                  <strong>{model.displayName}</strong>
                  <small>{model.description}</small>
                </span>
                {selected && <Check size={16} className="composer-model-menu-check" aria-hidden />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
