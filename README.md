# arxiv-recent

每日 arXiv 论文摘要（LLM 生成，中文）。自动抓取 AI / 计算机 / 网络安全方向论文，通过 vLLM 兼容接口生成中文结构化总结，邮件推送日报。

## 功能

- 按类别与关键词过滤，从 arXiv Atom API 抓取论文
- 去重并使用 SQLite 保存状态
- 通过可配置 LLM 端点并发生成中文总结（限流 + 缓存 + JSON 修复兜底）
- 幂等运行：同一天重复执行不会重复总结或发送
- 渲染 Markdown + 纯文本日报，保存到本地 `data/` 目录
- 通过 Email（SMTP）推送日报
- APScheduler 每日定时 + CLI 手动运行

## 关注方向

默认跟踪以下 arXiv 类别：

| 类别 | 方向 | 典型内容 |
|------|------|----------|
| `cs.AI` | 人工智能 | Agent、推理、知识图谱、规划 |
| `cs.LG` | 机器学习 | 模型架构、训练方法、优化、强化学习 |
| `cs.CL` | 自然语言处理 | LLM、对话系统、文本生成、RAG |
| `cs.CV` | 计算机视觉 | 多模态、图像生成、目标检测 |
| `cs.CR` | 密码学与安全 | 攻防对抗、漏洞挖掘、隐私保护、恶意软件分析 |
| `cs.NI` | 网络架构 | 网络协议、流量分析、SDN、网络安全 |

可通过 `ARXIV_INCLUDE_KEYWORDS` / `ARXIV_EXCLUDE_KEYWORDS` 进一步过滤。

## 快速开始

### 1. 安装

```bash
git clone https://github.com/Yurken/arxiv-recent.git && cd arxiv-recent

python3.11 -m venv .venv && source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. 配置

```bash
cp .env.example .env
vim .env
```

必填项：
- `VLLM_URL` — LLM chat completions 端点
- `VLLM_MODEL_NAME` — 模型名称

推送（可选）：
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` — SMTP 配置
- `EMAIL_FROM` / `EMAIL_TO` — 发件人 / 收件人
- `PUSH_CHANNELS=email` — 启用邮件推送

### 3. 检查环境

```bash
python -m arxiv_recent doctor
```

### 4. 运行

```bash
# 完整流程（抓取 → 总结 → 保存 → 推送）
python -m arxiv_recent run

# 指定日期
python -m arxiv_recent run --date 2024-01-15

# 单独步骤
python -m arxiv_recent fetch        # 仅抓取
python -m arxiv_recent summarize    # 仅总结
python -m arxiv_recent send         # 仅发送
```

### 5. 每日定时

```bash
python -m arxiv_recent scheduler
```

## 部署

### 服务器部署（systemd）

```bash
# 克隆 + 安装
git clone https://github.com/Yurken/arxiv-recent.git ~/arxiv-recent
cd ~/arxiv-recent
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# 配置
cp .env.example .env && vim .env

# 创建 systemd 服务
sudo tee /etc/systemd/system/arxiv-recent.service > /dev/null << 'EOF'
[Unit]
Description=arXiv Recent Daily Digest
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/arxiv-recent
ExecStart=/home/ubuntu/arxiv-recent/.venv/bin/python -m arxiv_recent scheduler
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now arxiv-recent
```

### 更新部署

```bash
cd ~/arxiv-recent
git pull
source .venv/bin/activate
pip install -e . -q
sudo systemctl restart arxiv-recent
```

### Docker 部署

```bash
cp .env.example .env && vim .env

docker compose up -d                                          # 启动定时
docker compose run --rm arxiv-recent run --date 2024-01-15   # 手动运行
docker compose run --rm arxiv-recent doctor                  # 检查环境
```

## 输出文件

每次运行后在 `data/` 目录生成：

```
data/
├── arxiv_recent.db          # SQLite 数据库（论文 + 摘要 + 运行记录）
├── digest-2024-01-15.md     # Markdown 日报
└── digest-2024-01-15.txt    # 纯文本日报
```

## CLI 参考

| 命令 | 说明 |
|------|------|
| `python -m arxiv_recent run [--date YYYY-MM-DD]` | 完整流程 |
| `python -m arxiv_recent fetch` | 从 arXiv 抓取论文 |
| `python -m arxiv_recent summarize` | 总结未处理的论文 |
| `python -m arxiv_recent send [--date YYYY-MM-DD]` | 渲染并推送摘要 |
| `python -m arxiv_recent doctor` | 检查配置与连通性 |
| `python -m arxiv_recent scheduler` | 启动每日定时任务 |

## 配置参考

所有配置通过环境变量或 `.env` 文件：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ARXIV_CATEGORIES` | `cs.CL,cs.AI` | arXiv 类别（逗号分隔） |
| `ARXIV_INCLUDE_KEYWORDS` | *(空)* | 包含任一关键词的论文 |
| `ARXIV_EXCLUDE_KEYWORDS` | *(空)* | 排除含关键词的论文 |
| `MAX_PAPERS_PER_DAY` | `50` | 单次最多论文数 |
| `TIME_WINDOW_HOURS` | `72` | 抓取最近 N 小时的论文 |
| `VLLM_URL` | *(空)* | LLM chat completions 端点（**必填**） |
| `VLLM_MODEL_NAME` | *(空)* | LLM 模型名称（**必填**） |
| `VLLM_API_KEY` | *(空)* | 可选 API Key |
| `LLM_MAX_CONCURRENCY` | `4` | LLM 并发上限 |
| `LLM_RATE_LIMIT_RPM` | `30` | LLM 每分钟请求上限 |
| `DB_PATH` | `data/arxiv_recent.db` | SQLite 路径 |
| `SMTP_HOST` | *(空)* | SMTP 服务器 |
| `SMTP_PORT` | `587` | SMTP 端口（465 为 SSL） |
| `SMTP_USER` | *(空)* | SMTP 用户名 |
| `SMTP_PASS` | *(空)* | SMTP 密码/授权码 |
| `EMAIL_FROM` | *(空)* | 发件人 |
| `EMAIL_TO` | *(空)* | 收件人（逗号分隔多个） |
| `PUSH_CHANNELS` | *(空)* | 推送渠道：`email` |
| `SCHEDULE_TIME` | `08:30` | 每日运行时间（HH:MM） |
| `SCHEDULE_TZ` | `America/Los_Angeles` | 时区 |

## 开发

```bash
make dev        # 安装开发依赖
make lint       # ruff 检查
make format     # 自动格式化
make test       # 运行 pytest（36 项测试）
```

## 故障排查

| 问题 | 解决 |
|------|------|
| arXiv 429 限流 | 系统自动重试（5 次，指数退避），等几分钟再试 |
| LLM 报错 | 检查 `VLLM_URL` 可达，系统自动重试 3 次 |
| 无论文 | 增大 `TIME_WINDOW_HOURS` 或检查 `ARXIV_CATEGORIES` |
| 重复邮件 | 系统幂等，不会重复发送 |
| JSON 解析失败 | 自动修复兜底，最差保存 `"unknown"` 字段的最小摘要 |
| 邮件发不出 | 运行 `python -m arxiv_recent doctor` 检查 SMTP 连通性 |

## 数据模型（SQLite）

- **papers**：`arxiv_id`（PK）, title, authors, category, published_at, updated_at, abs_url, pdf_url, abstract, fetched_at
- **summaries**：`arxiv_id`（PK, FK）, summary_json, created_at
- **runs**：`run_date`（PK）, status, sent_channels, created_at
