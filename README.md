# 热榜观测台

面向内容运营与舆情分析的五平台实时热点监控 MVP，统一采集抖音、小红书、微博、B站、知乎公开/授权热榜，提供实时排名、热度增量、平台健康状态和 24 小时趋势回放。

## 已实现

- React + Vite 深色分析工作台：平台筛选、实时榜单、升温趋势、选中话题详情、自动刷新和手动刷新。
- FastAPI 后端：统一 `TrendItem` 模型、采集重试/降级、健康检查、榜单查询、历史快照接口。
- PostgreSQL 16：保存快照与榜单明细；Redis 7：缓存仪表盘响应。
- 五平台适配入口：抖音/微博/B站/知乎优先直连，再回退 NewsNow；小红书使用授权 JSON 源或可替换的上游适配器。
- Docker 单容器部署；GitHub Actions 构建镜像并通过 SSH 部署到已安装 PostgreSQL/Redis 的目标主机。
- 不把数据库、Redis、SSH 或平台 Cookie 写入仓库；全部通过环境变量/GitHub Actions Secrets 注入。

## 本地运行

```powershell
cd D:\hot-trend-monitor
Copy-Item .env.example .env

cd frontend
npm install
npm run dev
```

另开一个终端启动 API：

```powershell
cd D:\hot-trend-monitor\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = (Get-Location).Path
uvicorn app.main:app --reload --port 8000
```

打开 <http://localhost:5173>。如果本机没有 PostgreSQL/Redis，后端会自动进入内存模式并用明确标记的备用样例数据渲染界面。

## 数据源配置

默认配置使用 `NEWSNOW_API_URL` 作为四个平台的公共榜单回退源；也可以替换为自建 NewsNow 服务。小红书榜单不伪造“已实时接入”：请配置一个你有权限使用的 JSON 源到 `XHS_TREND_URL`，格式可以是数组，也可以是包含 `items`/`data`/`list` 的对象，字段支持 `title`、`url`、`score`、`rank`、`id`、`thumbnail`、`author`。

```env
NEWSNOW_API_URL=https://newsnow.busiyi.world/api/s
NEWSNOW_XHS_ID=xiaohongshu
XHS_TREND_URL=https://your-authorized-source.example/hot.json
XHS_COOKIE=
HTTP_PROXY_URL=
```

采集失败时是否使用备用样例由 `ALLOW_SAMPLE_FALLBACK` 控制。生产环境建议先保留为 `true`，这样单个平台上游波动不会让整站空白；平台状态会显示为“备用”，不会伪装成正常实时数据。

## API

- `GET /api/health` — 服务、PostgreSQL/Redis 模式检查
- `GET /api/dashboard?platform=all|douyin|xiaohongshu|weibo|bilibili|zhihu` — 看板聚合数据
- `GET /api/trends?platform=...&q=...` — 榜单查询
- `POST /api/collect` — 手动触发五平台采集
- `GET /api/platforms` — 平台采集器状态

## GitHub Actions 部署

工作流位于 `.github/workflows/deploy.yml`，推送 `main` 或手动运行即可：

1. 构建并推送 `ghcr.io/<owner>/hot-trend-monitor`。
2. SSH 登录目标服务器，写入 `/opt/hot-trend-monitor/.env`。
3. 以 host network 启动 `hot-trend-monitor`，复用主机 `127.0.0.1:5432` 和 `127.0.0.1:6379`。
4. 通过 `http://127.0.0.1:8080/api/health` 做部署后检查。

需要配置的 GitHub Actions Secrets：

```text
DEPLOY_HOST
DEPLOY_USER
DEPLOY_PASSWORD
DATABASE_URL
REDIS_URL
NEWSNOW_API_URL
NEWSNOW_XHS_ID
XHS_TREND_URL
XHS_COOKIE
HTTP_PROXY_URL
COLLECT_INTERVAL_SECONDS
```

`DEPLOY_PASSWORD` 只用于 Action 的 SSH 登录；服务器和数据库密码已经在聊天中暴露过，部署完成后请轮换。不要把实际值写入 `.env.example`、README、workflow 或镜像标签。

## 开源参考

实现边界和许可证说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。本仓库没有复制 TrendRadar、MediaCrawler 或其他项目的源代码。

