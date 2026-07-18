import { useState, useEffect, useCallback } from 'react'
import { BotSettings, loadSettings, saveSettings, DEFAULT_SETTINGS } from '../settings'
import type { SettingsTabId } from '../utils/connectIntent'

export type { SettingsTabId }

const SETTINGS_TABS: ReadonlySet<string> = new Set([
  'behavior',
  'connections',
  'mcp',
  'github',
])

function isSettingsTabId(value: unknown): value is SettingsTabId {
  return typeof value === 'string' && SETTINGS_TABS.has(value)
}

export interface OpenSettingsOptions {
  mcpFocus?: string | null
}

export function useSettings() {
  const [settings, setSettings] = useState<BotSettings>(loadSettings)
  const [isOpen, setIsOpen] = useState(false)
  const [initialTab, setInitialTab] = useState<SettingsTabId | null>(null)
  const [mcpFocus, setMcpFocus] = useState<string | null>(null)

  useEffect(() => {
    saveSettings(settings)
  }, [settings])

  const updateSettings = useCallback((patch: Partial<BotSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }))
  }, [])

  const resetSettings = useCallback(() => {
    setSettings({ ...DEFAULT_SETTINGS })
  }, [])

  const openSettings = useCallback((tab?: SettingsTabId, options?: OpenSettingsOptions) => {
    // Ignore non-tab first args (e.g. React MouseEvent from onClick={openSettings})
    setInitialTab(isSettingsTabId(tab) ? tab : null)
    setMcpFocus(options?.mcpFocus ?? null)
    setIsOpen(true)
  }, [])

  const closeSettings = useCallback(() => {
    setIsOpen(false)
    setInitialTab(null)
    setMcpFocus(null)
  }, [])

  return {
    settings,
    updateSettings,
    resetSettings,
    isOpen,
    initialTab,
    mcpFocus,
    openSettings,
    closeSettings,
  }
}
