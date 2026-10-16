# 知衡 · 每日金融投资简报

公开网站：https://zesong01.github.io/value-daily/

React + TypeScript + Vite，手机优先。三层阅读、七类研究内容、六要素投资判断、原始来源、观点追踪与早晚归档。网页不需要登录，不含个人持仓或账户数据。

## 自动更新

GitHub Actions 在北京时间每天 08:30、18:30（UTC 00:30、10:30）运行 Python 脚本抓取官方数据，校验和构建成功后提交归档并部署 GitHub Pages。整个日常更新不调用模型、不需要模型 API Key，也不依赖本地电脑或 Codex 在线。平台排队可能让实际发布时间晚于计划时间；页面显示真实采集时点。

- 中证指数：沪深300，保留盘中或交易日时点。
- Nasdaq：综合指数，保留交易日及非实时标识。
- 美国财政部：10年期日度国债收益率，变化用基点。
- 国家统计局与美联储：从官方发布列表/RSS发现并打开原文。
- 巨潮资讯：跟踪唯万密封官方公告目录。目录发现不等于财报正文已经复核。

首页优先展示原始标题、来源链接和可用的原文摘要；没有摘要时只展示采集说明，明确标注“自动采集 · 未人工复核”。当前恒生科技、美元指数、黄金尚未接入可靠自动报价，缺失值保留 null。单个来源失败保留旧数据和原日期；不足两个来源成功则工作流失败，保留上一版，诊断状态保存到 Actions artifact。

每个早晚时段保存一份采集快照；休市日无新增内容会明确注明，不冒充新研究。同一期数据不变只更新 update-status.json，同一期内容改变先保存 revisions 快照。失败来源的旧公告不会因其他来源成功而被清空。

## 历史研究与自动采集的边界

原有 Codex 每日模型研究任务已暂停，日常更新完全交给 GitHub。脚本不生成投资分析、买卖评级或目标价，不改写公司财务、估值、观点追踪及 researchUpdatedAt。既有七模块研究仍可阅读，并显示原研究日期；历史催化与行动条件不代表当日建议。需要新的深度研究时，单独人工发起复核，附证据后更新。

## 深度研究编辑

公开 JSON 在 public/reports。每篇报告包含原始来源与数据期，并通过 src/report-schema.ts 校验。结论、公司/行业建议都应包括逻辑、估值、催化、行动和证伪；没有估值依据时不得给买入评级。

早晚报分别命名 YYYY-MM-DD-AM.json / PM.json；latest.json 对应最新一期，index.json 为可读历史目录。同一期修改保留 revisions 快照，Git 历史另有完整审计记录。研究改动必须更新 freshness.researchUpdatedAt，而仅采集行情不能改这个日期。

## 开发

需要 Node.js 24 和 Python 3.12+（Windows Python 需已安装时区数据库 tzdata）。

```sh
npm ci
npm run dev
npm run verify
npm run build
python scripts/update.py
python -m unittest discover -s scripts -p 'test_*.py'
```

本地入口带仓库路径： http://127.0.0.1:5182/value-daily/ 。所有数据由公开静态文件读取，没有可被公众写入的接口。关注和阅读设置仅保存在浏览器本机。网站适合添加到手机浏览器书签或主屏幕。

## 验证边界

在 GitHub Actions 的“Collect official finance sources and deploy Pages”选择 Run workflow，保持 refresh=true，即可手动补跑完整采集、校验、构建、提交与发布链路。只部署代码时可选 refresh=false。无需配置任何模型服务。TypeScript 与构建通过不等于数据源和云端发布通过。金融数据以来源时间为准，研究不能替代针对个人情况的投资判断。
