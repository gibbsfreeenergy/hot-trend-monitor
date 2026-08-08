from __future__ import annotations

from datetime import datetime, timezone

from .models import RawTrend


PLATFORM_LABELS = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "weibo": "微博",
    "bilibili": "B站",
    "zhihu": "知乎",
}

PLATFORM_URLS = {
    "douyin": "https://www.douyin.com/discover",
    "xiaohongshu": "https://www.xiaohongshu.com/explore",
    "weibo": "https://weibo.com/hot/search",
    "bilibili": "https://www.bilibili.com/v/popular/rank/all",
    "zhihu": "https://www.zhihu.com/hot",
}

PLATFORM_COLORS = {
    "douyin": "#f14d7d",
    "xiaohongshu": "#f04a3a",
    "weibo": "#f3a623",
    "bilibili": "#ee6b9f",
    "zhihu": "#4a90e2",
}

_TITLES = {
    "douyin": [
        "AI生成视频的边界在哪里？",
        "夏日通勤穿搭一周不重样",
        "这届年轻人开始研究情绪价值",
        "普通人如何用手机拍出电影感",
        "把家整理成喜欢的样子",
        "一条视频看懂今年毕业季",
        "周末去哪里：城市周边轻旅行",
        "新手健身最容易忽略的三个细节",
        "当代年轻人的第一台相机怎么选",
        "这道家常菜为什么突然火了",
    ],
    "xiaohongshu": [
        "多巴胺穿搭｜夏日彩色搭配指南",
        "小户型收纳，真的能多出一间房",
        "通勤妆怎么在十分钟内完成",
        "低预算也能拥有的周末旅行路线",
        "今年最值得买的桌面好物",
        "新手烘焙避坑清单",
        "把出租屋住出生活感",
        "夏天的三种清爽早餐",
        "普通人的一周运动记录",
        "拍照姿势终于有人讲明白了",
    ],
    "weibo": [
        "上半年消费趋势观察",
        "城市更新带来的新生活方式",
        "年轻人为什么开始重新看展",
        "今天的晚霞把城市点亮了",
        "体育赛事中的那些高光时刻",
        "公共空间如何变得更友好",
        "一份关于夏天的记忆清单",
        "科技公司发布最新产品计划",
        "网友讨论：工作和生活的边界",
        "这件小事为什么让很多人共鸣",
    ],
    "bilibili": [
        "UP主用一支视频讲清楚城市的前世今生",
        "三角洲宝藏月最全点位",
        "深度拆解一款游戏的美术设计",
        "旅行纪录片：去海边寻找夏天",
        "动画真的审美降级了吗？",
        "把复杂的经济学讲给普通人听",
        "这首歌的现场版太好听了",
        "一小时看懂人工智能发展史",
        "年轻人正在玩的新桌游",
        "挑战用旧设备拍出电影感",
    ],
    "zhihu": [
        "如何看待越来越多人选择慢下来？",
        "有哪些看似普通却很有效的习惯？",
        "为什么我们会反复观看熟悉的电影？",
        "一个人生活需要哪些实用能力？",
        "如何判断一项技术是否真的有价值？",
        "城市里的公共图书馆应该怎样升级？",
        "有哪些适合普通人的长期主义投资？",
        "工作五年后，你最大的变化是什么？",
        "怎样建立不被信息流打断的阅读时间？",
        "旅行中最值得记录的瞬间是什么？",
    ],
}


def sample_rows(platform: str, *, source: str = "sample") -> list[RawTrend]:
    now = datetime.now(timezone.utc)
    rows: list[RawTrend] = []
    for rank, title in enumerate(_TITLES[platform], start=1):
        rows.append(
            RawTrend(
                platform=platform,
                external_id=f"sample-{platform}-{rank}",
                title=title,
                url=PLATFORM_URLS[platform],
                mobile_url=PLATFORM_URLS[platform],
                rank=rank,
                score=max(220000, 1285432 - (rank - 1) * 118000),
                source=source,
                metadata={"sampled_at": now.isoformat()},
            )
        )
    return rows

