import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load_features():
    from src.web_ui.main import FEATURES_FILE, DEFAULT_FEATURES_FILE
    from src.task1_scenario_generation.models import FeaturePoint

    path = FEATURES_FILE if os.path.exists(FEATURES_FILE) else DEFAULT_FEATURES_FILE
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [FeaturePoint.model_validate(item) for item in data]


def cmd_task2(args):
    from src.task2_testing_agent.agent import TestingAgent
    from src.task1_scenario_generation.models import TestScenario

    features = _load_features()
    if not features:
        print("No test scenarios found. Run the Web UI and generate scenarios first.")
        return

    all_scenarios: list[tuple[str, TestScenario]] = []
    for f in features:
        for s in f.scenarios:
            all_scenarios.append((f.name, s))

    target_scenarios = all_scenarios
    if args.scenario:
        target_scenarios = [
            (fn, s) for fn, s in all_scenarios if args.scenario.lower() in s.name.lower()
        ]
        if not target_scenarios:
            print(f"No scenarios matching: {args.scenario}")
            return

    agent = TestingAgent(headless=args.headless)
    results = []

    for feat_name, scenario in target_scenarios:
        print(f"\n{'='*60}")
        print(f"Executing: [{feat_name}] {scenario.name}")
        print(f"{'='*60}")
        result = agent.run_scenario(scenario)
        status = "PASS" if result.get("rule_based", {}).get("passed") else "FAIL"
        print(f"  Status: {status}")
        print(f"  Rule-based: {result.get('rule_based', {}).get('passed')}")
        print(f"  LLM-based: {result.get('llm_based', {}).get('passed')}")
        results.append({
            "feature": feat_name,
            "scenario": scenario.name,
            "status": status,
            "rule_passed": result.get("rule_based", {}).get("passed"),
            "llm_passed": result.get("llm_based", {}).get("passed"),
        })

    print(f"\n{'='*60}")
    print(f"Batch Summary: {sum(1 for r in results if r['status']=='PASS')}/{len(results)} passed")
    for r in results:
        print(f"  {'PASS' if r['status']=='PASS' else 'FAIL'} {r['feature']} / {r['scenario']}")


def cmd_web():
    import uvicorn
    uvicorn.run(
        "src.web_ui.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=[".venv", "chroma_db", "docs_cache", "tmp"],
    )


def build_parser():
    parser = argparse.ArgumentParser(description="4gaBoard Test Agent")
    sub = parser.add_subparsers(dest="command")

    task2_parser = sub.add_parser("task2", help="Run Task 2 testing agent via CLI")
    task2_parser.add_argument("--scenario", "-s", help="Scenario name filter")
    task2_parser.add_argument("--all", action="store_true", help="Run all scenarios")
    task2_parser.add_argument("--headless", action="store_true", default=True,
                              help="Run browser headless (default: True)")
    task2_parser.add_argument("--no-headless", action="store_false", dest="headless",
                              help="Show browser window")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "task2":
        cmd_task2(args)
    else:
        cmd_web()
