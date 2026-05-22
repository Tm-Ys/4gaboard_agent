# 4gaBoard Agent

基于大模型的测试场景生成与智能测试工具 — 中国科学院大学《现代软件开发方法》课程项目

## 快速开始

```bash
# 克隆
git clone <repo-url>
cd 4gaboard_agent

# 虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 启动
python run.py
# 浏览器打开 http://127.0.0.1:8000
```

## 项目结构

```
4gaboard_agent/
├── run.py                    # 启动入口
├── docs_cache/               # 用户手册缓存（19页）
├── requirements.txt
├── .env.example              # 环境变量模板
└── src/
    ├── task1_scenario_generation/  # Task 1：测试场景生成
    ├── retrieval/                  # 可插拔检索策略
    ├── task2_testing_agent/        # Task 2：智能测试智能体
    ├── utils/                      # 工具（LLM 费用追踪）
    └── web_ui/                     # FastAPI Web 界面

```

## 环境变量

参考 `.env.example` 配置，主要包括：

| 变量 | 用途 |
|------|------|
| `DEEPSEEK_API` | DeepSeek LLM API 密钥 |
| `TOOL_API` | Embedding/Reranker API 密钥 |
| `TOOL_API_URL_OPENAI` | Embedding API 地址 |
| `RETRIEVER_MODE` | 检索策略：`embedding` 或 `page_index` |
| `4GABOARD_ACCOUNT` | 4gaboards demo 登录账号（Task 2） |

## 核心功能

- **Task 1**：抓取用户手册 → 构建索引 → LLM 提取功能点 → 生成结构化测试场景（steps + expectations）
- **Task 2**（进行中）：Web 测试智能体，自动执行测试场景并验证
- **双检索策略**：Embedding（语义向量）或 PageIndex（关键词匹配），可切换对比
- **费用追踪**：自动统计 LLM 调用消耗
