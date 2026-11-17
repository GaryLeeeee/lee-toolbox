export type TaskStatus = 'queued' | 'resolving' | 'downloading' | 'verifying' | 'completed' | 'failed' | 'cancelled' | 'interrupted'
export interface Task {
  id: string
  tool_id: string
  status: TaskStatus
  title: string
  author: string
  source_text: string
  format_id: string | null
  format_label: string
  asset_ids?: string[] | null
  asset_count?: number | null
  finished_assets?: number | null
  progress: number
  downloaded_bytes: number
  total_bytes: number | null
  speed_bps: number | null
  file_name: string | null
  file_size: number | null
  file_available: boolean
  error: { code: string; message: string } | null
  created_at: string
  updated_at: string
}
export interface MediaFormat {
  id: string
  label: string
  width: number
  height: number
  codec: string
  bitrate: number
  size_bytes: number | null
}
export interface MediaInfo {
  platform: string
  id: string
  title: string
  author: string
  cover_url: string | null
  duration: number
  source_url: string
  formats: MediaFormat[]
}
export interface XhsAsset {
  id: string
  kind: 'image' | 'video'
  label: string
  width: number
  height: number
  duration: number | null
  available: boolean
  unavailable_reason: string | null
  preview_url: string | null
  watermark_status: 'none' | 'present' | 'unknown'
}
export interface XhsNote {
  platform: 'xiaohongshu'
  id: string
  title: string
  author: string
  source_url: string
  warnings: string[]
  assets: XhsAsset[]
}
export interface Health { status: string; worker_running: boolean; ffmpeg_available: boolean }
