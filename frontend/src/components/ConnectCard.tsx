import { Plug } from 'lucide-react'
import type { ConnectIntent } from '../utils/connectIntent'
import { connectButtonLabel } from '../utils/connectIntent'

interface Props {
  data: ConnectIntent
  onConnect: (intent: ConnectIntent) => void
}

export default function ConnectCard({ data, onConnect }: Props) {
  const title =
    data.tab === 'github'
      ? 'Connect GitHub'
      : data.preset
        ? `Connect ${data.label}`
        : 'Connect an app'

  const description =
    data.tab === 'github'
      ? 'Link a repo so Atlas can answer from your actual code — not guesses.'
      : data.preset === 'upwork'
        ? 'Open Settings to choose Profile & drafts or Live account API — one clear path for Upwork.'
        : data.preset
          ? `Open Settings → Apps & tools to connect ${data.label}. Credentials stay there once you're set up.`
          : 'Open Settings → Apps & tools to connect Blender, live Upwork, Unity, or a custom app.'

  return (
    <div className="connect-mcp-card">
      <div className="connect-mcp-card-icon" aria-hidden>
        <Plug size={18} />
      </div>
      <div className="connect-mcp-card-body">
        <h3 className="connect-mcp-card-title">{title}</h3>
        <p className="connect-mcp-card-desc">{description}</p>
        <button
          type="button"
          className="integration-btn integration-btn-connect connect-mcp-card-btn"
          onClick={() => onConnect(data)}
        >
          {connectButtonLabel(data)}
        </button>
      </div>
    </div>
  )
}
