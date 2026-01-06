# 🔮 小易猜猜 (XiaoYi GuessGuess)

> 基于 AI 的金融时序数据分析与预测助手

## ✨ 特性

- 🤖 **自然语言交互**: 使用自然语言描述需求,自动获取和分析股票数据
- 📊 **多模型预测**: 支持 Prophet、XGBoost 等多种预测模型
- 📈 **实时流式响应**: 基于 SSE 的流式响应,实时展示分析步骤
- 🎨 **现代化界面**: Next.js + Tailwind CSS 打造的美观界面
- 🔄 **前后端分离**: 清晰的项目结构,易于维护和扩展

## 📁 项目结构

```
xiaoyi/
├── backend/                # 🔧 后端服务
│   ├── app/
│   │   ├── api/           # API路由
│   │   │   └── v1/
│   │   │       ├── endpoints/  # API端点
│   │   │       │   ├── chat.py       # 对话分析端点
│   │   │       │   ├── news.py       # 新闻API (预留)
│   │   │       │   ├── prediction.py # 预测模型 (预留)
│   │   │       │   └── upload.py     # 文件上传 (预留)
│   │   │       └── api.py        # API路由汇总
│   │   ├── core/          # 核心模块
│   │   │   ├── config.py         # 配置管理
│   │   │   └── utils.py          # 工具函数
│   │   ├── models/        # 数据模型
│   │   │   └── chat.py           # 对话请求模型
│   │   ├── services/      # 业务逻辑
│   │   │   └── finance_agent.py  # 金融分析Agent
│   │   ├── libs/          # 第三方库
│   │   └── main.py        # 应用入口
│   ├── requirements.txt   # Python依赖
│   ├── .env              # 环境变量 (需自行创建)
│   └── .env.example      # 环境变量模板
│
├── frontend/              # 🎨 前端应用
│   ├── app/              # Next.js页面
│   ├── components/       # React组件
│   │   ├── chat/        # 对话组件
│   │   ├── layout/      # 布局组件
│   │   └── lib/         # 工具
│   ├── package.json
│   └── ...
│
└── notebooks/            # 📓 实验和开发笔记
    ├── finance_agent.py  # Agent原型
    ├── libs/            # 库文件
    └── *.ipynb          # Jupyter笔记本
```

## 🚀 快速开始

### 1. 环境要求

- **Python**: 3.10+
- **Node.js**: 18+
- **包管理器**: 
  - Python: Miniconda/Anaconda
  - Node.js: pnpm (推荐)

### 2. 后端设置

#### 2.1 创建Conda环境

```bash
# 创建虚拟环境
conda create -n Xiaoyi python=3.10 -y

# 激活环境
conda activate Xiaoyi
```

#### 2.2 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

#### 2.3 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件,填入你的API Key
# DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

#### 2.4 启动后端服务

```bash
# 确保在 backend 目录下
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端服务将在 `http://localhost:8000` 启动

### 3. 前端设置

#### 3.1 安装依赖

```bash
cd frontend
pnpm install
```

#### 3.2 启动开发服务器

```bash
pnpm dev
```

前端应用将在 `http://localhost:3000` 启动

## 🎯 核心功能说明

### 后端模块

#### `finance_agent.py` - 金融分析Agent
完整的金融数据分析管道:
1. **NLP解析**: 将自然语言转换为数据配置
2. **数据获取**: 从AKShare获取股票数据
3. **时序分析**: 分析趋势、波动性等特征
4. **预测模型**: 
   - Prophet: 时序预测模型
   - XGBoost: 机器学习回归模型
5. **报告生成**: 生成自然语言分析报告

#### `chat.py` - 对话端点
提供SSE流式响应接口,实时返回分析步骤:
- 步骤1: 数据获取与预处理
- 步骤2: 时序特征分析
- 步骤3: 异常检测
- 步骤4: 模型训练与评估
- 步骤5: 预测生成
- 步骤6: 结果可视化
- 步骤7: 分析完成

#### `config.py` - 配置管理
- 自动加载 `.env` 文件
- 统一管理环境变量
- 提供Settings单例

### 前端组件

- **对话界面**: 实时显示分析步骤和结果
- **图表展示**: 可视化历史数据和预测结果
- **表格展示**: 展示数据详情和模型指标

## 🔧 开发规范

### 分支命名
- `feat/xxx` - 新功能
- `fix/xxx` - Bug修复
- `docs/xxx` - 文档更新

### 提交信息
- `feat: 添加xxx功能`
- `fix: 修复xxx问题`
- `docs: 更新xxx文档`

## 📝 API文档

启动后端后访问:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🔗 相关链接

- [AKShare文档](https://akshare.akfamily.xyz/)
- [Prophet文档](https://facebook.github.io/prophet/)
- [XGBoost文档](https://xgboost.readthedocs.io/)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [Next.js文档](https://nextjs.org/docs)

## 📄 License

MIT License
