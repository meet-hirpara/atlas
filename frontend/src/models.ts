export interface ComposerModel {
  id: string
  displayName: string
  description: string
}

export const COMPOSER_MODELS: ComposerModel[] = [
  {
    id: 'mistral-large',
    displayName: 'Fable 5',
    description: 'Powerful general assistant for reasoning and Q&A',
  },
  {
    id: 'mistral-code',
    displayName: 'Mistral Code',
    description: 'Code-focused — concise, technical, implementation-first',
  },
  {
    id: 'gpt-5.6',
    displayName: 'GPT 5.6',
    description: 'Creative and balanced — exploratory, vivid answers',
  },
]

export const DEFAULT_COMPOSER_MODEL_ID = 'mistral-large'

export function getComposerModelDisplay(modelSelection: string): string {
  const id =
    !modelSelection || modelSelection === 'auto' ? DEFAULT_COMPOSER_MODEL_ID : modelSelection
  const preset = COMPOSER_MODELS.find((m) => m.id === id)
  if (preset) return preset.displayName
  return modelSelection || 'Fable 5'
}

export function resolveComposerModelId(modelSelection: string): string {
  if (!modelSelection || modelSelection === 'auto') return DEFAULT_COMPOSER_MODEL_ID
  return modelSelection
}
