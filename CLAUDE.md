# 4gaBoard Agent — 项目规则

> 基于 LLM 的测试场景生成与智能测试工具  
> 技术栈：Python 3.13 + LangChain + ChromaDB + Playwright + FastAPI

---

## 一、常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 启动 Web UI
python run.py

# 切换检索模式
$env:RETRIEVER_MODE="page_index" && python run.py   # Windows
export RETRIEVER_MODE="page_index" && python run.py  # Linux/Mac
```

---

## 二、代码风格

- **函数/变量**：蛇形命名 `snake_case`
- **类名**：帕斯卡命名 `PascalCase`
- **常量**：大蛇形命名 `UPPER_SNAKE_CASE`
- **私有方法/属性**：单下划线前缀 `_method`
- **类型注解**：所有函数必须显式声明参数和返回类型
- **数据模型**：使用 Pydantic v2 定义

---

## 三、项目结构

```
4gaboard_agent/
├── run.py                    # 启动入口
├── docs_cache/               # 文档缓存（19页 JSON）
├── chroma_db/                # Chroma 向量库（本地生成，不提交 git）
├── requirements.txt
├── .env                      # 环境变量（不提交 git）
├── .env.example              # 环境变量模板
└── src/
    ├── task1_scenario_generation/
    │   ├── models.py              # FeaturePoint / TestScenario / TestStep
    │   ├── docs_scraper.py        # 文档爬取（优先读本地缓存）
    │   ├── knowledge_base.py      # LLM 工厂（get_llm + 费用追踪回调）
    │   └── scenario_generator.py  # 功能点提取 + 场景生成
    ├── retrieval/
    │   ├── base.py                # Retriever 抽象基类
    │   ├── embedding.py           # EmbeddingRetriever（自定义 SiliconFlow HTTP 调用）
    │   ├── page_index.py          # PageIndexRetriever（关键词/标题匹配）
    │   └── factory.py             # 工厂：根据 RETRIEVER_MODE 创建实例
    ├── task2_testing_agent/
    │   ├── agent.py               # 主循环协调器
    │   ├── planner.py             # 测试场景 → 执行计划
    │   ├── memory.py              # 执行上下文记忆
    │   ├── executor.py            # Playwright 浏览器交互
    │   └── verifier.py            # 规则验证 + LLM 验证
    ├── utils/
    │   └── llm_cost_tracker.py    # Token 追踪 + 费用计算 + 余额查询
    └── web_ui/
        ├── main.py                # FastAPI 路由 + 进度追踪
        ├── templates/index.html   # 可视化页面+实时进度条
        └── static/style.css
```

---

## 四、API 规范

### Web UI 路由

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 首页 |
| POST | `/scrape-and-generate` | 触发抓取 + 生成全流程 |
| GET | `/api/progress` | 获取当前进度（轮询用） |
| GET | `/api/features` | 获取所有功能点和测试场景 |
| GET | `/api/cost-report` | LLM 费用报告 |
| POST | `/api/cost-reset` | 重置费用统计 |

---

## 五、数据模型

```python
class FeaturePoint(BaseModel):
    name: str
    description: str
    scenarios: List[TestScenario]

class TestScenario(BaseModel):
    name: str
    description: str
    steps: List[TestStep]
    expectations: List[TestExpectation]

class TestStep(BaseModel):
    action: str
    target: Optional[str]

class TestExpectation(BaseModel):
    description: str
```

---

## 六、环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `DEEPSEEK_API` | DeepSeek LLM API 密钥 | ✅ |
| `DEEPSEEK_URL_OPENAI` | DeepSeek API 地址 | ✅ |
| `DEEPSEEK_MODEL` | LLM 模型名 | ✅ |
| `TOOL_API` | Embedding/Reranker API 密钥 | Embedding 模式必填 |
| `TOOL_API_URL_OPENAI` | Embedding API 地址 | Embedding 模式必填 |
| `TOOL_EMBEDDING_MODEL` | Embedding 模型名 | Embedding 模式必填 |
| `TOOL_RERANKING_MODEL` | Reranker 模型名（可选） | 可选 |
| `RETRIEVER_MODE` | `embedding` 或 `page_index` | 可选，默认 `embedding` |
| `4GABOARD_ACCOUNT` | Demo 账号 | Task 2 必填 |
| `4GABOARD_PASSWORD` | Demo 密码 | Task 2 必填 |
| `4GABOARD_CLIENT_ID` | OAuth client ID | Task 2 必填 |
| `4GABOARD_PWD` | 加密密码 | Task 2 必填 |

---

## 七、重要约定

### 检索策略
- **EmbeddingRetriever**（默认）：自定义 `SiliconFlowEmbeddings` 调用 `qwen3-embedding:8b`，支持可选 Reranker 重排序
- **PageIndexRetriever**：关键词分词 + 标题/内容倒排索引，轻量无 API 费用
- 通过 `.env` 中 `RETRIEVER_MODE` 切换

### Embedding 实现
- 使用自定义 `SiliconFlowEmbeddings` 类（直接 HTTP 请求），而非 LangChain 的 `OpenAIEmbeddings`（避免参数兼容问题）
- 构建索引导入 ChromaDB，持久化到 `chroma_db/`

### Git 管理
- `chroma_db/` 不提交（每人本地重建）
- `.env` 不提交
- `docs_cache/` 提交（共享缓存，避免重复抓取）

### LLM 费用
- 自动追踪：通过 LangChain `BaseCallbackHandler` 捕获每次调用的 token 消耗
- Web UI 可查看实时报告
- DeepSeek V4 Flash 定价：$0.14/1M input, $0.28/1M output

---

## 八、进度

- [x] Task 1：测试场景自动生成（14 功能点，65 场景）
- [x] Web UI：可视化 + 实时进度条
- [x] 双检索策略 + Reranker
- [ ] Task 2：智能测试智能体
- [ ] 变异测试
- [ ] 评估对比实验
