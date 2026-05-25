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
├── testscene/                # Task1 历史生成场景存档（自动生成）
└── src/
    ├── __init__.py
    ├── task1_scenario_generation/
    │   ├── __init__.py
    │   ├── models.py          # FeaturePoint / TestScenario / TestStep / TestExpectation
    │   ├── docs_scraper.py    # 文档爬取（优先读本地缓存）
    │   ├── demo_crawler.py    # Demo站UI爬虫（获取实际可操作元素）
    │   ├── knowledge_base.py  # LLM 工厂（get_llm + 费用追踪回调）
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
        ├── default_features.json  # 默认场景（启动即用，免LLM）
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
| GET | `/api/testscene/list` | 列出历史生成场景存档 |
| POST | `/api/testscene/load` | 加载指定历史存档 |
| GET | `/api/task2/scenarios` | 获取所有可执行场景列表 |
| GET | `/api/task2/progress` | Task2执行进度轮询 |
| GET | `/api/task2/results` | 获取Task2执行结果 |
| POST | `/api/task2/run` | 执行指定测试场景 |

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

- [ ] **Task 1**：根据用户手册识别主要功能点，生成可执行的测试场景
  - 实现方式：Embedding/PageIndex 双检索 + LLM 提取功能点，生成 `TestScenario`（steps + expectations）
  - 当前状态：骨架完成，但生成质量待优化（target 与实际 UI 不匹配，文档利用不充分）
- [x] **Task 2**：智能体能够执行简单测试场景，验证执行完整性与功能正确性
  - 实现方式：Planner 解析 → Executor 执行（Playwright）→ Verifier 验证（结构化 + LLM）
  - 当前状态：核心链路跑通（Login → Plan → Execute → Verify），可执行 3 场景 6 用例

### 提升创新档

- [ ] **Task 1 提升**：
  - 正确性与全面性：双检索策略（Embedding + PageIndex）+ Reranker 重排序，提高检索准确率
  - 粒度与可执行性：功能划分粒度适中，场景步骤需对准实际 UI
  - ⚠️ 待优化：文档利用不完整（仅 800 字摘要），target 与实际 UI 元素不匹配
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

---

## 十六、迭代记录 — 2026-05-22

### 16.1 Task 2 核心重构

对 Task 2 进行了大规模重写，使智能体能真正端到端执行测试场景。

#### Executor 重写（`src/task2_testing_agent/executor.py`）

| 改进项 | 说明 |
|--------|------|
| **自动登录** | 从 `.env` 读取 `4GABOARD_ACCOUNT`/`4GABOARD_PASSWORD`，登录 demo 站（email + password） |
| **智能元素定位** | 多策略查找元素：`text` → `placeholder` → `aria-label` → `title` → `name` → CSS selector，逐步降级 |
| **9 种操作类型** | `click` / `fill` / `navigate` / `wait` / `screenshot` / `check` / `uncheck` / `hover` / `scroll` |
| **提交表单识别** | 自动匹配 `button[type="submit"]`，兜底 Enter 键提交 |
| **Popup/Modal 优先** | 弹窗打开时优先在弹窗内查找输入框（修复了填到搜索框的 bug） |
| **SPA 导航等待** | 提交后轮询 URL 变化，适应 React SPA 的路由跳转 |
| **每步状态捕获** | 每次操作后记录 URL、`path`、页面可见文本、关键元素列表 |
| **失败截图** | 步骤失败时自动截图到临时目录 |

#### Planner（`src/task2_testing_agent/planner.py`）

- 加入 `step_type` 标注（click / fill / navigate / wait 等），便于 executor 路由
- `context` 参数预留，后续可用于 LLM 动态规划

#### Verifier 重写（`src/task2_testing_agent/verifier.py`）

| 验证方式 | 方法 | 速度 | 准确性 |
|---------|------|------|--------|
| **结构化验证**（主力） | 检查 URL 路径模式（`/projects/...`）、页面文本、关键元素存在性 | 即时 | ✅ |
| **LLM 验证**（辅助） | 执行轨迹 + 页面状态 → DeepSeek 判断 | ~几秒 | ⚠️ 偶有假阴性 |

**去掉了多模态验证**（`MM_MODEL` 相关配置保留但不再用于验证流程），原因是：
- API 响应慢（最好情况 1-2s/请求）
- 模型对截图的理解不精确（假阳性/假阴性）

#### Web UI

- 添加「智能测试执行」侧边面板：场景列表 → 选择 → 执行 → 查看结果
- 4 个新 API 路由：
  - `GET /api/task2/scenarios` — 平坦化场景列表
  - `GET /api/task2/progress` — 执行进度轮询
  - `GET /api/task2/results` — 执行结果
  - `POST /api/task2/run` — 执行指定场景
- Task2 按钮常亮（不再依赖 Task1 是否跑过）

### 16.2 Task 1 改进

#### Demo 站 UI 爬虫（`src/task1_scenario_generation/demo_crawler.py`）

新增模块，用于登录 demo 站后爬取实际 UI 元素：
- 收集可见按钮文本、链接、输入框
- 进入项目页面收集 board view 元素
- 打开「添加项目」弹窗，记录弹窗内元素结构
- 输出结果缓存在内存中，减少重复爬取

#### 场景生成 Prompt 优化（`src/task1_scenario_generation/scenario_generator.py`）

- 特征提取 prompt 加入排除规则：不再提取注册、SSO、管理员设置等 demo 站不支持的功能
- 场景生成 prompt 加入实际 UI 元素信息：引导 LLM 使用 demo 站真实存在的元素文本作为 `target`
- 限制生成操作类型：仅生成 click/fill/navigate/wait，不生成拖拽、文件上传、键盘快捷键等

#### 默认场景数据（`src/web_ui/default_features.json`）

内置 3 个功能点 / 6 个场景，启动即用，无需调用 LLM：
- 项目管理：创建项目、侧边栏导航、搜索项目
- 面板管理：添加面板
- 看板视图：查看看板、添加卡片

#### 持久化与历史记录

- 启动时自动加载 `features.json`（无则加载 `default_features.json`）
- 重新生成场景后自动保存到 `testscene/testscene_YYYY_MM_DD_HH_MM_SS.json`
- 顶部下拉框可切换加载任意历史版本
- 新增 API：
  - `GET /api/testscene/list` — 列出历史版本
  - `POST /api/testscene/load` — 加载指定版本
- 「重新生成测试场景」按钮有确认弹窗，防止误触

### 16.3 仍需加强的部分

#### Task 1：场景生成质量

当前问题：
- 功能点提取只用了 docs 的前 800 字符摘要，未覆盖完整手册内容（19 页）
- 生成 prompt 虽然有 demo UI 信息，但 LLM 生成的 target 仍可能不匹配实际 UI
- 撤回率：无法保证每个功能点都生成了可执行的场景
- 场景粒度不均：有的 2 步，有的 8 步

建议改进方向：
- 用更完整的文档上下文（增大 `content[:800]` 或多次检索）
- 对生成的场景做可执行性校验（pre-flight check），过滤掉 executor 无法处理的步骤
- 考虑将 UI 探索结果结构化后注入 prompt（而非纯文本）
- 增加场景的后处理步骤：清洗 target 为实际 UI 文本

#### Task 2：智能体完整度

当前状态：核心链路（Login → Plan → Execute → Verify）已跑通，可执行简单场景。

**Agent**（`agent.py`）：
- ✅ 自动登录
- ✅ 执行计划
- ❌ 无场景预检（场景执行前检查步骤是否可执行）
- ❌ 无重试机制（步骤失败直接中止）
- ❌ 执行报告未持久化

**Executor**（`executor.py`）：
- ✅ 登录
- ✅ 点击（文本匹配）
- ✅ 填写输入框
- ✅ 表单提交
- ✅ 导航
- ❌ 下拉选择（`<select>`）
- ❌ 复选框/单选框
- ❌ 文件上传
- ❌ 拖拽操作
- ❌ 元素等待/显式等待策略
- ❌ 弹窗/确认框处理（Alert/Confirm/Prompt）

**Planner**（`planner.py`）：
- ❌ 未真正使用 LLM 做动态规划
- ❌ `context` 参数未接入
- ❌ 无错误恢复策略

**Verifier**（`verifier.py`）：
- ✅ 结构化验证（URL 模式、文本匹配、元素存在性）
- ✅ LLM 验证
- ❌ 缺少截图对比验证
- ❌ 验证规则不可扩展（硬编码在 `_check_*` 方法中）
- ❌ 无验证结果聚合/报告

**Memory**（`memory.py`）：
- ✅ 事件记录
- ✅ 页面状态键值存储
- ❌ 缺少截图历史
- ❌ `get_context()` 信息密度低（仅输出 event 名称）
- ❌ 无法回溯到特定时间点的状态

**整体架构**：
- ❌ 无 CLI 入口（只能通过 Web UI 调用）
- ❌ 无批量执行模式
- ❌ 无测试报告导出
- ❌ 无执行日志持久化
- ❌ 无并发/并行执行支持

### 16.4 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/task2_testing_agent/executor.py` | 重写 | 登录、智能定位、9种操作、状态捕获 |
| `src/task2_testing_agent/agent.py` | 重写 | 自动登录、加载.env、结果处理 |
| `src/task2_testing_agent/verifier.py` | 重写 | 结构化验证 + LLM验证，去掉多模态 |
| `src/task2_testing_agent/planner.py` | 重写 | 步骤类型标注 |
| `src/task2_testing_agent/memory.py` | 不变 | — |
| `src/task1_scenario_generation/demo_crawler.py` | 新增 | demo站UI爬虫 |
| `src/task1_scenario_generation/scenario_generator.py` | 修改 | prompt加入demo UI约束 |
| `src/task1_scenario_generation/knowledge_base.py` | 修改 | 去掉多模态client |
| `src/web_ui/main.py` | 修改 | 默认加载、testscene存档、Task2路由 |
| `src/web_ui/default_features.json` | 新增 | 默认场景数据 |
| `src/web_ui/templates/index.html` | 修改 | Task2面板、历史选择器 |
| `src/web_ui/static/style.css` | 修改 | Task2面板样式 |
| `.env` | 修改 | 加入MM_MODEL配置 |

---

## 十七、迭代记录 — 2026-05-25 — Task 2 完善（阶段 1-4 全部完成）

### 17.1 背景

基于 2026-05-22 的迭代记录 §16.3 "仍需加强的部分" 中列出的 20+ 项缺失功能，本次迭代对 Task 2 进行了全模块改进，分 4 个阶段实施。

### 17.2 实现方案

| 阶段 | 优先级 | 覆盖的缺失项 |
|------|--------|-------------|
| 阶段 1a：Executor 稳定性 | 高 | 显式等待策略、下拉选择、弹窗/确认框处理 |
| 阶段 1b：Agent 健壮性 | 高 | 场景预检、重试机制 |
| 阶段 2：LLM 动态规划 | 中 | LLM 动态规划、错误恢复策略、可扩展验证规则 |
| 阶段 3：Memory+报告 | 中 | 截图历史、get_context 密度提升、报告持久化 |
| 阶段 4：CLI+批量 | 低 | CLI 入口、批量执行、并发 |

### 17.3 文件变更清单

#### 新增文件

| 文件 | 说明 |
|------|------|
| `src/task2_testing_agent/verification_rules.json` | 可配置验证规则（URL 模式 + 元素存在性检查），替代硬编码字典 |
| `testscene/` | 执行报告持久化目录 |

#### 修改文件

**`src/task2_testing_agent/executor.py`** — 10 项改进

| 改进项 | 代码 |
|--------|------|
| 显式等待 `_wait_for_element(selector, timeout, state)` | 新增方法，基于 Playwright 原生 `wait_for_selector` |
| 弹窗自动处理 | `start()` 中注册 `page.on("dialog")` → `dialog.accept()` |
| 下拉选择 `_do_select()` | 检测 `<select>` 标签并用 `select_option(label=...)` 操作 |
| 新增 `select` 操作类型 | `_parse_action` 识别 "下拉" 关键字 → select 动作 |
| 提交按钮英文关键词 | `_do_click` 的 `is_submit` 检测新增 `submit/create/save/add` |
| `_capture_state` 每步截图 | `page_state` 事件附带 `screenshot` 路径 |
| 关键元素大小写不敏感 | 匹配 `keyword.lower() in text_lower` 而非精确匹配 |
| `_wait_ready` 英文兼容 | `button:has-text("Add Project")` 而非中文 |
| `_extract_value_from_action` 中英双语 | 支持 `fill/project/password/email` 等英文关键词 |
| `_click_by_text` 稳定性 | 使用 `get_by_text("Add Project", exact=True)` 优先 |

**`src/task2_testing_agent/agent.py`** — 6 项改进

| 改进项 | 代码 |
|--------|------|
| 场景预检 `_precheck_scenario()` | 执行前检查缺失的 action/target |
| 重试机制 `_execute_with_retry()` | 步骤失败最多重试 2 次，失败后调用 LLM 恢复 |
| LLM 超时保护 `_call_with_timeout()` | 线程超时机制，规避 API 挂死 |
| 报告持久化 `_save_report()` | 每次执行后保存 JSON 到 `testscene/task2_report_*.json` |
| 错误恢复集成 | 调用 `planner.plan_recovery()` 生成替代操作 |
| 预检警告输出 | 返回结果中携带 `warnings` 字段 |

**`src/task2_testing_agent/planner.py`** — 4 项改进

| 改进项 | 代码 |
|--------|------|
| LLM 动态规划 `_adjust_with_llm()` | 根据页面状态动态跳过/调整步骤 |
| 错误恢复 `plan_recovery()` | 步骤失败时 LLM 生成替代操作 |
| API 超时保护 `_llm_invoke_safe()` | 统一封装 LLM 调用，10 秒超时 |
| 新增 `select` 类型检测 | `_detect_type` 识别 "下拉" 关键字 |
| 英文 Prompt | 全部改用英文以减少 LLM 理解偏差 |

**`src/task2_testing_agent/verifier.py`** — 4 项改进

| 改进项 | 代码 |
|--------|------|
| 可配置规则 | 从 `verification_rules.json` 加载，`reload_rules()` 热加载 |
| 大小写不敏感匹配 | 元素存在性检查使用 `keyword.lower() in text_lower` |
| `_check_url_pattern` 从配置加载 | 替代硬编码 dict |
| `_check_element_existence` 从配置加载 | 替代硬编码 dict |

**`src/task2_testing_agent/memory.py`** — 5 项改进

| 改进项 | 代码 |
|--------|------|
| 截图历史 | `screenshots: List[str]` 自动追踪每步截图路径 |
| `get_context()` 密度提升 | 输出事件名 + 关键细节（点击目标/填充值/导航 URL） |
| 时间点回溯 | `get_state_at(index)` 获取指定历史点的页面状态 |
| 序列化 | `to_dict()` 方法用于报告导出 |
| 最新截图获取 | `get_latest_screenshot()` 便捷方法 |

**`src/web_ui/main.py`** — 2 项新增 API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/task2/run-all` | 批量执行所有场景 |
| GET | `/api/task2/reports` | 列出历史执行报告 |

**`run.py`** — CLI 入口

| 命令 | 参数 | 描述 |
|------|------|------|
| `python run.py task2` | `--all` | 批量执行所有场景 |
| `python run.py task2` | `--scenario "名称"` | 按名称过滤执行 |
| `python run.py task2` | `--no-headless` | 显示浏览器窗口 |
| `python run.py` | （无参数） | 启动 Web UI（默认行为） |

**`src/web_ui/default_features.json`** — 中英适配

- 将场景中的中文 target 全部替换为英文（与 demo 站实际 UI 匹配）
- 更新期望描述以兼容结构化验证
- 场景保留 3 个功能点 6 个场景

**`src/task2_testing_agent/verification_rules.json`**（新增）

- 5 条 URL 路径模式（project/board/login/home/settings）
- 9 条元素存在性规则（sidebar/project/card/board/list/error/modal/user）

### 17.4 环境依赖安装

```bash
pip install playwright langchain langchain-community langchain-openai langchain-chroma langchain-text-splitters openai
playwright install chromium
```

### 17.5 验证结果

经过对 demo.4gaboards.com 的实际运行验证：

| 场景 | 结构化验证 | LLM 验证 | 备注 |
|------|-----------|---------|------|
| **Create new project** | ✅ PASS | ⏭ 跳过 | 完整执行：点击 Add Project → 填写 → 提交 |
| **Navigate to project via sidebar** | ✅ PASS | ⏭ 跳过 | 点击 Getting started，成功跳转项目页 |
| **Search project** | ✅ PASS | ⏭ 跳过 | 搜索框过滤准确显示结果 |
| **Add board in project** | ✅ PASS | ⏭ 跳过 | 进入项目 → 添加面板 → 命名提交 |
| **View project board** | ✅ PASS | ⏭ 跳过 | 进入看板页正确显示列表和卡片 |
| **Add card on board** | ✅ 步骤级通过 | ⏭ 跳过 | 添加卡片全流程执行成功 |

> **注**：LLM 验证因 DeepSeek API 返回 `503 Service Unavailable` 被跳过。结构化验证 5/6 场景通过，"Add card" 场景的验证失败因页面文本大小写问题已修复，但 demo 站后续封锁了 headless 浏览器连接，无法重验证。

### 17.6 已知问题

| 问题 | 原因 | 影响 |
|------|------|------|
| demo.4gaboards.com 封锁 headless 浏览器 | Cloudflare 反爬机制 / 中国区网络限制 | 间歇性无法连接（ERR_CONNECTION_CLOSED） |
| DeepSeek API 503 繁忙 | API 服务负载过高 | LLM 验证和动态规划无法使用 |
| 验证规则覆盖不全 | 结构化验证依赖预定义的 URL 模式和关键词 | 部分自然语言期望无法匹配 |
| `select` 操作类型触发条件苛刻 | 需要 action 文本包含 "下拉" 关键字 | Task 1 生成的场景暂不包含下拉操作 |

### 17.7 剩余工作

- [ ] **变异测试**：对测试场景做变异操作，检测被测应用是否能正确识别错误
- [ ] **评估对比实验**：对比 EmbeddingRetriever 与 PageIndexRetriever 的召回率/场景质量
- [ ] **LLM 验证恢复**：DeepSeek API 恢复后启用 `verify_with_llm`
- [ ] **截图对比验证**：增加基于视觉 embedding 的页面截图对比
- [ ] **Web UI 完善**：Task 2 批量执行进度展示、报告可视化

### 17.8 评分标准对标更新

#### 基础功能档

- [x] **Task 1**：根据用户手册识别主要功能点，生成可执行的测试场景
  - 实现方式：Embedding/PageIndex 双检索 + LLM 提取功能点
- [x] **Task 2**：智能体能够执行简单测试场景，验证执行完整性与功能正确性
  - 实现方式：Planner → Executor(Playwright) → Verifier(结构化+LLM)
  - 当前状态：核心链路稳定，6 场景均可执行，5/6 通过结构化验证

#### 提升创新档

- [x] **Task 2 稳定性提升**：
  - 显式等待 + 弹窗自动处理 + 下拉选择支持
  - 重试机制（最多 2 次）+ 场景预检
  - LLM 动态规划 + 错误恢复策略
  - 可配置验证规则（JSON 文件驱动）
- [ ] **Task 2 剩余提升**：
  - 通过率提升至接近 100%（当前受 demo 站不稳定限制）
  - 变异测试
  - 验证结果聚合报告（结构化已实现，需可视化）
- [ ] **Task 1 提升**：
  - 文档利用不完整仍待优化
  - 场景步骤与 UI 元素对齐需要进一步工程
