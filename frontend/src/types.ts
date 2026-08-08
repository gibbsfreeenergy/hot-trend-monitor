export type PlatformId = 'douyin' | 'xiaohongshu' | 'weibo' | 'bilibili' | 'zhihu'

export interface PlatformStatus {
  id: PlatformId
  name: string
  color: string
  url: string
  item_count: number
  status: 'ok' | 'degraded' | 'failed' | 'pending'
  source: string
  last_synced: string | null
  error: string | null
  average_score: number
  rising_count: number
}

export interface TrendItem {
  platform: PlatformId
  external_id: string
  title: string
  url: string
  mobile_url: string
  rank: number
  score: number
  delta: number
  source: string
  captured_at: string
  author?: string | null
  thumbnail_url?: string | null
  metadata?: Record<string, unknown>
}

export interface TrendSeriesPoint {
  platform: PlatformId
  captured_at: string
  average_score: number
}

export interface DashboardResponse {
  generated_at: string
  storage_mode: string
  platforms: PlatformStatus[]
  items: TrendItem[]
  series: TrendSeriesPoint[]
  summary: {
    total_topics: number
    rising_topics: number
    active_platforms: number
    healthy_platforms: number
  }
}

