import type { LucideIcon } from 'lucide-react'
import {
  HelpCircle,
  Plus,
  Settings,
  Telescope,
  Globe,
  Sparkles,
  Code2,
  Bot,
  Terminal,
  FileText,
  Hammer,
  GitBranch,
  Brain,
  ListChecks,
  Mail,
  Briefcase,
  Minimize2,
  Box,
} from 'lucide-react'
import type { SettingsTabId } from './connectIntent'

export interface SlashCommand {
  name: string
  label: string
  description: string
  icon: LucideIcon
  aliases?: string[]
  category?: string
  /** If true, selecting inserts `/name ` for optional args */
  acceptsArgs?: boolean
  /** Placeholder / helper when waiting for args */
  argPrompt?: string
  /** Example queries shown as clickable chips */
  suggestions?: string[]
}

export const SLASH_CATEGORIES: { id: string; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'create', label: 'Create & research' },
  { id: 'models', label: 'Models' },
  { id: 'tools', label: 'Tools' },
]

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    name: 'help',
    label: '/help',
    description: 'Show available slash commands',
    icon: HelpCircle,
    category: 'general',
  },
  {
    name: 'new',
    label: '/new',
    description: 'Start a new chat',
    icon: Plus,
    aliases: ['clear'],
    category: 'general',
  },
  {
    name: 'settings',
    label: '/settings',
    description: 'Open settings',
    icon: Settings,
    category: 'tools',
  },
  {
    name: 'mcp',
    label: '/mcp',
    description: 'Open Apps & tools in Settings',
    icon: Box,
    aliases: ['connect'],
    category: 'tools',
  },
  {
    name: 'research',
    label: '/research',
    description: 'Deep research with web sources and cited report',
    icon: Telescope,
    category: 'create',
    acceptsArgs: true,
    argPrompt: 'What should I research?',
  },
  {
    name: 'web',
    label: '/web',
    description: 'Toggle web search on or off',
    icon: Globe,
    category: 'tools',
  },
  {
    name: 'fable',
    label: '/fable',
    description: 'Switch to Fable 5 model',
    icon: Sparkles,
    aliases: ['model'],
    category: 'models',
  },
  {
    name: 'code',
    label: '/code',
    description: 'Switch to Mistral Code model',
    icon: Code2,
    category: 'models',
    acceptsArgs: true,
    argPrompt: 'What should I code?',
    suggestions: [
      'Write a Python CLI to batch-rename files',
      'Add JWT auth middleware to this Express API',
      'Refactor this function for readability and tests',
    ],
  },
  {
    name: 'gpt',
    label: '/gpt',
    description: 'Switch to GPT 5.6 model',
    icon: Bot,
    category: 'models',
  },
  {
    name: 'terminal',
    label: '/terminal',
    description: 'Open or close the code terminal',
    icon: Terminal,
    category: 'tools',
  },
  {
    name: 'pdf',
    label: '/pdf',
    description: 'Upload a PDF document',
    icon: FileText,
    aliases: ['doc', 'document'],
    category: 'tools',
  },
  {
    name: 'build',
    label: '/build',
    description: 'Production build mode — multi-file project output',
    icon: Hammer,
    category: 'create',
    acceptsArgs: true,
    argPrompt: 'What should I build?',
    suggestions: [
      'A todo app with React, TypeScript, and local storage',
      'REST API for a blog with auth and SQLite',
      'Landing page with hero, pricing, and contact form',
    ],
  },
  {
    name: 'diagram',
    label: '/diagram',
    description: 'Ask for a Mermaid diagram',
    icon: GitBranch,
    category: 'create',
    acceptsArgs: true,
    argPrompt: 'What should the diagram show?',
    suggestions: [
      'User login flow from sign-in to dashboard',
      'Microservices architecture for an e-commerce platform',
      'Git branching strategy for feature releases',
    ],
  },
  {
    name: 'memory',
    label: '/memory',
    description: 'View or save facts Atlas remembers across chats',
    icon: Brain,
    category: 'tools',
    aliases: ['remember'],
    acceptsArgs: true,
    argPrompt: 'add Your fact here — or use list / clear',
  },
  {
    name: 'summarize',
    label: '/summarize',
    description: 'Summarize long text into key points',
    icon: Minimize2,
    category: 'create',
    acceptsArgs: true,
    argPrompt: 'Paste text or describe what to summarize',
  },
  {
    name: 'checklist',
    label: '/checklist',
    description: 'Turn a topic into an actionable checklist',
    icon: ListChecks,
    category: 'create',
    acceptsArgs: true,
    argPrompt: 'What should the checklist cover?',
  },
  {
    name: 'email',
    label: '/email',
    description: 'Draft a professional email',
    icon: Mail,
    category: 'create',
    acceptsArgs: true,
    argPrompt: 'Describe the email (recipient, purpose, tone)',
  },
  {
    name: 'proposal',
    label: '/proposal',
    description: 'Draft a freelance / client proposal',
    icon: Briefcase,
    category: 'create',
    acceptsArgs: true,
    argPrompt: 'Describe the project or paste the job post',
  },
]

export interface SlashCommandContext {
  onHelp: () => void
  onNewChat: () => void
  onOpenSettings: (tab?: SettingsTabId, options?: { mcpFocus?: string | null }) => void
  onToggleWebSearch: () => void
  onToggleTerminal: () => void
  onPickPdf: () => void
  onModelSelect: (id: string) => void
  setDeepResearch: (enabled: boolean) => void
  webSearchEnabled: boolean
  onMemoryHelp: () => void
  onMemoryAdd: (text: string) => void
  onMemoryClear: () => void
}

export type SlashExecuteResult =
  | { type: 'handled' }
  | { type: 'send'; message: string; deepResearch?: boolean }
  | { type: 'insert'; text: string }

function matchCommand(token: string): SlashCommand | undefined {
  const q = token.toLowerCase()
  return SLASH_COMMANDS.find(
    (c) => c.name === q || c.aliases?.some((a) => a === q),
  )
}

export interface SlashInputParse {
  active: boolean
  query: string
  command?: SlashCommand
  args: string
  /** Query for the menu (primary command or chained command being typed) */
  menuQuery: string
  /** True when the slash command menu should be open */
  menuOpen: boolean
}

function parseSlashSegment(segment: string): {
  query: string
  command?: SlashCommand
  args: string
} {
  const body = segment.startsWith('/') ? segment.slice(1) : segment
  const space = body.indexOf(' ')
  const query = (space === -1 ? body : body.slice(0, space)).trim()
  const args = space === -1 ? '' : body.slice(space + 1)
  const command = query ? matchCommand(query) : undefined
  return { query, command, args }
}

export function parseSlashInput(input: string): SlashInputParse {
  if (!input.startsWith('/')) {
    return { active: false, query: '', args: '', menuQuery: '', menuOpen: false }
  }

  const chain = splitSlashChain(input)
  if (chain.length > 1) {
    const last = chain[chain.length - 1]!
    const primary = parseSlashSegment(chain[0]!)
    const lastParsed = parseSlashSegment(last)
    // Menu follows the last incomplete token in a multi-command chain
    const menuOpen = !lastParsed.command || (lastParsed.command && !last.includes(' ') && last === `/${lastParsed.query}`)
    return {
      active: true,
      query: primary.query,
      command: primary.command,
      args: input.slice(chain[0]!.length).trimStart(),
      menuQuery: lastParsed.query,
      menuOpen: Boolean(menuOpen && !lastParsed.args),
    }
  }

  const { query, command, args } = parseSlashSegment(input)
  return {
    active: true,
    query,
    command,
    args,
    menuQuery: query,
    menuOpen: !command,
  }
}

/** Split `/a /b msg` into effect commands + final payload segment.
 *  Trailing non-slash text after a side-effect command is kept with the
 *  nearest acceptsArgs command, or as a final send payload.
 */
export function splitSlashChain(input: string): string[] {
  const trimmed = input.trim()
  if (!trimmed.startsWith('/')) return [trimmed]

  const tokens: string[] = []
  const re = /\/[a-zA-Z][\w-]*/g
  let match: RegExpExecArray | null
  const starts: number[] = []
  while ((match = re.exec(trimmed)) !== null) {
    // Only treat as a chain command if at start or preceded by whitespace
    if (match.index === 0 || /\s/.test(trimmed[match.index - 1]!)) {
      starts.push(match.index)
    }
  }
  if (starts.length <= 1) return [trimmed]

  for (let i = 0; i < starts.length; i++) {
    const start = starts[i]!
    const end = i + 1 < starts.length ? starts[i + 1]! : trimmed.length
    tokens.push(trimmed.slice(start, end).trim())
  }
  return tokens.filter(Boolean)
}

export function filterSlashCommands(query: string): SlashCommand[] {
  const q = query.toLowerCase()
  if (!q) return SLASH_COMMANDS
  return SLASH_COMMANDS.filter(
    (c) =>
      c.name.startsWith(q) ||
      c.label.slice(1).startsWith(q) ||
      c.aliases?.some((a) => a.startsWith(q)),
  )
}

export function buildHelpMessage(): string {
  const lines = SLASH_COMMANDS.map(
    (c) => `- **${c.label}** — ${c.description}${c.acceptsArgs ? ' _(optional message after command)_' : ''}`,
  )
  return `## Slash commands\n\nType \`/\` in the message box to see these shortcuts:\n\n${lines.join('\n')}`
}

const SIDE_EFFECT_ONLY = new Set([
  'help', 'new', 'settings', 'mcp', 'web', 'terminal', 'pdf', 'memory',
])

export function executeSlashCommand(
  input: string,
  ctx: SlashCommandContext,
  options?: { chainIntermediate?: boolean },
): SlashExecuteResult {
  const chain = splitSlashChain(input)
  if (chain.length > 1) {
    // Forbid /new anywhere in a multi-command chain — it would wipe the session mid-flight.
    const hasNew = chain.some((seg) => {
      const { command } = parseSlashSegment(seg)
      return command?.name === 'new'
    })
    if (hasNew) {
      return {
        type: 'insert',
        text: input,
      }
    }

    // Collect leftover args from side-effect-only finals onto the last acceptsArgs command.
    const segments = chain.map((seg) => {
      const parsed = parseSlashSegment(seg)
      return { raw: seg, ...parsed }
    })

    let carryArgs = ''
    const last = segments[segments.length - 1]!
    if (last.command && SIDE_EFFECT_ONLY.has(last.command.name) && last.args.trim()) {
      carryArgs = last.args.trim()
      last.args = ''
    }

    if (carryArgs) {
      // Prefer attaching to the last acceptsArgs command in the chain
      for (let i = segments.length - 1; i >= 0; i--) {
        const seg = segments[i]!
        if (seg.command?.acceptsArgs) {
          seg.args = seg.args ? `${seg.args} ${carryArgs}` : carryArgs
          carryArgs = ''
          break
        }
      }
    }

    for (let i = 0; i < segments.length - 1; i++) {
      const seg = segments[i]!
      const rebuilt = seg.command
        ? `/${seg.command.name}${seg.args ? ` ${seg.args}` : ''}`
        : seg.raw
      executeSlashCommand(rebuilt, ctx, { chainIntermediate: true })
    }

    const final = segments[segments.length - 1]!
    const rebuiltFinal = final.command
      ? `/${final.command.name}${final.args ? ` ${final.args}` : ''}`
      : final.raw

    // If leftover text still has no home, send it as a normal message after effects
    if (carryArgs) {
      executeSlashCommand(rebuiltFinal, ctx, { chainIntermediate: true })
      return { type: 'send', message: carryArgs }
    }

    return executeSlashCommand(rebuiltFinal, ctx, options)
  }

  const { command, args, query } = parseSlashInput(input)
  if (!command) {
    if (query) return { type: 'send', message: input }
    return { type: 'handled' }
  }

  const trimmedArgs = args.trim()
  const chainIntermediate = options?.chainIntermediate ?? false

  switch (command.name) {
    case 'help':
      ctx.onHelp()
      return { type: 'handled' }
    case 'new':
      if (chainIntermediate) return { type: 'handled' }
      ctx.onNewChat()
      return { type: 'handled' }
    case 'settings':
      ctx.onOpenSettings()
      return { type: 'handled' }
    case 'mcp': {
      const focus = trimmedArgs.toLowerCase()
      const mcpFocus =
        focus.includes('upwork') ? 'upwork'
          : focus.includes('blender') ? 'blender'
            : focus.includes('unity') ? 'unity'
              : null
      ctx.onOpenSettings('mcp', { mcpFocus })
      return { type: 'handled' }
    }
    case 'web':
      ctx.onToggleWebSearch()
      return { type: 'handled' }
    case 'terminal':
      ctx.onToggleTerminal()
      return { type: 'handled' }
    case 'pdf':
      ctx.onPickPdf()
      return { type: 'handled' }
    case 'fable':
      ctx.onModelSelect('mistral-large')
      if (trimmedArgs) return { type: 'send', message: trimmedArgs }
      return { type: 'handled' }
    case 'code':
      ctx.onModelSelect('mistral-code')
      if (trimmedArgs) return { type: 'send', message: trimmedArgs }
      return { type: 'handled' }
    case 'gpt':
      ctx.onModelSelect('gpt-5.6')
      if (trimmedArgs) return { type: 'send', message: trimmedArgs }
      return { type: 'handled' }
    case 'research':
      ctx.setDeepResearch(true)
      if (trimmedArgs) return { type: 'send', message: trimmedArgs, deepResearch: true }
      if (chainIntermediate) return { type: 'handled' }
      return { type: 'insert', text: '/research ' }
    case 'build':
      if (trimmedArgs) {
        return {
          type: 'send',
          message: `Build a complete production-ready project: ${trimmedArgs}`,
        }
      }
      if (chainIntermediate) return { type: 'handled' }
      return { type: 'insert', text: '/build ' }
    case 'diagram':
      if (trimmedArgs) {
        return {
          type: 'send',
          message: `Create a detailed SVG diagram (use a single \`\`\`mermaid block) for: ${trimmedArgs}`,
        }
      }
      if (chainIntermediate) return { type: 'handled' }
      return { type: 'insert', text: '/diagram ' }
    case 'memory': {
      const sub = trimmedArgs.toLowerCase()
      if (!sub || sub === 'list') {
        ctx.onMemoryHelp()
        return { type: 'handled' }
      }
      if (sub === 'clear') {
        ctx.onMemoryClear()
        return { type: 'handled' }
      }
      if (sub.startsWith('add ')) {
        ctx.onMemoryAdd(trimmedArgs.slice(4).trim())
        return { type: 'handled' }
      }
      ctx.onMemoryAdd(trimmedArgs)
      return { type: 'handled' }
    }
    case 'summarize':
      if (trimmedArgs) {
        return {
          type: 'send',
          message: `Summarize the following into clear key points with a short intro:\n\n${trimmedArgs}`,
        }
      }
      if (chainIntermediate) return { type: 'handled' }
      return { type: 'insert', text: '/summarize ' }
    case 'checklist':
      if (trimmedArgs) {
        return {
          type: 'send',
          message: `Create a detailed actionable checklist for: ${trimmedArgs}`,
        }
      }
      if (chainIntermediate) return { type: 'handled' }
      return { type: 'insert', text: '/checklist ' }
    case 'email':
      if (trimmedArgs) {
        return {
          type: 'send',
          message: `Draft a professional email based on this: ${trimmedArgs}. Include subject line and email body.`,
        }
      }
      if (chainIntermediate) return { type: 'handled' }
      return { type: 'insert', text: '/email ' }
    case 'proposal':
      if (trimmedArgs) {
        return {
          type: 'send',
          message: `Write a freelance proposal draft for: ${trimmedArgs}. Include intro, understanding of needs, scope, timeline, deliverables, and closing.`,
        }
      }
      if (chainIntermediate) return { type: 'handled' }
      return { type: 'insert', text: '/proposal ' }
    default:
      return { type: 'insert', text: input }
  }
}

export function commandInsertText(command: SlashCommand): string {
  return command.acceptsArgs ? `/${command.name} ` : `/${command.name}`
}

export function buildSuggestionInput(command: SlashCommand, suggestion: string): string {
  return `/${command.name} ${suggestion}`
}

const RESEARCH_FALLBACK_POOL = [
  'Compare React vs Vue for a new SaaS dashboard',
  'Latest breakthroughs in AI agents and tooling',
  'Best practices for PostgreSQL indexing at scale',
  'State of quantum error correction and fault-tolerant qubits',
  'How vector databases compare for RAG pipelines',
  'Security implications of LLM tool-calling in production',
  'Market landscape for edge AI hardware in 2026',
  'Carbon accounting standards for cloud workloads',
  'Clinical trial progress on GLP-1 alternatives',
  'Open-source observability stacks for Kubernetes',
  'Regulatory trends in EU AI Act compliance',
  'Advances in solid-state battery chemistry',
  'Competitive analysis of serverless database offerings',
  'Impact of remote work on commercial real estate demand',
]

const RESEARCH_TOPIC_TEMPLATES = [
  (topic: string) => `Deep dive into ${topic}`,
  (topic: string) => `Latest research and developments on ${topic}`,
  (topic: string) => `Compare leading approaches to ${topic}`,
  (topic: string) => `Best practices, risks, and trade-offs for ${topic}`,
  (topic: string) => `What experts say about ${topic} in 2026`,
  (topic: string) => `Future trends and predictions for ${topic}`,
  (topic: string) => `Evidence-based overview of ${topic}`,
  (topic: string) => `How ${topic} is evolving — key players and open questions`,
]

function shufflePick<T>(items: T[], count: number): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy.slice(0, count)
}

function isUsefulResearchContext(text: string): boolean {
  const trimmed = text.trim()
  if (trimmed.length < 12) return false
  if (trimmed.startsWith('/')) return false
  if (/^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure)\b[!.?\s]*$/i.test(trimmed)) return false
  return true
}

function extractResearchTopic(recentMessages: string[]): string | null {
  const candidates = recentMessages
    .map((m) => m.trim())
    .filter(isUsefulResearchContext)
    .slice(-3)

  for (let i = candidates.length - 1; i >= 0; i--) {
    const msg = candidates[i]
    const firstSentence = msg.split(/[.!?\n]/)[0]?.trim() ?? msg
    const topic = (firstSentence.length >= 12 ? firstSentence : msg).slice(0, 120).trim()
    if (isUsefulResearchContext(topic)) return topic
  }
  return null
}

/** Context-aware research chips; randomizes fallback pool when no topic is found. */
export function getResearchSuggestions(recentMessages: string[]): string[] {
  const topic = extractResearchTopic(recentMessages)
  if (topic) {
    return shufflePick(RESEARCH_TOPIC_TEMPLATES, 3).map((fn) => fn(topic))
  }
  return shufflePick(RESEARCH_FALLBACK_POOL, 3)
}

/** True when user picked a command that expects args but hasn't typed any yet */
export function shouldShowSlashHints(input: string): SlashCommand | null {
  const { command, args } = parseSlashInput(input)
  const chained = args.trimStart().startsWith('/')

  if (chained && command) {
    const chain = parseSlashSegment(args.trimStart())
    if (!chain.command?.acceptsArgs || !chain.command.argPrompt) return null
    if (!args.trimStart().slice(1).includes(' ')) return null
    if (chain.args.trim().length > 0) return null
    return chain.command
  }

  if (!command?.acceptsArgs || !command.argPrompt) return null
  if (!input.slice(1).includes(' ')) return null
  if (args.trim().length > 0) return null
  return command
}

export function getComposerPlaceholder(
  input: string,
  deepResearch: boolean,
  defaultPlaceholder: string,
): string {
  const hintCommand = shouldShowSlashHints(input)
  if (hintCommand?.argPrompt) return hintCommand.argPrompt
  if (deepResearch) return 'What should I research in depth?'
  return defaultPlaceholder
}

export function groupSlashCommands(commands: SlashCommand[]): { category: string; label: string; commands: SlashCommand[] }[] {
  const byCategory = new Map<string, SlashCommand[]>()
  for (const cmd of commands) {
    const cat = cmd.category ?? 'general'
    const list = byCategory.get(cat) ?? []
    list.push(cmd)
    byCategory.set(cat, list)
  }
  return SLASH_CATEGORIES.filter((c) => byCategory.has(c.id)).map((c) => ({
    category: c.id,
    label: c.label,
    commands: byCategory.get(c.id)!,
  }))
}
