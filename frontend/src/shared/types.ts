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
export interface Health { status: string; worker_running: boolean; ffmpeg_available: boolean }
