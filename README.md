# 🔮 小易猜猜 (XiaoYi)

> 基于 AI 的智能金融分析与预测平台

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0+-red)](https://redis.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 核心特性

### 🤖 智能分析
- **自然语言交互**: 使用自然语言描述需求，AI 自动解析并执行分析
- **多模型预测**: 支持 Prophet、XGBoost、RandomForest、DLinear 四种预测模型
- **深度报告**: AI 生成 600-800 字专业分析报告，包含投资建议和风险提示

### 📊 数据分析
- **时序预测**: 基于历史数据预测未来 30 天价格走势
- **市场情绪**: 综合新闻和技术指标分析市场情绪（-1 到 1）
- **新闻集成**: 自动获取相关新闻并进行AI总结
- **研报集成**: 支持研报检索和总结（可扩展）

### 🎨 现代化界面
- **异步渲染**: 基于 Redis 的会话管理，实时展示 7 个分析步骤
- **专业图表**: Recharts 动态展示历史数据和预测走势
- **情绪仪表盘**: 汽车仪表盘样式的市场情绪可视化
- **Markdown 报告**: 结构化、专业的分析报告展示

### 🏗️ 技术架构
- **前后端分离**: Next.js + FastAPI
- **会话管理**: Redis 缓存，24 小时 TTL
- **异步任务**: 后台任务处理，前端轮询获取进度
- **类型安全**: Pydantic 数据验证

## 📁 项目结构

```
xiaoyi/
├── backend/                # 🔧 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/            # API 路由层
│   │   │   └── v1/endpoints/
│   │   │       ├── chat.py      # 对话分析端点（旧）
│   │   │       └── analysis.py  # 异步任务端点（新）✨
│   │   ├── core/           # 核心模块
│   │   │   ├── config.py        # 配置管理
│   │   │   ├── redis_client.py  # Redis 客户端 ✨
│   │   │   ├── session.py       # Session 管理 ✨
│   │   │   └── tasks.py         # 异步任务处理 ✨
│   │   ├── schemas/        # 数据模型
│   │   │   └── session_schema.py # Session Pydantic 模型 ✨
│   │   ├── agents/         # Agent 层
│   │   │   ├── nlp_agent.py     # NLP 解析
│   │   │   ├── report_agent.py  # 报告生成（增强）✨
│   │   │   └── feature_agents.py # 新闻/情绪分析 ✨
│   │   ├── models/         # 预测模型层
│   │   │   ├── base.py          # 基础接口
│   │   │   ├── analyzer.py      # 特征分析
│   │   │   ├── prophet.py       # Prophet
│   │   │   ├── xgboost.py       # XGBoost
│   │   │   ├── randomforest.py  # RandomForest
│   │   │   └── dlinear.py       # DLinear（完整实现）✨
│   │   ├── data/           # 数据层
│   │   │   └── fetcher.py       # 数据获取
│   │   └── main.py         # 应用入口
│   ├── requirements.txt    # Python 依赖
│   ├── .env               # 环境变量
│   └── .env.example       # 环境变量模板
│
├── frontend/               # 🎨 前端应用 (Next.js)
│   ├── app/
│   │   ├── analysis/       # 分析页面（新）✨
│   │   │   └── page.tsx
│   │   └── chat/          # 聊天页面（旧）
│   ├── lib/api/
│   │   ├── analysis.ts    # 分析API客户端 ✨
│   │   └── chat.ts        # 聊天API客户端
│   └── components/        # React 组件
│
├── docker-compose.yml     # Docker 配置
├── SCHEMA_COMPARISON.md   # Schema 对比文档 ✨
└── README.md
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Redis 7.0+
- pnpm (推荐) 或 npm

### 1. 启动 Redis

```bash
# 使用 Docker Compose
docker-compose up -d redis

# 或直接启动
redis-server
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 DEEPSEEK_API_KEY

# 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 前端设置

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm run dev
```

### 4. 访问应用

- **新版分析页面**: http://localhost:3000/analysis ✨ (推荐)
- **旧版聊天页面**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs

## 📊 Redis Session Schema

### 数据结构

```json
{
  "session_id": "uuid",
  "context": "用户上下文",
  "steps": 7,
  "status": "completed",
  "is_time_series": true,
  
  "time_series_original": [
    {"date": "2025-01-01", "value": 1856.32, "is_prediction": false}
  ],
  "time_series_full": [
    {"date": "2025-01-01", "value": 1856.32, "is_prediction": false},
    {"date": "2026-01-08", "value": 1923.45, "is_prediction": true}
  ],
  "prediction_done": true,
  "prediction_start_day": "2026-01-07",
  
  "news_list": [
    {
      "title": "...",
      "summary": "...",
      "date": "2026-01-06",
      "source": "财经日报"
    }
  ],
  "emotion": 0.7,
  "emotion_des": "市场情绪偏乐观",
  
  "conclusion": "# 综合分析报告...",
  
  "created_at": "2026-01-08T00:00:00",
  "updated_at": "2026-01-08T00:05:00",
  "model_name": "prophet"
}
```

### 验证数据

```bash
# 查看所有 session
redis-cli KEYS "session:*"

# 查看特定 session
redis-cli GET "session:<uuid>" | python3 -m json.tool

# 运行验证脚本
python3 check_redis.py
```

## 🔄 异步分析流程

### 1. 创建任务

```bash
curl -X POST http://localhost:8000/api/analysis/create \
  -H "Content-Type: application/json" \
  -d '{
    "message": "分析贵州茅台未来一个月走势",
    "model": "prophet"
  }'

# 返回: {"session_id": "uuid", "status": "created"}
```

### 2. 轮询状态

```bash
curl http://localhost:8000/api/analysis/status/<session_id>
```

### 3. 分析步骤

1. **解析需求** 🔍 - NLP 解析用户问题
2. **获取数据** 📊 - 从 AKShare 获取股票数据
3. **特征分析** 📈 - 提取时序特征
4. **获取新闻** 📰 - 获取相关新闻并总结
5. **情绪分析** 😊 - 分析市场情绪
6. **模型预测** 🔮 - 运行预测模型
7. **生成报告** 📝 - AI 生成专业报告

## 🤖 AI 功能

### 报告生成（增强版）

- **字数**: 600-800 字（原 200 字）
- **结构**: 5 个章节
  1. 历史走势分析（150-200 字）
  2. 市场情绪与基本面（100-150 字）
  3. 预测结果解读（150-200 字）
  4. 投资建议（100-150 字）
  5. 风险提示（80-100 字）
- **内容**: 包含支撑位、阻力位、止盈止损建议

### 情绪分析（双模式）

- **LLM 模式**: 使用 DeepSeek AI 深度分析
- **规则模式**: 关键词统计（备用）
- **输出**: 情绪分数（-1 到 1）+ 详细描述（100-150 字）

## 🎯 预测模型

### Prophet
- Facebook 开源时序预测
- 适合有季节性的数据
- 自动处理异常值

### XGBoost
- 梯度提升树
- 支持特征工程
- 高性能预测

### RandomForest
- 随机森林集成学习
- 稳定性好
- 抗过拟合

### DLinear ✨
- 论文标准实现
- Series Decomposition（移动平均 + L2 正则化）
- 递归预测（autoregressive）

## 🔧 配置说明

### 环境变量 (.env)

```env
# API Keys
DEEPSEEK_API_KEY=your_api_key_here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Server
HOST=0.0.0.0
PORT=8000
```

### CORS 配置

- **后端监听**: `0.0.0.0:8000` (所有网络接口)
- **CORS 允许**: `localhost:3000` (浏览器可访问)
- **前端请求**: `localhost:8000` (安全规范)

## 📝 API 文档

### 异步任务 API

#### POST /api/analysis/create
创建分析任务

**Request**:
```json
{
  "message": "分析茅台未来走势",
  "model": "prophet",
  "context": ""
}
```

**Response**:
```json
{
  "session_id": "uuid",
  "status": "created"
}
```

#### GET /api/analysis/status/{session_id}
查询任务状态

**Response**:
```json
{
  "session_id": "uuid",
  "status": "completed",
  "steps": 7,
  "data": { /* AnalysisSession */ }
}
```

#### DELETE /api/analysis/{session_id}
删除会话

## 🧪 测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
pnpm test

# Redis 验证
python3 check_redis.py
```


## 🛠️ 技术栈

### 后端
- **FastAPI** - 现代化 API 框架
- **Redis** - 会话缓存
- **Pydantic** - 数据验证
- **AKShare** - 金融数据获取
- **DeepSeek AI** - LLM 能力
- **Prophet / XGBoost / RandomForest / DLinear** - 预测模型

### 前端
- **Next.js 14** - React 框架
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式
- **Recharts** - 图表库
- **React Markdown** - Markdown 渲染
- **Lucide React** - 图标库

## 🚧 开发中功能

- [ ] MySQL 持久化存储
- [ ] 研报 RAG 检索和总结
- [ ] WebSocket 实时推送
- [ ] 任务队列（Celery/RQ）
- [ ] 更多预测模型

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

- 项目主页: [GitHub Repository]
- 问题反馈: [Issues]
