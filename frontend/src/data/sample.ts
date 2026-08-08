import type { DashboardResponse, PlatformId, PlatformStatus, TrendItem } from '../types'

export const platformMeta: Record<PlatformId, { name: string; color: string; mark: string; url: string }> = {
  douyin: { name: '抖音', color: '#f14d7d', mark: '♪', url: 'https://www.douyin.com/discover' },
  xiaohongshu: { name: '小红书', color: '#f04a3a', mark: '小红', url: 'https://www.xiaohongshu.com/explore' },
  weibo: { name: '微博', color: '#f3a623', mark: '微', url: 'https://weibo.com/hot/search' },
  bilibili: { name: 'B站', color: '#ee6b9f', mark: '哔', url: 'https://www.bilibili.com/v/popular/rank/all' },
  zhihu: { name: '知乎', color: '#4a90e2', mark: '知', url: 'https://www.zhihu.com/hot' },
}

const titles: Record<PlatformId, string[]> = {
  douyin: ['AI生成视频的边界在哪里？', '夏日通勤穿搭一周不重样', '这届年轻人开始研究情绪价值', '普通人如何拍出电影感', '一条视频看懂今年毕业季', '周末城市周边轻旅行'],
  xiaohongshu: ['多巴胺穿搭｜夏日彩色搭配指南', '小户型收纳，真的能多出一间房', '通勤妆怎么在十分钟内完成', '今年最值得买的桌面好物', '把出租屋住出生活感', '拍照姿势终于有人讲明白了'],
  weibo: ['上半年消费趋势观察', '城市更新带来的新生活方式', '年轻人为什么开始重新看展', '今天的晚霞把城市点亮了', '体育赛事中的那些高光时刻', '网友讨论：工作和生活的边界'],
  bilibili: ['UP主用一支视频讲清楚城市的前世今生', '三角洲宝藏月最全点位', '深度拆解一款游戏的美术设计', '旅行纪录片：去海边寻找夏天', '动画真的审美降级了吗？', '一小时看懂人工智能发展史'],
  zhihu: ['如何看待越来越多人选择慢下来？', '有哪些看似普通却很有效的习惯？', '为什么我们会反复观看熟悉的电影？', '一个人生活需要哪些实用能力？', '如何判断一项技术是否真的有价值？', '怎样建立不被信息流打断的阅读时间？'],
}

const itemRows: TrendItem[] = (Object.keys(titles) as PlatformId[]).flatMap((platform) =>
  titles[platform].map((title, index) => ({
    platform,
    external_id: `sample-${platform}-${index}`,
    title,
    url: platformMeta[platform].url,
    mobile_url: platformMeta[platform].url,
    rank: index + 1,
    score: 1285432 - index * 126000,
    delta: Math.max(0, 126 - index * 17),
    source: 'sample',
    captured_at: new Date(Date.now() - index * 60_000).toISOString(),
  })),
)

const platformRows: PlatformStatus[] = (Object.keys(platformMeta) as PlatformId[]).map((id, index) => ({
  id,
  ...platformMeta[id],
  item_count: 50,
  status: 'degraded',
  source: 'sample',
  last_synced: new Date(Date.now() - index * 2 * 60_000).toISOString(),
  error: '等待首次实时采样',
  average_score: 690000 - index * 43000,
  rising_count: 12 - index,
}))

export const fallbackDashboard: DashboardResponse = {
  generated_at: new Date().toISOString(),
  storage_mode: 'memory',
  platforms: platformRows,
  items: itemRows,
  series: [],
  summary: {
    total_topics: itemRows.length,
    rising_topics: itemRows.filter((item) => item.delta > 0).length,
    active_platforms: 0,
    healthy_platforms: platformRows.length,
  },
}

