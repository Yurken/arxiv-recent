# arxiv-recent

每日 arXiv 论文摘要（LLM 生成，中文）。抓取论文、通过兼容 vLLM 的接口总结，并通过 Email/Telegram 推送。

## 功能

- 按类别与关键词过滤从 arXiv Atom API 抓取论文
- 去重并使用 SQLite 保存状态
- 通过可配置 LLM 端点进行中文总结/翻译
- 并发总结并带限流
- 缓存 LLM 输出（同一论文不会重复总结）
- 幂等：同一天重复运行不会发送重复摘要
- 渲染 Markdown + 纯文本日报
- 通过 Email（SMTP）和/或 Telegram 推送
- 通过 APScheduler 每日定时
- 提供命令行用于手动运行和诊断

## 快速开始

### 1. 安装

```bash
# Clone
git clone <repo-url> && cd arxiv-recent

# Create virtualenv
python -m venv .venv && source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### 2. 配置

```bash
cp .env.example .env
# Edit .env with your settings
```

关键配置：
- `ARXIV_CATEGORIES` — 逗号分隔的 arXiv 类别（例如 `cs.CL,cs.AI`）
- `VLLM_URL` — LLM chat completions 端点
- `VLLM_MODEL_NAME` — LLM 模型名称
- `PUSH_CHANNELS` — 逗号分隔：`email`, `telegram`（留空则不推送）

### 3. 检查环境

```bash
python -m arxiv_recent doctor
```

### 4. 运行

```bash
# Full pipeline (fetch → summarize → render → push)
python -m arxiv_recent run

# Or specify a date
python -m arxiv_recent run --date 2024-01-15

# Individual steps
python -m arxiv_recent fetch
python -m arxiv_recent summarize
python -m arxiv_recent send
```

### 5. 定时

```bash
# Run daily at configured time (default 08:30 America/Los_Angeles)
python -m arxiv_recent scheduler
```

## Docker

```bash
cp .env.example .env
# Edit .env

# Build and run scheduler
docker compose up -d

# One-off run
docker compose run --rm arxiv-recent run --date 2024-01-15

# Check connectivity
docker compose run --rm arxiv-recent doctor
```

## CLI 参考

| 命令 | 说明 |
|---------|-------------|
| `python -m arxiv_recent run [--date YYYY-MM-DD]` | 完整流程 |
| `python -m arxiv_recent fetch` | 从 arXiv 抓取论文 |
| `python -m arxiv_recent summarize` | 总结未处理的论文 |
| `python -m arxiv_recent send [--date YYYY-MM-DD]` | 渲染并推送摘要 |
| `python -m arxiv_recent doctor` | 检查配置与连通性 |
| `python -m arxiv_recent scheduler` | 启动每日定时任务 |

## 开发

```bash
# Install dev dependencies
make dev

# Lint
make lint

# Format
make format

# Test
make test
```

## Makefile 目标

| 目标 | 说明 |
|--------|-------------|
| `make install` | 安装包 |
| `make dev` | 安装（含开发依赖） |
| `make lint` | 运行 ruff 代码检查 |
| `make format` | 自动格式化代码 |
| `make test` | 运行 pytest |
| `make run` | 运行完整流程 |
| `make doctor` | 检查环境 |
| `make scheduler` | 启动定时任务 |
| `make clean` | 清理产物 |

## 配置参考

所有配置通过环境变量或 `.env` 文件：

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `ARXIV_CATEGORIES` | `cs.CL,cs.AI` | arXiv 类别 |
| `ARXIV_INCLUDE_KEYWORDS` | *(empty)* | 包含任一关键词的论文 |
| `ARXIV_EXCLUDE_KEYWORDS` | *(empty)* | 排除含关键词的论文 |
| `MAX_PAPERS_PER_DAY` | `50` | 单次最多论文数 |
| `TIME_WINDOW_HOURS` | `72` | 抓取最近 N 小时的论文 |
| `VLLM_URL` | *(empty)* | LLM chat completions 端点（必填） |
| `VLLM_MODEL_NAME` | `/mnt/ssd/model/Qwen3-VL-30B-A3B-Instruct-FP8` | LLM 模型 |
| `VLLM_API_KEY` | *(empty)* | 可选 API Key |
| `LLM_MAX_CONCURRENCY` | `4` | LLM 并发上限 |
| `LLM_RATE_LIMIT_RPM` | `30` | LLM 每分钟请求上限 |
| `DB_PATH` | `data/arxiv_recent.db` | SQLite 数据库路径 |
| `SMTP_HOST` | *(empty)* | SMTP 服务器 |
| `SMTP_PORT` | `587` | SMTP 端口（465 为 SSL） |
| `SMTP_USER` | *(empty)* | SMTP 用户名 |
| `SMTP_PASS` | *(empty)* | SMTP 密码 |
| `EMAIL_FROM` | *(empty)* | 发件人地址 |
| `EMAIL_TO` | *(empty)* | 收件人（逗号分隔） |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Telegram 机器人 token |
| `TELEGRAM_CHAT_ID` | *(empty)* | Telegram chat id |
| `PUSH_CHANNELS` | *(empty)* | 推送渠道：`email`, `telegram` |
| `SCHEDULE_TIME` | `08:30` | 每日运行时间（HH:MM） |
| `SCHEDULE_TZ` | `America/Los_Angeles` | 时区 |

## 故障排查

- **`doctor` 无法访问 arXiv**：arXiv API 可能临时不可用或触发限流，稍后重试。
- **LLM 报错**：确认 `VLLM_URL` 可访问。系统会指数退避重试 3 次。
- **找不到论文**：增大 `TIME_WINDOW_HOURS` 或检查 `ARXIV_CATEGORIES`。
- **重复邮件**：系统是幂等的——重复运行不会在已发送情况下再次发送。
- **JSON 解析错误**：总结器包含修复兜底逻辑。如两次都失败，会保存一个包含 `"unknown"` 字段的最小摘要。

## 数据模型（SQLite）

- **papers**：`arxiv_id`（PK）, title, authors, category, published_at, updated_at, abs_url, pdf_url, abstract, fetched_at
- **summaries**：`arxiv_id`（PK, FK）, summary_json, created_at
- **runs**：`run_date`（PK）, status, sent_channels, created_at
