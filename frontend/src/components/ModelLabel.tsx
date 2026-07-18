import { ChevronDown } from 'lucide-react'

interface Props {
  name: string
  onClick?: () => void
  open?: boolean
}

export default function ModelLabel({ name, onClick, open = false }: Props) {
  return (
    <button
      type="button"
      className={`composer-model-chip${open ? ' active' : ''}`}
      title={`Model: ${name}`}
      aria-label={`Model: ${name}`}
      onClick={onClick}
      disabled={!onClick}
    >
      <span className="composer-model-chip-name">{name}</span>
      <ChevronDown size={12} strokeWidth={2.25} className="composer-model-chip-chevron" aria-hidden />
    </button>
  )
}