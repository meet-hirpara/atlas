import type { YouTubeVideo } from '../api'

const MARKER = '<!--nexus-youtube:'
const MARKER_END = '-->'

export function parseYoutubeVideos(content: string): YouTubeVideo[] {
  const start = content.indexOf(MARKER)
  if (start < 0) return []
  const jsonStart = start + MARKER.length
  const end = content.indexOf(MARKER_END, jsonStart)
  if (end < 0) return []
  try {
    const data = JSON.parse(content.slice(jsonStart, end)) as YouTubeVideo[]
    if (!Array.isArray(data)) return []
    return data.filter((v) => v && v.videoId)
  } catch {
    return []
  }
}

export function stripYoutubeMarker(content: string): string {
  const start = content.indexOf(MARKER)
  if (start < 0) return content.trim()
  return content.slice(0, start).trim()
}
