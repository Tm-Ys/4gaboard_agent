import json
import os
from typing import List
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from src.task1_scenario_generation.models import FeaturePoint, TestScenario
from src.task1_scenario_generation.docs_scraper import scrape_all_docs
from src.task1_scenario_generation.knowledge_base import llm_invoke
from src.task1_scenario_generation.scenario_generator import extract_features, generate_scenarios, _clean_json
from src.retrieval.factory import create_retriever, RETRIEVER_MODE_KEY

app = FastAPI(title="4gaBoard Test Agent")

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")
jinja_env = Environment(loader=FileSystemLoader(templates_dir), auto_reload=False)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

features: List[FeaturePoint] = []

# 全局进度追踪
pipeline_progress = {
    "status": "idle",
    "current_step": "",
    "detail": "",
    "progress_pct": 0,
    "total_features": 0,
    "current_feature": 0,
    "current_scenario": "",
}


def set_progress(status: str, current_step: str = "", detail: str = "", pct: int = 0, **kw):
    pipeline_progress.update(
        status=status, current_step=current_step, detail=detail, progress_pct=pct, **kw
    )


def _build_feature_context(pages: List[dict]) -> str:
    blocks = []
    for p in pages:
        content = p.get("content", "")
        blocks.append(
            f"=== {p['title']} ===\nURL: {p['url']}\n{content[:800]}..."
        )
    return "\n\n".join(blocks)


def _run_pipeline():
    global features

    set_progress("running", "读取文档", "正在加载已缓存的用户手册...", 5)
    pages = scrape_all_docs()

    set_progress("running", "构建索引", f"正在构建 {type(create_retriever()).__name__} 索引...", 10)
    retriever = create_retriever()
    retriever.build_index(pages)

    set_progress("running", "LLM 分析", "正在调用 LLM 从文档中提取功能点...", 20)
    context = _build_feature_context(pages)
    extracted = extract_features(context)
    if not extracted:
        raise RuntimeError("未从文档中提取出任何功能点")

    set_progress("running", "生成场景", f"已提取 {len(extracted)} 个功能点，正在逐個生成测试场景...", 30,
                 total_features=len(extracted), current_feature=0)

    for i, feat in enumerate(extracted):
        pct = 30 + int((i + 1) / len(extracted) * 65)
        set_progress("running", "生成场景",
                     f"[{i+1}/{len(extracted)}] 正在为「{feat.name}」生成测试场景...",
                     pct, current_feature=i + 1)
        generate_scenarios(feat, retriever)

    features = extracted
    total = sum(len(f.scenarios) for f in features)
    set_progress("done", "完成", f"共生成 {len(extracted)} 个功能点、{total} 个测试场景", 100)
    return len(extracted)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    mode = os.getenv(RETRIEVER_MODE_KEY, "embedding")
    template = jinja_env.get_template("index.html")
    html = template.render(features=features, retriever_mode=mode)
    return HTMLResponse(html)


@app.post("/scrape-and-generate")
async def scrape_and_generate():
    import asyncio
    set_progress("running", "准备", "正在启动生成流程...", 0)
    try:
        count = await asyncio.to_thread(_run_pipeline)
        return {
            "status": "ok",
            "feature_count": count,
            "retriever_mode": os.getenv(RETRIEVER_MODE_KEY, "embedding"),
        }
    except Exception as e:
        set_progress("error", "出错了", str(e), 0)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/progress")
async def get_progress():
    return pipeline_progress


@app.get("/api/features")
async def get_features():
    return [f.model_dump() for f in features]


@app.get("/api/cost-report")
async def cost_report():
    from src.utils.llm_cost_tracker import get_tracker
    tracker = get_tracker()
    return {
        "report_text": tracker.report(),
        "cost": tracker.get_cost(),
        "balance": tracker.get_balance(),
    }


@app.post("/api/cost-reset")
async def cost_reset():
    from src.utils.llm_cost_tracker import get_tracker
    get_tracker().reset()
    return {"status": "ok"}


@app.post("/api/generate-single")
async def generate_single(feature_name: str = Form(...)):
    from src.retrieval.factory import create_retriever
    from src.task1_scenario_generation.docs_scraper import load_from_cache

    pages = load_from_cache()
    retriever = create_retriever()
    if pages:
        retriever.build_index(pages)

    docs = retriever.retrieve(feature_name, k=3)
    context = "\n".join([d["content"] for d in docs])

    tmpl = (
        '请为功能点"{name}"生成一个测试场景。'
        "参考以下文档内容：\n{ctx}\n"
        '返回 JSON 格式：{{"name": "...", "description": "...", '
        '"steps": [{{"action": "...", "target": "..."}}], '
        '"expectations": [{{"description": "..."}}]}}'
    )
    prompt = tmpl.format(name=feature_name, ctx=context)
    from langchain_core.messages import HumanMessage
    response = llm_invoke([HumanMessage(content=prompt)])
    data = json.loads(_clean_json(response.content))
    scenario = TestScenario(**data)
    return scenario.model_dump()
