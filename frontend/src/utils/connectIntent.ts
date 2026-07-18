export type SettingsTabId = 'behavior' | 'connections' | 'mcp' | 'github'
export type ConnectPresetFocus = 'upwork' | 'blender' | 'unity' | null

export interface ConnectIntent {
  tab: SettingsTabId
  preset: ConnectPresetFocus
  label: string
}

const MARKER = '<!--nexus-connect:'
const MARKER_END = '-->'

const TARGET_PATTERNS: { re: RegExp; intent: ConnectIntent }[] = [
  { re: /\bupwork\b/i, intent: { tab: 'mcp', preset: 'upwork', label: 'Upwork' } },
  { re: /\bblender\b/i, intent: { tab: 'mcp', preset: 'blender', label: 'Blender' } },
  { re: /\bunity\b/i, intent: { tab: 'mcp', preset: 'unity', label: 'Unity' } },
  { re: /\bgithub\b/i, intent: { tab: 'github', preset: null, label: 'GitHub' } },
  { re: /\bmcp\b/i, intent: { tab: 'mcp', preset: null, label: 'Apps & tools' } },
]

/** Detect chat phrases like "connect upwork" / "can you connect to blender?" / "set up mcp". */
export function tryParseConnectIntent(message: string): ConnectIntent | null {
  const trimmed = message.trim()
  if (trimmed.length > 160) return null

  // Direct command forms
  const command =
    /^(?:(?:please|can you|could you|would you|hey|hi)\s+)?(?:help\s+me\s+)?(?:to\s+)?(?:connect|link|setup|set\s*up|add|enable|integrate)(?:\s+to|\s+with|\s+my)?\s+(.+?)[?.!]*$/i.exec(
      trimmed,
    )
  if (command?.[1]) {
    const rest = command[1].toLowerCase().replace(/\s+/g, ' ').trim()
    for (const { re, intent } of TARGET_PATTERNS) {
      if (re.test(rest)) return { ...intent }
    }
  }

  // Softer phrasings: "I want to connect upwork", "how do I link blender", "open mcp settings"
  const soft =
    /(?:connect|link|setup|set\s*up|add|enable|integrate|open).{0,40}?\b(upwork|blender|unity|github|mcp)\b|\b(upwork|blender|unity|github|mcp)\b.{0,30}?(?:connect|link|setup|set\s*up|settings)/i.exec(
      trimmed,
    )
  if (soft) {
    const target = (soft[1] || soft[2] || '').toLowerCase()
    for (const { re, intent } of TARGET_PATTERNS) {
      if (re.test(target)) return { ...intent }
    }
  }

  return null
}

export function parseConnectPrompt(content: string): ConnectIntent | null {
  const start = content.indexOf(MARKER)
  if (start < 0) return null
  const jsonStart = start + MARKER.length
  const end = content.indexOf(MARKER_END, jsonStart)
  if (end < 0) return null
  try {
    const data = JSON.parse(content.slice(jsonStart, end)) as ConnectIntent
    if (!data.tab || !data.label) return null
    return {
      tab: data.tab,
      preset: data.preset ?? null,
      label: String(data.label),
    }
  } catch {
    return null
  }
}

export function stripConnectMarker(content: string): string {
  const start = content.indexOf(MARKER)
  if (start < 0) return content.trim()
  return content.slice(0, start).trim()
}

export function isConnectMessage(content: string): boolean {
  return content.includes(MARKER)
}

export function encodeConnectMessage(intent: ConnectIntent): string {
  const isNamed = Boolean(intent.preset) || intent.tab === 'github'
  const title =
    intent.tab === 'github'
      ? 'Connect GitHub'
      : intent.preset
        ? `Connect ${intent.label}`
        : 'Connect an app'

  let explanation: string
  if (intent.preset === 'upwork') {
    explanation =
      'Open Settings → Integrations → Upwork and pick one path: Profile & drafts (quick) or Live account API (jobs & proposals).'
  } else if (isNamed) {
    explanation = `Open Settings to connect ${intent.label}. After you connect, it appears under Settings → ${
      intent.tab === 'github' ? 'GitHub' : 'Apps & tools'
    }.`
  } else {
    explanation =
      'Open Settings → Apps & tools to add Blender, live Upwork, Unity, or a custom connection.'
  }

  return `${title}\n\n${explanation}\n${MARKER}${JSON.stringify({
    tab: intent.tab,
    preset: intent.preset,
    label: intent.label,
  })}${MARKER_END}`
}

export function connectButtonLabel(intent: ConnectIntent): string {
  if (intent.preset) return `Connect ${intent.label}`
  if (intent.tab === 'github') return 'Open GitHub Settings'
  return 'Open Apps & tools'
}
