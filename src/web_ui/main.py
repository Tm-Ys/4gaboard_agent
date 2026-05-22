import json
import os
from typing import List
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from src.task1_scenario_generation.models import FeaturePoint, TestScenario
from src.task1_scenario_generation.docs_scraper import scrape_all_docs
from src.task1_scenario_generation.knowledge_base import get_llm
from src.task1_scenario_generation.scenario_generator import extract_features, generate_scenarios, _clean_json
from src.retrieval.factory import create_retriever, RETRIEVER_MODE_KEY

app = FastAPI(title="4gaBoard Test Agent")

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")
jinja_env = Environment(loader=FileSystemLoader(templates_dir), auto_reload=False)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

FEATURES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "features.json")
DEFAULT_FEATURES_FILE = os.path.join(os.path.dirname(__file__), "default_features.json")
TESTSCENE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "testscene")

features: List[FeaturePoint] = []
task2_results: dict = {}


def _load_features_from(source: str) -> list[FeaturePoint]:
    if not os.path.exists(source):
        return []
    try:
        with open(source) as f:
            data = json.load(f)
        return [FeaturePoint.model_validate(item) for item in data]
    except Exception:
        return []


def _load_features():
    global features
    source = FEATURES_FILE if os.path.exists(FEATURES_FILE) else DEFAULT_FEATURES_FILE
    features = _load_features_from(source)


def _save_features():
    os.makedirs(TESTSCENE_DIR, exist_ok=True)
    data = [feat.model_dump() for feat in features]
    with open(FEATURES_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    from datetime import datetime
    ts = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    archive_path = os.path.join(TESTSCENE_DIR, f"testscene_{ts}.json")
    with open(archive_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_load_features()

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

task2_progress = {
    "status": "idle",
    "current_scenario": "",
    "detail": "",
    "progress_pct": 0,
    "scenario_index": 0,
    "total_scenarios": 0,
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

    set_progress("running", "探索演示站", "正在爬取演示站实际 UI 元素...", 15)
    from src.task1_scenario_generation.demo_crawler import get_demo_ui_context, clear_demo_ui_cache
    clear_demo_ui_cache()
    demo_ui = get_demo_ui_context()

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
        generate_scenarios(feat, retriever, demo_ui_context=demo_ui)

    features = extracted
    _save_features()
    total = sum(len(f.scenarios) for f in features)
    set_progress("done", "完成", f"共生成 {len(extracted)} 个功能点、{total} 个测试场景", 100)
    return len(extracted)


def _run_scenario_batch(scenario_index: int, headless: bool = True):
    global task2_results
    if not features or scenario_index < 0 or scenario_index >= sum(len(f.scenarios) for f in features):
        return {"status": "error", "error": "Invalid scenario index"}

    flat = [(f, s) for f in features for s in f.scenarios]
    feature, scenario = flat[scenario_index]

    task2_progress.update(
        status="running",
        current_scenario=scenario.name,
        detail=f"正在执行测试场景: {scenario.name}",
        progress_pct=50,
        scenario_index=scenario_index,
        total_scenarios=len(flat),
    )

    from src.task2_testing_agent.agent import TestingAgent
    agent = TestingAgent(headless=headless)
    result = agent.run_scenario(scenario)

    task2_results[scenario.name] = result
    task2_progress.update(
        status="done" if result.get("status") == "completed" else "error",
        detail=f"场景「{scenario.name}」执行{'完成' if result.get('status') == 'completed' else '失败'}",
        progress_pct=100,
    )
    return result


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


@app.get("/api/testscene/list")
async def testscene_list():
    os.makedirs(TESTSCENE_DIR, exist_ok=True)
    files = sorted(
        [f for f in os.listdir(TESTSCENE_DIR) if f.endswith(".json")],
        reverse=True,
    )
    entries = []
    for f in files:
        path = os.path.join(TESTSCENE_DIR, f)
        try:
            size = os.path.getsize(path)
            with open(path) as fh:
                data = json.load(fh)
            total_scenarios = sum(len(feat.get("scenarios", [])) for feat in data)
            entries.append({
                "filename": f,
                "size": size,
                "features": len(data),
                "scenarios": total_scenarios,
                "active": os.path.exists(FEATURES_FILE) and os.path.samefile(path, FEATURES_FILE),
            })
        except Exception:
            entries.append({"filename": f, "error": True})
    return {"files": entries}


@app.post("/api/testscene/load")
async def testscene_load(filename: str = Form(...)):
    global features
    # Allow path traversal only within testscene dir
    safe_path = os.path.normpath(os.path.join(TESTSCENE_DIR, os.path.basename(filename)))
    if not safe_path.startswith(os.path.normpath(TESTSCENE_DIR)):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="File not found")

    loaded = _load_features_from(safe_path)
    if not loaded:
        raise HTTPException(status_code=400, detail="Failed to load features")

    features = loaded
    _save_features()
    return {
        "status": "ok",
        "features": len(features),
        "scenarios": sum(len(f.scenarios) for f in features),
    }


@app.get("/api/task2/scenarios")
async def task2_list_scenarios():
    flat = []
    for fi, f in enumerate(features):
        for si, s in enumerate(f.scenarios):
            flat.append({
                "index": len(flat),
                "feature_name": f.name,
                "scenario": s.model_dump(),
            })
    return {"scenarios": flat, "total": len(flat)}


@app.get("/api/task2/progress")
async def task2_get_progress():
    return task2_progress


@app.get("/api/task2/results")
async def task2_get_results():
    return task2_results


@app.post("/api/task2/run")
async def task2_run_scenario(scenario_index: int = Form(...), headless: bool = Form(True)):
    import asyncio
    try:
        result = await asyncio.to_thread(_run_scenario_batch, scenario_index, headless)
        return {"status": "ok", "result": result}
    except Exception as e:
        task2_progress.update(status="error", detail=str(e), progress_pct=0)
        raise HTTPException(status_code=500, detail=str(e))


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

    llm = get_llm()
    tmpl = (
        '请为功能点"{name}"生成一个测试场景。'
        "参考以下文档内容：\n{ctx}\n"
        '返回 JSON 格式：{{"name": "...", "description": "...", '
        '"steps": [{{"action": "...", "target": "..."}}], '
        '"expectations": [{{"description": "..."}}]}}'
    )
    prompt = tmpl.format(name=feature_name, ctx=context)
    response = llm.invoke(prompt)
    data = json.loads(_clean_json(response.content))
    scenario = TestScenario(**data)
    return scenario.model_dump()
