import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  Activity,
  BarChart3,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Database,
  ExternalLink,
  Flame,
  History,
  Info,
  LayoutDashboard,
  RefreshCw,
  Search,
  Server,
  SlidersHorizontal,
  TrendingUp,
} from 'lucide-react'
import { collectNow, fetchDashboard } from './api'
import { fallbackDashboard, platformMeta } from './data/sample'
import type { DashboardResponse, PlatformId, PlatformStatus, TrendItem } from './types'

const platformOrder: PlatformId[] = ['douyin', 'xiaohongshu', 'weibo', 'bilibili', 'zhihu']
const navItems = [
  { id: 'overview', label: '总览', icon: LayoutDashboard },
  { id: 'live', label: '实时热榜', icon: Flame },
  { id: 'history', label: '趋势回放', icon: History },
  { id: 'collectors', label: '采集器', icon: Server },
] as const

type NavId = (typeof navItems)[number]['id']

function formatScore(value: number) {
  if (!value) return '—'
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}亿`
  if (value >= 10_000) return `${(value / 10_000).toFixed(1)}万`
  return Math.round(value).toLocaleString('zh-CN')
}

function formatTime(value: string | null) {
  if (!value) return '待采样'
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value))
}

function formatRelative(value: string) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60_000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  return `${Math.round(minutes / 60)}小时前`
}

function statusLabel(status: PlatformStatus['status']) {
  return { ok: '正常', degraded: '备用', failed: '异常', pending: '等待' }[status]
}

function PlatformMark({ platform, small = false }: { platform: PlatformId; small?: boolean }) {
  const meta = platformMeta[platform]
  return (
    <span className={`platform-mark ${small ? 'platform-mark-small' : ''}`} style={{ '--mark-color': meta.color } as CSSProperties}>
      {meta.mark}
    </span>
  )
}

function Sparkline({ platform, status }: { platform: PlatformId; status: PlatformStatus }) {
  const values = Array.from({ length: 18 }, (_, index) => {
    const wave = Math.sin(index * 1.3 + platform.length) * 0.07
    const rise = index * 0.02
    return Math.max(0.16, 0.58 + wave + rise)
  })
  const path = values.map((value, index) => `${index === 0 ? 'M' : 'L'} ${index * 10.6} ${38 - value * 30}`).join(' ')
  return (
    <svg className="platform-sparkline" viewBox="0 0 180 42" role="img" aria-label={`${status.name} 热度趋势`}>
      <path d={path} fill="none" stroke={status.status === 'ok' ? '#55d6be' : '#6d899f'} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

function TrendPulse({ dashboard }: { dashboard: DashboardResponse }) {
  const chartWidth = 760
  const chartHeight = 230
  const chartPadding = { left: 40, right: 54, top: 18, bottom: 28 }
  const plotWidth = chartWidth - chartPadding.left - chartPadding.right
  const plotHeight = chartHeight - chartPadding.top - chartPadding.bottom
  const series = platformOrder.map((platform) => {
    const status = dashboard.platforms.find((row) => row.id === platform)
    const actual = dashboard.series.filter((point) => point.platform === platform)
    const baseline = Math.max(status?.average_score || 0, 180_000)
    const values = actual.length > 1
      ? actual.map((point) => point.average_score)
      : Array.from({ length: 12 }, (_, index) => baseline * (0.24 + index * 0.065 + Math.sin(index * 0.8 + platform.length) * 0.018))
    return { platform, color: platformMeta[platform].color, values }
  })
  const allValues = series.flatMap((row) => row.values)
  const min = Math.min(...allValues) * 0.86
  const max = Math.max(...allValues) * 1.05
  const pathFor = (values: number[]) => values.map((value, index) => {
    const x = chartPadding.left + (index / Math.max(values.length - 1, 1)) * plotWidth
    const y = chartPadding.top + plotHeight - ((value - min) / Math.max(max - min, 1)) * plotHeight
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
  const yTicks = [0, 1, 2, 3]

  return (
    <div className="pulse-panel panel-frame">
      <div className="panel-heading">
        <div className="panel-title-group">
          <h2>正在上升</h2>
          <Info size={15} strokeWidth={1.7} />
        </div>
        <div className="segmented-control" aria-label="趋势排序方式">
          <button className="segmented-active">增量榜</button>
          <button>增速榜</button>
          <button>新上榜</button>
        </div>
        <button className="text-button">更多 <ChevronRight size={15} /></button>
      </div>
      <div className="legend-row">
        {platformOrder.map((platform) => (
          <span key={platform} className="legend-item">
            <i style={{ background: platformMeta[platform].color }} />
            {platformMeta[platform].name}
          </span>
        ))}
      </div>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="trend-chart" role="img" aria-label="过去24小时平台热度趋势">
          {yTicks.map((tick) => {
            const y = chartPadding.top + (tick / 3) * plotHeight
            return <line key={tick} x1={chartPadding.left} x2={chartWidth - chartPadding.right} y1={y} y2={y} className="chart-grid" />
          })}
          {yTicks.map((tick) => {
            const y = chartPadding.top + (tick / 3) * plotHeight + 4
            return <text key={`label-${tick}`} x="2" y={y} className="chart-axis-label">{tick === 0 ? '0' : `${(3 - tick) * 0.4 + 0.4}M`}</text>
          })}
          {series.map((row) => <path key={row.platform} d={pathFor(row.values)} fill="none" stroke={row.color} strokeWidth="2.2" strokeLinecap="round" />)}
          {[0, 2, 4, 6, 8, 10].map((tick) => <text key={`x-${tick}`} x={chartPadding.left + (tick / 10) * plotWidth} y={chartHeight - 5} className="chart-axis-label">{['09:15', '13:15', '17:15', '21:15', '01:15', '05:15'][tick / 2]}</text>)}
        </svg>
      </div>
      <div className="pulse-footnote"><span>过去 24 小时</span><span className="muted-note">{dashboard.series.length > 0 ? '基于已采样快照' : '首轮采样后开始记录历史'}</span></div>
    </div>
  )
}

function DetailPanel({ item, dashboard }: { item: TrendItem; dashboard: DashboardResponse }) {
  const platform = dashboard.platforms.find((row) => row.id === item.platform)
  return (
    <div className="detail-panel panel-frame">
      <div className="panel-heading detail-heading">
        <h2>最新采样</h2>
        <a className="outline-button" href={item.url} target="_blank" rel="noreferrer">在平台查看 <ExternalLink size={14} /></a>
      </div>
      <div className="detail-content">
        <div className="detail-banner" style={{ '--detail-color': platform?.color || '#55d6be' } as CSSProperties}>
          <PlatformMark platform={item.platform} />
          <div className="detail-banner-lines"><span /><span /><span /><span /></div>
          <span className="detail-banner-caption">{platform?.name} / TREND SIGNAL</span>
        </div>
        <div className="detail-title-row">
          <h3>{item.title}</h3>
          {item.delta > 0 && <span className="hot-mark">热</span>}
        </div>
        <div className="detail-source"><PlatformMark platform={item.platform} small /> {platform?.name} · TOP{item.rank}<span className="detail-divider" /> 热度增量 <strong>+{item.delta.toLocaleString('zh-CN')}</strong></div>
        <div className="detail-meta-grid">
          <div><span>采样时间</span><strong>{formatTime(item.captured_at)}</strong></div>
          <div><span>当前热度</span><strong>{formatScore(item.score)}</strong></div>
          <div><span>排名变化</span><strong className="positive">{item.delta ? `↑ ${item.delta}` : '—'}</strong></div>
        </div>
        <div className="detail-actions"><a href={item.url} target="_blank" rel="noreferrer"><ExternalLink size={16} /> 原文</a><button><BarChart3 size={16} /> 加入回放</button><button><SlidersHorizontal size={16} /> 关注主题</button></div>
      </div>
    </div>
  )
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardResponse>(fallbackDashboard)
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformId | 'all'>('all')
  const [selectedItemId, setSelectedItemId] = useState<string>(fallbackDashboard.items[0].external_id)
  const [activeNav, setActiveNav] = useState<NavId>('overview')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [timeRange, setTimeRange] = useState('过去 24 小时')
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsRefreshing(true)
    try {
      const next = await fetchDashboard(selectedPlatform)
      setDashboard(next)
      setError('')
      if (next.items[0]) setSelectedItemId((current) => next.items.some((item) => item.external_id === current) ? current : next.items[0].external_id)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '数据接口暂不可用，当前展示最近一次采样')
    } finally {
      if (showSpinner) setIsRefreshing(false)
    }
  }, [selectedPlatform])

  useEffect(() => { void loadDashboard() }, [loadDashboard])
  useEffect(() => {
    if (!autoRefresh) return
    const timer = window.setInterval(() => void loadDashboard(), 30_000)
    return () => window.clearInterval(timer)
  }, [autoRefresh, loadDashboard])

  const visibleItems = useMemo(() => {
    const filtered = selectedPlatform === 'all' ? dashboard.items : dashboard.items.filter((item) => item.platform === selectedPlatform)
    return [...filtered].sort((a, b) => selectedPlatform === 'all' ? b.score - a.score : a.rank - b.rank).slice(0, 50)
  }, [dashboard.items, selectedPlatform])
  const selectedItem = visibleItems.find((item) => item.external_id === selectedItemId) || visibleItems[0] || dashboard.items[0]
  const pageTitle = navItems.find((item) => item.id === activeNav)?.label === '总览' ? '全网热度' : navItems.find((item) => item.id === activeNav)?.label
  const isSampleMode = dashboard.items.some((item) => item.source === 'sample')

  async function handleRefresh() {
    setIsRefreshing(true)
    try {
      await collectNow()
      await loadDashboard()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '刷新失败')
    } finally {
      setIsRefreshing(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Activity size={27} /></div>
          <div><strong>热榜观测台</strong><span>HOT SIGNAL ROOM</span></div>
        </div>
        <nav className="main-nav" aria-label="主导航">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${activeNav === id ? 'nav-item-active' : ''}`} onClick={() => setActiveNav(id)}>
              <Icon size={19} strokeWidth={1.7} /><span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="collector-title"><span>采集器状态</span><button onClick={handleRefresh} disabled={isRefreshing}>刷新</button></div>
          {dashboard.platforms.map((status) => (
            <div className="collector-row" key={status.id}><i className={status.status === 'ok' ? 'collector-dot collector-dot-active' : 'collector-dot'} />{status.name}采集器<span className={status.status === 'ok' ? 'collector-ok' : 'collector-muted'}>{statusLabel(status.status)}</span></div>
          ))}
          <div className="sync-block"><div><RefreshCw size={15} className={isRefreshing ? 'spin' : ''} /><span>刚刚同步</span><time>{formatTime(dashboard.generated_at)}</time></div><strong>{isSampleMode ? '存在备用数据' : '所有采集器运行正常'}</strong></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="title-line"><h1>{pageTitle}</h1><button className={`auto-refresh ${autoRefresh ? 'auto-refresh-on' : ''}`} onClick={() => setAutoRefresh((value) => !value)}><RefreshCw size={17} className={autoRefresh ? 'spin-slow' : ''} /> 自动刷新 30s</button></div>
          <div className="top-actions">
            <label className="time-select"><CalendarDays size={16} /><select value={timeRange} onChange={(event) => setTimeRange(event.target.value)}><option>过去 24 小时</option><option>过去 7 天</option><option>实时窗口</option></select><ChevronDown size={14} /></label>
            <span className="last-sync"><CheckCircle2 size={17} /> 刚刚同步 <time>{formatTime(dashboard.generated_at)}</time></span>
            <button className="primary-button" onClick={handleRefresh} disabled={isRefreshing}><RefreshCw size={17} className={isRefreshing ? 'spin' : ''} /> 刷新全部</button>
          </div>
        </header>

        {error && <div className="error-strip"><Info size={15} /> {error}</div>}
        {isSampleMode && <div className="sample-strip"><Activity size={15} /> 当前含备用样例数据；实时采集成功后会自动替换为最新榜单。</div>}

        <section className="platform-strip" aria-label="平台概览">
          {platformOrder.map((platform) => {
            const status = dashboard.platforms.find((row) => row.id === platform) || fallbackDashboard.platforms.find((row) => row.id === platform)!
            return <button key={platform} className={`platform-card ${selectedPlatform === platform ? 'platform-card-selected' : ''}`} onClick={() => setSelectedPlatform(platform)}>
              <div className="platform-card-top"><PlatformMark platform={platform} /><div><strong>{status.name}</strong><span>{status.item_count || 50} 条热榜</span></div><span className={`status-signal ${status.status === 'ok' ? 'status-signal-good' : ''}`} /></div>
              <div className="platform-stats"><span>热榜 {status.item_count || 50}</span><i /> <span className="rising-number">上升 {status.rising_count || 0}</span></div>
              <Sparkline platform={platform} status={status} />
              <div className="platform-card-footer"><CheckCircle2 size={14} /> {status.status === 'ok' ? '刚刚同步' : '备用采样'} <time>{formatTime(status.last_synced)}</time></div>
            </button>
          })}
        </section>

        <section className="workspace-grid">
          <div className="rank-panel panel-frame">
            <div className="panel-heading rank-heading"><div className="panel-title-group"><h2>实时热榜</h2><span className="record-count">{dashboard.summary.total_topics || 0} 条</span></div><div className="source-tabs"><button className={selectedPlatform === 'all' ? 'source-tab-active' : ''} onClick={() => setSelectedPlatform('all')}>全部</button>{platformOrder.map((platform) => <button key={platform} className={selectedPlatform === platform ? 'source-tab-active' : ''} onClick={() => setSelectedPlatform(platform)}><PlatformMark platform={platform} small /> {platformMeta[platform].name}</button>)}</div><button className="filter-button" aria-label="筛选"><Search size={15} /></button></div>
            <div className="table-head"><span>#</span><span>来源</span><span>话题 / 内容</span><span>热度增量 <TrendingUp size={14} /></span><span>更新时间</span></div>
            <div className="rank-list">
              {visibleItems.slice(0, 10).map((item, index) => <button key={item.external_id} className={`rank-row ${selectedItem?.external_id === item.external_id ? 'rank-row-selected' : ''}`} onClick={() => setSelectedItemId(item.external_id)}><span className={`rank-number ${index < 3 ? 'rank-top' : ''}`}>{selectedPlatform === 'all' ? index + 1 : item.rank}</span><span><PlatformMark platform={item.platform} small /></span><span className="topic-cell"><strong>{item.title}</strong>{item.delta > 90 && <em>热</em>}</span><span className="delta-cell">+{item.delta.toLocaleString('zh-CN')}</span><span className="time-cell">{formatTime(item.captured_at)}</span></button>)}
              {visibleItems.length === 0 && <div className="empty-row">暂无匹配话题</div>}
            </div>
            <div className="pagination"><button aria-label="上一页"><ChevronLeft size={17} /></button><span>1 / 10</span><button aria-label="下一页"><ChevronRight size={17} /></button><span className="pagination-total">共 {visibleItems.length || 0} 条</span></div>
          </div>
          <div className="right-column"><TrendPulse dashboard={dashboard} />{selectedItem && <DetailPanel item={selectedItem} dashboard={dashboard} />}</div>
        </section>
        <footer className="page-footer"><span><Database size={14} /> 数据源：NewsNow / 平台直连 / 授权 JSON</span><span><Check size={14} /> 仅展示公开榜单与授权数据</span><span className="footer-right">{dashboard.storage_mode === 'postgres' ? 'PostgreSQL 已连接' : '本地内存模式'}</span></footer>
      </main>
    </div>
  )
}

export default App
