# 4gaBoard Agent — 项目计划书

> **课程**：现代软件开发方法  
> **目标应用**：[4ga Boards](https://demo.4gaboards.com/) — 看板项目管理工具  
> **用户手册**：https://docs.4gaboards.com/  

---

## 一、项目概述

构建基于大模型的测试场景生成与智能测试工具，包含两大核心任务：

| 任务 | 名称 | 目标 |
|------|------|------|
| Task 1 | 基于用户手册的测试场景自动生成 | 利用 RAG 从用户手册提取功能点，生成结构化测试场景 |
| Task 2 | 测试场景驱动的智能测试智能体 | 基于 LLM 的 Web Agent，自动执行测试场景并验证结果 |

---

## 二、技术栈

| 组件 | 技术选型 |
|------|----------|
| 编程语言 | Python 3.13 |
| 大模型 | DeepSeek V4 Flash（LLM）+ Qwen3-Embedding-8B（Embedding） |
| 检索框架 | LangChain + ChromaDB（向量存储）+ PageIndex（关键词索引） |
| 浏览器自动化 | Playwright |
| Web UI | FastAPI + Jinja2 |
| 数据模型 | Pydantic v2 |
| 版本控制 | Git |

---

## 三、项目目录结构

```
4gaboard_agent/
├── .env                      # API Key 等敏感配置
├── .gitignore
├── README.md
├── PLANS.md                  # 本文件
├── requirements.txt
├── run.py                    # 启动入口
├── scrape_docs.py            # 离线抓取脚本（一次性）
├── docs_cache/
│   └── pages.json            # 用户手册本地缓存（19 页）
├── chroma_db/                # Chroma 向量库持久化目录
└── src/
    ├── __init__.py
    ├── task1_scenario_generation/
    │   ├── __init__.py
    │   ├── models.py          # FeaturePoint / TestScenario / TestStep / TestExpectation
    │   ├── docs_scraper.py    # 文档爬取（优先读本地缓存）
    │       ├── knowledge_base.py  # LLM 工厂（get_llm + 费用追踪回调）
    │   └── scenario_generator.py  # LLM 提取功能点 + 生成测试场景
    ├── utils/                  # 工具模块
    │   ├── __init__.py
    │   └── llm_cost_tracker.py # LLM 调用追踪 + 费用计算 + 余额查询
    ├── retrieval/              # 可插拔检索策略
    │   ├── __init__.py
    │   ├── base.py             # Retriever 抽象基类
    │   ├── embedding.py        # EmbeddingRetriever（RAG / ChromaDB）
    │   ├── page_index.py       # PageIndexRetriever（关键词/标题匹配）
    │   └── factory.py          # 工厂：根据 RETRIEVER_MODE 创建实例
    ├── task2_testing_agent/
    │   ├── __init__.py
    │   ├── agent.py           # 主循环协调器
    │   ├── planner.py         # 测试场景 → 执行计划
    │   ├── memory.py          # 执行上下文记忆
    │   ├── executor.py        # Playwright 浏览器交互
    │   └── verifier.py        # 规则验证 + LLM 验证
    └── web_ui/
        ├── __init__.py
        ├── main.py            # FastAPI 路由 + 进度追踪
        ├── templates/
        │   └── index.html     # 可视化页面
        └── static/
            └── style.css
```

---

## 四、系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Web UI (FastAPI)                  │
│   ┌──────────────┐  ┌──────────────────────────┐    │
│   │ 功能点展示页面 │  │  测试执行结果报告页面     │    │
│   └──────┬───────┘  └──────────┬───────────────┘    │
└──────────┼──────────────────────┼────────────────────┘
           │                      │
┌──────────▼──────────────────────▼────────────────────┐
│                   Task 1 流水线                       │
│                                                       │
│  用户手册 → 文档抓取 → ┌─ EmbeddingRetriever (RAG) ─┐│
│                        │  分块 → ChromaDB → 语义检索 ││
│                        ├─ PageIndexRetriever ────────┤│
│                        │  关键词索引 → 标题/内容匹配 ││
│                        └──────────┬─────────────────┘│
│                                   ↓                   │
│                        LLM (检索 + 生成)              │
│                                   ↓                   │
│                       结构化测试场景 (JSON)            │
└──────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│                   Task 2 智能体                       │
│                                                       │
│  测试场景 → Planner → Memory → Executor → Verifier    │
│                          ↕                            │
│                    Playwright Browser                  │
│                          ↕                            │
│                   demo.4gaboards.com                   │
└──────────────────────────────────────────────────────┘
```

### 数据流

1. **Task 1 数据流**：
   - `docs_scraper.py` → 用户手册页面列表（19 页）→ `docs_cache/pages.json`
   - 两种检索策略（通过 `.env` 的 `RETRIEVER_MODE` 切换）：
     - **EmbeddingRetriever**（默认）：分块 → OpenAIEmbeddings → Chroma 向量库 → 语义检索
     - **PageIndexRetriever**：关键词分词 → 标题/内容倒排索引 → 关键词匹配检索
   - `scenario_generator.py` → Retriever 检索相关文档块 → LLM 提取功能点 → LLM 为每个功能点生成测试场景

2. **Task 2 数据流**：
   - 输入：`TestScenario`（steps + expectations）
   - `Planner` 将步骤转换为可执行 `PlanStep` 序列
   - `Executor` 用 Playwright 操作浏览器（导航、点击、填写等）
   - `Memory` 记录每一步的执行轨迹和页面状态
   - `Verifier` 基于规则 / LLM 判断预期结果是否满足

---

## 五、数据模型

### FeaturePoint（功能点）

```python
class FeaturePoint(BaseModel):
    name: str                          # 功能点名称，如"看板管理"
    description: str                   # 功能点描述
    scenarios: List[TestScenario]      # 测试场景列表
```

### TestScenario（测试场景）

```python
class TestScenario(BaseModel):
    name: str                          # 场景名称，如"创建新看板"
    description: str                   # 场景描述
    steps: List[TestStep]              # 操作步骤
    expectations: List[TestExpectation]  # 预期结果
```

### TestStep（操作步骤）

```python
class TestStep(BaseModel):
    action: str                        # 操作描述，如"点击'+'按钮"
    target: Optional[str]              # 目标元素描述
```

### TestExpectation（预期结果）

```python
class TestExpectation(BaseModel):
    description: str                   # 预期状态描述
```

---

## 六、Task 1 详细设计

### 6.1 文档抓取

- 手动枚举 19 个文档页面 URL（避免自动爬取超时 / 重复 / 多语言）
- 抓取后保存到 `docs_cache/pages.json`
- 运行时优先读取本地缓存，避免重复网络请求

### 6.2 RAG 流水线

```
pages.json ─→ RecursiveCharacterTextSplitter
                  chunk_size=1000, chunk_overlap=200
                      ↓
              OpenAIEmbeddings → ChromaDB
                      ↓
              similarity_search(query, k=5)
                      ↓
              相关文档块 → LLM 上下文
```

- Embedding 模型：`TOOL_EMBEDDING_MODEL`（通过 TOOL_API 接口调用）
- 检索策略：对每个功能点，以其描述作为 query 检索最相关文档块

### 6.3 测试场景生成

**阶段 1 — 功能点提取**：
- Prompt：从文档内容中提取主要功能点，每个功能点包含 name 和 description
- 输出：JSON 数组 `[{"name": "...", "description": "..."}]`

**阶段 2 — 测试场景生成**：
- 对每个功能点，RAG 检索相关文档上下文
- Prompt：根据功能描述 + 文档上下文，生成多个测试场景
- 每个场景包含：操作步骤列表 + 预期结果列表
- 输出：结构化 JSON

---

## 七、Task 2 详细设计

### 7.1 智能体架构（Planner → Executor → Verifier）

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Planner  │──▶│ Executor │──▶│ Memory   │──▶│ Verifier │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
 测试场景解析     Playwright    历史轨迹     规则/LLM 判断
```

### 7.2 Planner（规划模块）

- 接收 `TestScenario` 的结构化 steps
- 将自然语言操作步骤转换为可执行动作
- 当前：直接映射 steps → `PlanStep`
- 未来改进：让 LLM 根据当前页面状态动态调整执行计划

### 7.3 Executor（执行模块）

- 使用 Playwright 启动 Chromium 浏览器
- 支持动作类型：
  - `navigate` — 页面导航
  - `click` — 点击元素（按文本 / 选择器定位）
  - `fill` / `type` — 输入文本
  - `press` — 键盘操作
- 横竖：headless / 可见模式可切换
- 异常处理：捕获定位失败、超时等异常

### 7.4 Memory（记忆模块）

- 记录执行历史：`[{"event": "navigated", "details": {}}, ...]`
- 维护页面状态上下文
- 最近 10 条事件用于 LLM 验证上下文

### 7.5 Verifier（验证模块）

提供两种验证策略：

| 策略 | 方法 | 适用场景 |
|------|------|----------|
| 规则验证 | 检查执行轨迹中是否包含预期状态关键词 | 快速验证，适合简单场景 |
| LLM 验证 | 将执行轨迹 + 预期结果发给 LLM 判断 | 更准确，适合复杂场景 |

---

## 八、Web UI 设计

### 页面布局

```
┌──────────────────────────────────────────────────────┐
│  4gaBoard 测试场景生成与智能测试工具                    │
│  [开始抓取文档并生成测试场景]                          │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌─ 功能点 1 ──────────────────────────────────────┐ │
│  │  描述：...                                       │ │
│  │  ┌─ 测试场景 1 ───────────────────────────────┐ │ │
│  │  │  操作步骤：1. ...  2. ...                  │ │ │
│  │  │  预期结果：1. ...  2. ...                  │ │ │
│  │  └────────────────────────────────────────────┘ │ │
│  │  ┌─ 测试场景 2 ...                             │ │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─ 功能点 2 ...                                     │ │
└──────────────────────────────────────────────────────┘
```

### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 首页（可视化展示） |
| POST | `/scrape-and-generate` | 触发抓取 + 生成全流程 |
| GET | `/api/progress` | 获取当前进度（前端轮询用） |
| GET | `/api/features` | 获取所有功能点和测试场景（JSON） |
| GET | `/api/cost-report` | LLM 费用报告 |
| POST | `/api/cost-reset` | 重置费用统计 |
| POST | `/api/generate-single` | 为指定功能点单独生成测试场景 |

---

## 九、分工建议

| 模块 | 负责人 | 工作量预估 |
|------|--------|-----------|
| `models.py` + `docs_scraper.py` | — | 1 人天 |
| `knowledge_base.py`（RAG 实现） | — | 2 人天 |
| `scenario_generator.py`（Prompt 工程） | — | 2-3 人天 |
| Web UI（FastAPI + 模板） | — | 2 人天 |
| `executor.py`（Playwright 集成） | — | 2 人天 |
| `planner.py` + `agent.py`（智能体协调） | — | 2 人天 |
| `verifier.py`（验证策略） | — | 1-2 人天 |
| 测试 + 集成 + 调试 | — | 3 人天 |
| 变异测试 + 评估指标（提升档） | — | 2-3 人天 |

---

## 十、开发里程碑

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| M1：基础架构 | 第 1 周 | 项目骨架搭建、数据模型定义、文档抓取、RAG pipeline |
| M2：Task 1 完成 | 第 2 周 | 功能点提取 + 测试场景生成 + Web UI 展示 |
| M3：Task 2 基础 | 第 3 周 | Playwright 执行 + 简单场景验证 |
| M4：Task 2 完善 | 第 4 周 | LLM 验证、复杂场景执行、错误处理 |
| M5：提升档 | 第 5 周 | 变异测试、评估指标、性能优化 |

---

## 十一、评分标准对标

### 基础功能档

- [x] **Task 1**：根据用户手册识别主要功能点（14 个），生成主要功能的测试场景（65 个），格式符合要求
  - 实现方式：Embedding/PageIndex 双检索 + LLM 提取功能点，生成 `TestScenario`（steps + expectations）
- [ ] **Task 2**：智能体能够执行简单测试场景，验证执行完整性与功能正确性
  - 实现方式：Planner 解析 → Executor 执行 → Verifier 验证（开发中）

### 提升创新档

- [x] **Task 1 提升**：
  - 正确性与全面性：双检索策略（Embedding + PageIndex）+ Reranker 重排序，提高检索准确率
  - 粒度与可执行性：功能划分粒度适中（14 个功能点），场景步骤具体可被 Playwright 执行
- [ ] **Task 2 提升**：
  - 通过率与稳定性：提升执行准确率，支持中等 / 困难场景
  - 变异测试：对测试场景做变异，检测应用错误
  - 验证：识别执行成功后 / 失败，输出失败原因

---

## 十二、环境配置

### 前置要求

- Python 3.10+
- 推荐使用虚拟环境

### 安装步骤

```bash
# 克隆仓库
git clone <repo-url>
cd 4gaboard_agent

# 创建并激活虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 配置环境变量（参考 .env.example）
# DEEPSEEK_API=your_api_key_here

# 启动 Web UI
python run.py
# 浏览器打开 http://127.0.0.1:8000
```

### 环境变量

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `DEEPSEEK_API` | DeepSeek API 密钥（LLM 调用） | `sk-xxxx` |
| `DEEPSEEK_URL_OPENAI` | DeepSeek API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | LLM 模型名称 | `deepseek-v4-flash` |
| `TOOL_API` | Embedding / Reranker API 密钥 | `sk-xxxx` |
| `TOOL_API_URL_OPENAI` | Embedding / Reranker API 地址 | `https://api.siliconflow.cn` |
| `TOOL_EMBEDDING_MODEL` | Embedding 模型名称 | `Qwen/Qwen3-VL-Embedding-8B` |
| `TOOL_RERANKING_MODEL` | Reranker 模型名称（可选） | `Qwen/Qwen3-VL-Reranker-8B` |
| `RETRIEVER_MODE` | 检索策略：`embedding` 或 `page_index` | `embedding` |
| `4GABOARD_ACCOUNT` | Demo 登录账号 | `user@example.com` |
| `4GABOARD_PASSWORD` | Demo 登录密码 | — |
| `4GABOARD_CLIENT_ID` | OAuth Client ID | — |
| `4GABOARD_PWD` | 加密密码 | — |

---

## 十三、双检索策略对比评估设计

### 13.1 设计动机

提供两种检索策略作为可插拔选项，后续可系统对比其效果：

| 策略 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **EmbeddingRetriever**（RAG） | 文档分块 → Embedding → 语义相似度检索 → (可选) Reranker 重排序 | 理解语义关系，容错性强 | 需调用 Embedding API，依赖向量库 |
| **PageIndexRetriever**（PageIndex） | 关键词分词 → 标题/内容倒排索引 | 轻量、无额外 API 调用、可解释性强 | 仅匹配字面关键词，无法理解语义 |

### 13.2 评估指标

| 指标 | 计算方式 | 说明 |
|------|----------|------|
| **召回率 (Recall)** | 检索到的相关文档数 / 应检索到的文档总数 | 检索到的上下文是否覆盖功能点所需信息 |
| **场景覆盖率** | 生成场景覆盖的功能点 / 总功能点 | 是否所有功能点都生成了有效场景 |
| **场景质量（人工评分）** | 1-5 分制，评估场景步骤合理性和可执行性 | 多人交叉评分取平均 |
| **Task 2 通过率** | 执行通过的场景数 / 总执行场景数 | 生成的场景是否能被 Agent 有效执行 |

### 13.3 对比实验

```bash
# 运行 PageIndex 模式
$env:RETRIEVER_MODE="page_index"
python run.py

# 运行 Embedding 模式（默认）
$env:RETRIEVER_MODE="embedding"
python run.py
```

对两种模式分别运行完整流程后，使用评估脚本统计上述指标。

### 13.4 预期分析

- **EmbeddingRetriever** 在召回率上应该优于 PageIndex，因为语义检索能匹配"同义不同词"的查询
- **PageIndexRetriever** 在有明确关键词匹配的场景下更精确，且无额外 API 费用
- 最终选择：默认使用 EmbeddingRetriever，但在特定场景（如网络受限、仅需关键词匹配）可回退到 PageIndex

---

## 十四、注意事项

1. **API 费用**：DeepSeek V3 调用会产生费用，注意控制 token 消耗
2. **Demo 站点稳定性**：demo.4gaboards.com 为第三方托管，可能不稳定
3. **Playwright 兼容性**：确保安装的 Chromium 版本与 Playwright 匹配
4. **多语言文档**：docs.4gaboards.com 支持中/英/波兰语，仅抓取英文版即可
5. **Git 管理**：`.env`、`chroma_db/`、`docs_cache/`、`__pycache__/` 已加入 `.gitignore`

---

## 十五、LLM 费用追踪

### 15.1 设计

`src/utils/llm_cost_tracker.py` 实现了 `LLMCostTracker` 类，继承 LangChain 的 `BaseCallbackHandler`：

- **自动追踪**：通过 Callback 机制自动捕获每次 LLM 调用的 token 消耗
- **费用计算**：基于 DeepSeek 官方定价（`deepseek-v4-flash`：$0.14/1M input, $0.28/1M output）
- **余额查询**：调用 `https://api.deepseek.com/user/balance` API
- **报告输出**：格式化打印总消耗、费用（USD/CNY）、账户余额

### 15.2 API

```python
from src.utils.llm_cost_tracker import get_tracker

tracker = get_tracker()
cost = tracker.get_cost()          # 返回 {input_tokens, output_tokens, total_cost_usd, ...}
balance = tracker.get_balance()    # 返回 DeepSeek 余额信息
report = tracker.report()          # 格式化的完整报告字符串
tracker.reset()                    # 重置统计数据
```

### 15.3 Web UI

页面右上角「查看 LLM 消耗」按钮 → 弹出模态框显示完整报告。

### 15.4 定价参考（DeepSeek V4 Flash）

| 类型 | 价格（/1M tokens） |
|------|-------------------|
| Input (cache miss) | $0.14 |
| Input (cache hit) | $0.0028 |
| Output | $0.28 |
