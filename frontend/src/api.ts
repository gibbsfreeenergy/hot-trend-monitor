import type { DashboardResponse, PlatformId } from './types'

export async function fetchDashboard(platform: PlatformId | 'all'): Promise<DashboardResponse> {
  const search = platform === 'all' ? '' : `?platform=${encodeURIComponent(platform)}`
  const response = await fetch(`/api/dashboard${search}`)
  if (!response.ok) throw new Error(`dashboard request failed: ${response.status}`)
  return response.json() as Promise<DashboardResponse>
}

export async function collectNow(): Promise<void> {
  const response = await fetch('/api/collect', { method: 'POST' })
  if (!response.ok) throw new Error(`collect request failed: ${response.status}`)
}

