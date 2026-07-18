export interface ProjectFile {
  path: string
  language: string
  content: string
}

const FENCE_RE = /```([^\n`]+)\n([\s\S]*?)```/g
const PATH_INFO_RE = /^(?:[\w+-]+:)?([\w./\\-]+\.[\w]+)$/i

const EXT_LANG: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  py: 'python',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  html: 'html',
  css: 'css',
  md: 'markdown',
  sql: 'sql',
  sh: 'bash',
  env: 'bash',
}

function inferLanguage(path: string): string {
  const ext = path.includes('.') ? path.split('.').pop()!.toLowerCase() : ''
  return EXT_LANG[ext] ?? ext ?? 'text'
}

export function parseFenceInfo(info: string): { language: string; path?: string } {
  const trimmed = info.trim()
  if (!trimmed || trimmed.toLowerCase() === 'mermaid') {
    return { language: trimmed }
  }
  const match = PATH_INFO_RE.exec(trimmed)
  if (match) {
    const path = match[1].replace(/\\/g, '/')
    const colon = trimmed.indexOf(':')
    const language = colon > 0 ? trimmed.slice(0, colon).trim() : inferLanguage(path)
    return { language: language || 'text', path }
  }
  return { language: trimmed }
}

export function parseCodeClassName(className?: string): { language: string; path?: string } {
  const match = /language-(.+)/.exec(className || '')
  if (!match) return { language: '' }
  return parseFenceInfo(match[1])
}

export function extractProjectFiles(content: string): ProjectFile[] {
  const files: ProjectFile[] = []
  const re = new RegExp(FENCE_RE)
  let match: RegExpExecArray | null
  while ((match = re.exec(content)) !== null) {
    const { language, path } = parseFenceInfo(match[1])
    if (path) {
      files.push({
        path,
        language,
        content: match[2].replace(/\n$/, ''),
      })
    }
  }
  return files
}

export function isMultiFileProject(content: string): boolean {
  return extractProjectFiles(content).length >= 2
}

export function buildFileTree(paths: string[]): Map<string, string[]> {
  const root = new Map<string, string[]>()
  for (const filePath of paths.sort()) {
    const parts = filePath.split('/')
    if (parts.length === 1) {
      const list = root.get('') ?? []
      list.push(filePath)
      root.set('', list)
      continue
    }
    const dir = parts.slice(0, -1).join('/')
    const list = root.get(dir) ?? []
    list.push(parts[parts.length - 1])
    root.set(dir, list)
  }
  return root
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff
  for (let i = 0; i < bytes.length; i++) {
    crc ^= bytes[i]
    for (let j = 0; j < 8; j++) {
      crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1
    }
  }
  return (crc ^ 0xffffffff) >>> 0
}

function u16(n: number): number[] {
  return [n & 0xff, (n >>> 8) & 0xff]
}

function u32(n: number): number[] {
  return [n & 0xff, (n >>> 8) & 0xff, (n >>> 16) & 0xff, (n >>> 24) & 0xff]
}

export function createProjectZip(files: ProjectFile[], _projectName = 'project'): Blob {
  const chunks: number[] = []
  const central: number[] = []
  let offset = 0

  for (const file of files) {
    const nameBytes = new TextEncoder().encode(file.path.replace(/\\/g, '/'))
    const dataBytes = new TextEncoder().encode(file.content)
    const crc = crc32(dataBytes)
    const local = [
      ...u32(0x04034b50),
      ...u16(20),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u32(crc),
      ...u32(dataBytes.length),
      ...u32(dataBytes.length),
      ...u16(nameBytes.length),
      ...u16(0),
      ...Array.from(nameBytes),
      ...Array.from(dataBytes),
    ]
    chunks.push(...local)

    central.push(
      ...u32(0x02014b50),
      ...u16(20),
      ...u16(20),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u32(crc),
      ...u32(dataBytes.length),
      ...u32(dataBytes.length),
      ...u16(nameBytes.length),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u16(0),
      ...u32(0),
      ...u32(offset),
      ...Array.from(nameBytes),
    )
    offset += local.length
  }

  const centralStart = chunks.length
  chunks.push(...central)
  const centralSize = chunks.length - centralStart
  chunks.push(
    ...u32(0x06054b50),
    ...u16(0),
    ...u16(0),
    ...u16(files.length),
    ...u16(files.length),
    ...u32(centralSize),
    ...u32(centralStart),
    ...u16(0),
  )

  return new Blob([new Uint8Array(chunks)], { type: 'application/zip' })
}

export function stripProjectFences(content: string): string {
  return content.replace(FENCE_RE, (block, info: string) => {
    const { path } = parseFenceInfo(info)
    return path ? '' : block
  }).replace(/\n{3,}/g, '\n\n').trim()
}

export function downloadProjectZip(files: ProjectFile[], projectName = 'project'): void {
  const blob = createProjectZip(files, projectName)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${projectName}.zip`
  a.click()
  URL.revokeObjectURL(url)
}
