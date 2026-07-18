export interface QuickReply {
  id: string
  label: string
  /** User message sent when chip is clicked */
  buildMessage: (assistantPreview: string) => string
}

interface ContentSignals {
  text: string
  wordCount: number
  hasCodeBlock: boolean
  hasNumberedList: boolean
  hasBulletList: boolean
  hasTable: boolean
  hasQuestion: boolean
  mentionsEmail: boolean
  mentionsProposal: boolean
  mentionsBusiness: boolean
  mentionsResearch: boolean
  mentionsPricing: boolean
  mentionsRisk: boolean
  mentionsTranslate: boolean
  hasComparison: boolean
  hasSteps: boolean
  hasHowTo: boolean
  hasFactualPrefs: boolean
  isLong: boolean
  hasDiagram: boolean
  topicHint: string | null
}

function stripMarkers(content: string): string {
  return content
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/```[\s\S]*?```/g, ' ')
    .trim()
}

function extractTopicHint(text: string): string | null {
  const heading = text.match(/^#{1,3}\s+(.+)$/m)
  if (heading) {
    const hint = heading[1].replace(/[*_`]/g, '').trim()
    if (hint.length >= 3 && hint.length <= 48) return hint
  }

  const bold = text.match(/\*\*([^*]{3,48})\*\*/)
  if (bold) {
    const hint = bold[1].trim()
    if (!/^(react|vue|python|node)$/i.test(hint)) return hint
  }

  const firstLine = text
    .split('\n')
    .map((line) => line.replace(/[*_`#>-]/g, '').trim())
    .find(
      (line) =>
        line.length >= 8 &&
        !/^(here(?:'s| is)|this is|below is|use it when)/i.test(line),
    )

  if (!firstLine) return null
  const sentence = firstLine.split(/[.!?]/)[0]?.trim()
  if (!sentence || sentence.length < 8) return null
  if (sentence.length > 48) return `${sentence.slice(0, 45).trim()}…`
  return sentence
}

function analyzeContent(content: string): ContentSignals {
  const text = stripMarkers(content)
  const words = text.split(/\s+/).filter(Boolean)

  return {
    text,
    wordCount: words.length,
    hasCodeBlock: /```[\s\S]*?```/.test(content),
    hasNumberedList: /^\s*\d+[.)]\s+/m.test(text),
    hasBulletList: /^\s*[-*•]\s+/m.test(text),
    hasTable: /\|.+\|/.test(text) && /\|[-:| ]+\|/.test(text),
    hasQuestion: /\?\s*$/.test(text.trim()) || /\?[\s\n]/.test(text),
    mentionsEmail: /\b(email|e-mail|subject line|dear\s+\w+)\b/i.test(text),
    mentionsProposal: /\b(proposal|freelance|scope of work|deliverables?|statement of work)\b/i.test(
      text,
    ),
    mentionsBusiness: /\b(client|customer|stakeholder|meeting|pitch|contract|vendor)\b/i.test(text),
    mentionsResearch: /\b(research|study|studies|sources?|evidence|literature|findings)\b/i.test(
      text,
    ),
    mentionsPricing: /\b(pric(e|ing)|budget|cost|quote|rate|fee|invoice)\b/i.test(text),
    mentionsRisk: /\b(risk|mitigation|challenge|drawback|concern|pitfall)\b/i.test(text),
    mentionsTranslate: /\b(translate|translation|hindi|spanish|french|german|language)\b/i.test(
      text,
    ),
    hasComparison: /\b(vs\.?|versus|compared to|alternative|pros and cons|trade-?offs?)\b/i.test(
      text,
    ),
    hasSteps:
      /\b(step\s+\d+|first,|second,|then,|finally,|next,)\b/i.test(text) ||
      /\b\d+[.)]\s+/m.test(text),
    hasHowTo: /\b(how to|guide|tutorial|walkthrough|instructions?)\b/i.test(text),
    hasFactualPrefs:
      /\b(i prefer|my name is|remember that|deadline is|timezone|always use|never use)\b/i.test(
        text,
      ) || /\b(as of|effective|due date|located in)\b/i.test(text),
    isLong: words.length > 140 || text.length > 750,
    hasDiagram: /```(?:mermaid|flowchart|graph)\b/.test(content),
    topicHint: extractTopicHint(text),
  }
}

type Candidate = QuickReply & { score: number }

function previewSlice(preview: string, max = 400): string {
  return preview.slice(0, max).trim()
}

function addCandidate(pool: Candidate[], candidate: Candidate): void {
  if (pool.some((item) => item.id === candidate.id)) return
  pool.push(candidate)
}

function buildCandidates(signals: ContentSignals): Candidate[] {
  const pool: Candidate[] = []
  const topic = signals.topicHint

  if (signals.isLong) {
    addCandidate(pool, {
      id: 'shorter',
      label: 'Make it shorter',
      score: 90,
      buildMessage: () => 'Explain the above more briefly using bullet points.',
    })
  }

  if (signals.hasHowTo || signals.hasSteps || signals.wordCount > 80) {
    addCandidate(pool, {
      id: 'examples',
      label: topic ? `Show examples for ${topic}` : 'Give practical examples',
      score: signals.hasHowTo ? 88 : 72,
      buildMessage: () => 'Give 2–3 concrete, practical examples based on the above.',
    })
  }

  if (signals.hasSteps || signals.hasNumberedList || signals.hasBulletList) {
    addCandidate(pool, {
      id: 'checklist',
      label: 'Turn into checklist',
      score: signals.hasSteps ? 92 : 78,
      buildMessage: () =>
        'Turn the above into a clear actionable checklist with numbered steps.',
    })
  }

  if (signals.hasComparison && !signals.hasTable) {
    addCandidate(pool, {
      id: 'table',
      label: 'Make this a table',
      score: 86,
      buildMessage: () => 'Reformat the comparison above as a clear markdown table.',
    })
  }

  if (signals.hasTable) {
    addCandidate(pool, {
      id: 'summarize-table',
      label: 'Summarize the table',
      score: 74,
      buildMessage: () => 'Summarize the key takeaways from the table above in plain language.',
    })
  }

  if (signals.hasCodeBlock) {
    addCandidate(pool, {
      id: 'explain-code',
      label: 'Explain this code',
      score: 94,
      buildMessage: () => 'Walk through the code above line by line and explain what each part does.',
    })
    addCandidate(pool, {
      id: 'improve-code',
      label: 'Suggest improvements',
      score: 82,
      buildMessage: () =>
        'Review the code above and suggest concrete improvements for readability, edge cases, and best practices.',
    })
  }

  if (signals.mentionsEmail || (signals.mentionsBusiness && signals.wordCount > 60)) {
    addCandidate(pool, {
      id: 'email',
      label: signals.mentionsEmail ? 'Polish this email' : 'Draft follow-up email',
      score: signals.mentionsEmail ? 91 : 76,
      buildMessage: () =>
        'Draft a professional email based on the above. Include subject line and body.',
    })
  }

  if (signals.mentionsProposal || (signals.mentionsBusiness && signals.hasSteps)) {
    addCandidate(pool, {
      id: 'proposal',
      label: 'Shape into proposal',
      score: signals.mentionsProposal ? 90 : 70,
      buildMessage: () =>
        'Turn the above into a freelance proposal draft (intro, scope, timeline, deliverables).',
    })
  }

  if (
    (signals.mentionsProposal || signals.mentionsBusiness) &&
    !signals.mentionsPricing
  ) {
    addCandidate(pool, {
      id: 'pricing',
      label: 'Add pricing section',
      score: 84,
      buildMessage: () =>
        'Add a pricing section to the above with tiered options and what each tier includes.',
    })
  }

  if (signals.mentionsResearch || signals.hasComparison) {
    addCandidate(pool, {
      id: 'deeper',
      label: topic ? `Go deeper on ${topic}` : 'Dig deeper',
      score: signals.mentionsResearch ? 85 : 68,
      buildMessage: () =>
        'Go deeper on the above with more detail, nuance, and supporting points.',
    })
  }

  if (signals.mentionsRisk || signals.mentionsProposal || signals.hasSteps) {
    addCandidate(pool, {
      id: 'risks',
      label: 'What are the risks?',
      score: signals.mentionsRisk ? 87 : 65,
      buildMessage: () =>
        'List the main risks, trade-offs, and failure modes related to the above, with mitigation ideas.',
    })
  }

  if (signals.hasQuestion) {
    addCandidate(pool, {
      id: 'direct-answer',
      label: 'Answer more directly',
      score: 83,
      buildMessage: () =>
        'Answer the question in the above more directly, with a short summary first.',
    })
  }

  if (signals.isLong && (signals.hasBulletList || signals.hasNumberedList)) {
    addCandidate(pool, {
      id: 'key-points',
      label: 'Highlight key points',
      score: 80,
      buildMessage: () => 'Pull out the 5 most important takeaways from the above.',
    })
  }

  if (signals.hasDiagram) {
    addCandidate(pool, {
      id: 'diagram-text',
      label: 'Explain the diagram',
      score: 88,
      buildMessage: () => 'Explain the diagram above in plain language step by step.',
    })
  }

  if (signals.mentionsTranslate) {
    addCandidate(pool, {
      id: 'translate',
      label: 'Translate to Hindi',
      score: 89,
      buildMessage: () => 'Translate the above into Hindi while keeping formatting and tone.',
    })
  } else if (signals.wordCount > 50 && !signals.hasCodeBlock) {
    addCandidate(pool, {
      id: 'simplify',
      label: 'Simplify this',
      score: 62,
      buildMessage: () =>
        'Rewrite the above in simpler language for someone new to the topic.',
    })
  }

  if (signals.hasFactualPrefs) {
    addCandidate(pool, {
      id: 'remember',
      label: 'Save to memory',
      score: 93,
      buildMessage: (preview) =>
        `Remember this for all future chats: ${previewSlice(preview)}`,
    })
  }

  if (signals.hasSteps || signals.mentionsBusiness || signals.hasHowTo) {
    addCandidate(pool, {
      id: 'next-steps',
      label: 'What should I do next?',
      score: 77,
      buildMessage: () =>
        'Based on the above, what are the smartest next steps I should take right now?',
    })
  }

  if (pool.length < 3) {
    addCandidate(pool, {
      id: 'expand',
      label: topic ? `Expand on ${topic}` : 'Tell me more',
      score: 55,
      buildMessage: () => 'Expand on the above with more detail and practical guidance.',
    })
    addCandidate(pool, {
      id: 'counterpoint',
      label: 'Play devil’s advocate',
      score: 50,
      buildMessage: () =>
        'Challenge the above with counterpoints, blind spots, and what I might be missing.',
    })
  }

  return pool
}

function stableOrder(content: string, replies: QuickReply[]): QuickReply[] {
  let hash = 0
  for (let i = 0; i < content.length; i += 1) {
    hash = (hash * 31 + content.charCodeAt(i)) >>> 0
  }

  return [...replies].sort((a, b) => {
    const aScore = (hash + a.id.length * 17) % 100
    const bScore = (hash + b.id.length * 17) % 100
    return bScore - aScore
  })
}

export function getContextualQuickReplies(content: string): QuickReply[] {
  const signals = analyzeContent(content)
  if (signals.wordCount < 12 && !signals.hasCodeBlock && !signals.hasDiagram) return []

  const ranked = buildCandidates(signals)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(({ id, label, buildMessage }) => ({ id, label, buildMessage }))

  if (ranked.length < 3) return ranked
  return stableOrder(content, ranked)
}

export function shouldShowQuickReplies(content: string, isStreaming?: boolean): boolean {
  if (isStreaming) return false
  const text = content.trim()
  if (text.length < 40) return false
  if (text.includes('<!--nexus-clarification:')) return false
  return getContextualQuickReplies(text).length > 0
}
