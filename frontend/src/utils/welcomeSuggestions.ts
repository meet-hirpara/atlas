const STORAGE_KEY = 'atlas:welcome-suggestions:last'
const CHIP_COUNT = 3

const MORNING_PROMPTS = [
  'Help me plan my day with three top priorities',
  'Draft a meeting agenda for a sprint planning session',
  'Break this project into actionable tasks for the week',
  'Review my API design approach',
  'Create a weekly learning plan for TypeScript',
  'Summarize what I should focus on this morning',
]

const AFTERNOON_PROMPTS = [
  'Build a React component for a searchable dropdown',
  'Write a Python script to parse CSV and summarize stats',
  'Help me debug a CORS error in my API',
  'Refactor this function to be more readable',
  'Design REST endpoints for user authentication',
  'Compare PostgreSQL vs MongoDB for my use case',
  'Explain how JWT authentication works step by step',
]

const EVENING_PROMPTS = [
  'Help me draft a polite follow-up email',
  'Write a product launch announcement',
  'Improve the clarity of this paragraph',
  'Create an outline for a technical blog post',
  'Help me write a freelance proposal for a web app',
  'Turn these bullet points into a professional summary',
  'Suggest taglines for a sustainable fashion brand',
]

const NIGHT_PROMPTS = [
  'Explain quantum computing in simple terms',
  'Teach me recursion with simple examples',
  'What are the latest trends in AI agents?',
  'Summarize pros and cons of GraphQL vs REST',
  'How do vector databases work for RAG pipelines?',
  'Quiz me on JavaScript closures',
]

const GENERAL_PROMPTS = [
  'Draw a transformer architecture diagram',
  'Create a flowchart for a user signup flow',
  'Diagram a microservices architecture for e-commerce',
  'Help me plan a product roadmap',
  'Brainstorm names for a productivity app',
  'Compare React vs Vue for a new SaaS dashboard',
  'How should I price a logo design package?',
  'Draft a client contract scope section',
  'Write unit tests for an async data-fetching hook',
  'Explain the CAP theorem with real-world examples',
  'Research best practices for PostgreSQL indexing',
  'Help me prepare talking points for a stakeholder demo',
  'Convert this idea into a one-page project brief',
  'Suggest interview questions for a senior backend role',
  'Outline a migration plan from monolith to microservices',
]

const ALL_PROMPTS = [
  ...MORNING_PROMPTS,
  ...AFTERNOON_PROMPTS,
  ...EVENING_PROMPTS,
  ...NIGHT_PROMPTS,
  ...GENERAL_PROMPTS,
]

type TimePeriod = 'morning' | 'afternoon' | 'evening' | 'night'

const TIME_POOLS: Record<TimePeriod, string[]> = {
  morning: MORNING_PROMPTS,
  afternoon: AFTERNOON_PROMPTS,
  evening: EVENING_PROMPTS,
  night: NIGHT_PROMPTS,
}

function shufflePick<T>(items: T[], count: number): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy.slice(0, count)
}

function getTimePeriod(): TimePeriod {
  const hour = new Date().getHours()
  if (hour >= 6 && hour < 12) return 'morning'
  if (hour >= 12 && hour < 17) return 'afternoon'
  if (hour >= 17 && hour < 22) return 'evening'
  return 'night'
}

function readLastSet(): string[] {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (!stored) return []
    const parsed = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

function saveLastSet(suggestions: string[]): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(suggestions))
  } catch {
    // sessionStorage may be unavailable in private mode
  }
}

function setsEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const sortedA = [...a].sort()
  const sortedB = [...b].sort()
  return sortedA.every((item, index) => item === sortedB[index])
}

function pickFromPool(pool: string[], count: number, exclude: Set<string>): string[] {
  const preferred = pool.filter((item) => !exclude.has(item))
  if (preferred.length >= count) return shufflePick(preferred, count)
  const extras = pool.filter((item) => exclude.has(item))
  const merged = [...new Set([...preferred, ...extras])]
  return shufflePick(merged, Math.min(count, merged.length))
}

function buildSuggestionSet(lastSet: string[]): string[] {
  const exclude = new Set<string>()
  const period = getTimePeriod()
  const timePick = shufflePick(
    TIME_POOLS[period].filter((item) => !lastSet.includes(item)),
    1,
  )
  const first = timePick[0] ?? shufflePick(TIME_POOLS[period], 1)[0]
  exclude.add(first)

  const remaining = pickFromPool(
    ALL_PROMPTS.filter((item) => item !== first),
    CHIP_COUNT - 1,
    new Set([...exclude, ...lastSet]),
  )

  return shufflePick([first, ...remaining], CHIP_COUNT)
}

/** Random welcome chips for the home screen; avoids repeating the last set when possible. */
export function getWelcomeSuggestions(): string[] {
  const lastSet = readLastSet()
  let picked = buildSuggestionSet(lastSet)

  for (let attempt = 0; attempt < 8 && setsEqual(picked, lastSet); attempt++) {
    picked = buildSuggestionSet(lastSet)
  }

  saveLastSet(picked)
  return picked
}
