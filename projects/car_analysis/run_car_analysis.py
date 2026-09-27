# -*- coding: utf-8 -*-
"""
HiveFlow 真实项目：二手车市场分析 Agent
========================================
使用 HiveFlow (HiveMindApp) 认知编排，让本地 LLM (Ollama qwen2.5-coder:14b)
对真实二手车数据集自动规划多步任务，由 Skill Agents 协作完成数据分析并产出报告。

链路：用户输入 → IntentParser(LLM) → CognitiveOrchestrator(LLM 规划 TaskGraph)
      → dynamic_orch 调度 DAG → analyze_data/summarize Skill Agents(blackboard 协作)
      → 最终分析报告

运行：
  cd E:\\HiveFlow\\projects\\car_analysis
  python run_car_analysis.py
"""
import asyncio
import csv
import json
import logging
import statistics
from collections import Counter

from hiveflow import HiveFlowConfig

from app import HiveMindApp, HiveMindConfig
from llm.ollama_client import OllamaLLMClient
from memory.vector_store import VectorStore

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# 数据层：真实二手车数据集（纯标准库分析，零依赖）
# ---------------------------------------------------------------------------
CSV_PATH = r"E:\爬取二手车交易数据并进行预处理及汽车数据\data\cleaned\dongchedi_cars_cleaned.csv"


class InMemoryVectorStore(VectorStore):
    """轻量向量存储（embedding 由 Ollama 提供）"""

    def __init__(self, embedding_fn):
        self.embedding_fn = embedding_fn

    async def add_texts(self, texts, metadatas=None, ids=None):
        return ids or [f"doc_{i}" for i in range(len(texts))]

    async def similarity_search(self, query, k=5, filter_fn=None):
        return []

    async def delete(self, ids):
        pass


def load_cars():
    # utf-8-sig：去除 CSV 的 UTF-8 BOM，避免首列键名被污染（如 \ufeffbrand）
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def analyze_dataset() -> dict:
    """对二手车数据做全套统计（真实计算）。"""
    rows = load_cars()
    n = len(rows)
    if n == 0:
        return {"error": "dataset empty"}

    def num(row, key):
        try:
            v = row.get(key, "")
            if v in ("", None, "未知"):
                return None
            return float(str(v).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    prices = [p for p in (num(r, "price") for r in rows) if p is not None]
    sales = [s for s in (num(r, "sales_volume") for r in rows) if s is not None]
    brands = Counter(r["brand"] for r in rows if r.get("brand") and r["brand"] != "未知")
    energy = Counter(r["energy_type"] for r in rows if r.get("energy_type") and r["energy_type"] != "未知")
    segments = Counter(r["price_segment"] for r in rows if r.get("price_segment"))

    # 品牌 TOP10（按记录数），附平均价
    brand_top = []
    for b, cnt in brands.most_common(10):
        bp = [p for r in rows if r.get("brand") == b for p in [num(r, "price")] if p is not None]
        brand_top.append({"brand": b, "count": cnt, "avg_price": round(statistics.mean(bp), 2) if bp else None})

    # 销量 TOP5 车型
    by_sales = sorted(
        (r for r in rows if num(r, "sales_volume") is not None),
        key=lambda r: num(r, "sales_volume"), reverse=True,
    )[:5]
    top_sales = [
        {
            "model": r.get("model", ""),
            "brand": r.get("brand", ""),
            "price": num(r, "price"),
            "sales_volume": int(num(r, "sales_volume")),
            "rating": num(r, "rating"),
        }
        for r in by_sales
    ]

    energy_dist = [{"type": k, "count": v, "pct": round(v * 100.0 / n, 1)} for k, v in energy.most_common()]
    seg_dist = [{"segment": k, "count": v, "pct": round(v * 100.0 / n, 1)} for k, v in segments.most_common()]

    overview = {
        "total_records": n,
        "total_brands": len(brands),
        "total_energy_types": len(energy),
        "price_min": round(min(prices), 2) if prices else None,
        "price_max": round(max(prices), 2) if prices else None,
        "price_avg": round(statistics.mean(prices), 2) if prices else None,
        "price_median": round(statistics.median(prices), 2) if prices else None,
        "sales_total": int(sum(sales)) if sales else None,
        "sales_avg": round(statistics.mean(sales), 1) if sales else None,
    }

    return {
        "overview": overview,
        "top_brands": brand_top,
        "top_sales": top_sales,
        "energy_distribution": energy_dist,
        "price_segment_distribution": seg_dist,
    }


# ---------------------------------------------------------------------------
# Skill Agent Handlers
# ---------------------------------------------------------------------------
async def analyze_data_handler(ecm, view):
    """[analyze_data] 真实执行数据分析（读 CSV → 统计）。"""
    print(f"    [analyze_data] 执行数据分析 (node={ecm.intent_id}) ...")
    analysis = analyze_dataset()
    await view.put(f"hivemind:result:{ecm.intent_id}", analysis)
    print(f"    [analyze_data] 完成：{analysis['overview']['total_records']} 条记录 / "
          f"{analysis['overview']['total_brands']} 个品牌 / 均价 {analysis['overview']['price_avg']} 万")
    return analysis


async def summarize_handler(ecm, view):
    """[summarize] 汇总上游分析结果，生成最终报告。"""
    print(f"    [summarize] 生成最终分析报告 (node={ecm.intent_id}) ...")
    deps = ecm.payload.get("input_keys", {})
    analysis = {}
    inherited_answer = None
    for _name, key in deps.items():
        try:
            candidate = await view.get(key)
        except (KeyError, PermissionError):
            continue
        if isinstance(candidate, dict):
            if "overview" in candidate:
                analysis = candidate
            elif "answer" in candidate and inherited_answer is None:
                inherited_answer = candidate["answer"]  # 上游已是报告 → 直接透传
    if inherited_answer:
        answer = inherited_answer
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}
    if not analysis:
        answer = "未能获取上游分析结果。"
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}

    ov = analysis["overview"]
    seg = "\n".join(
        f"  - {s['segment']}: {s['count']} 辆 ({s['pct']}%)"
        for s in analysis["price_segment_distribution"]
    )
    en = "\n".join(
        f"  - {e['type']}: {e['count']} 辆 ({e['pct']}%)"
        for e in analysis["energy_distribution"]
    )
    brands = "\n".join(
        f"  - {b['brand']}: {b['count']} 辆，均价 {b['avg_price']} 万"
        for b in analysis["top_brands"]
    )
    sales = "\n".join(
        f"  - {s['brand']} {s['model']}：销量 {s['sales_volume']}，价格 {s['price']} 万，评分 {s['rating']}"
        for s in analysis["top_sales"]
    )

    answer = f"""# 二手车市场分析报告（HiveFlow 多 Agent 生成）

## 一、数据概况
- 样本量：{ov['total_records']} 条在售车源
- 品牌数：{ov['total_brands']} 个
- 价格区间：{ov['price_min']} ~ {ov['price_max']} 万元
- 均价：{ov['price_avg']} 万元（中位数 {ov['price_median']} 万）
- 总销量（样本）：{ov['sales_total']}

## 二、价格段分布
{seg}

## 三、能源类型分布
{en}

## 四、品牌 TOP10（按在售车源数）
{brands}

## 五、销量 TOP5 车型
{sales}

## 六、核心结论
1. 样本均价 {ov['price_avg']} 万、中位数 {ov['price_median']} 万，说明市场以中低价位车源为主；
2. 销量最高的车型为 {analysis['top_sales'][0]['brand']} {analysis['top_sales'][0]['model']}（销量 {analysis['top_sales'][0]['sales_volume']}）；
3. 能源结构以 {'、'.join(e['type'] for e in analysis['energy_distribution'][:2])} 为主。
"""
    await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
    return {"answer": answer}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
async def main():
    print("=" * 64)
    print("HiveFlow 真实项目：二手车市场分析 Agent（本地 LLM 认知编排）")
    print("=" * 64)

    # 真实 LLM：qwen2.5-coder:14b（Ollama 本地），JSON 稳定性好
    llm = OllamaLLMClient(model="qwen2.5-coder:14b", base_url="http://localhost:11434")
    embed_llm = OllamaLLMClient(model="andersc/qwen3-embedding:4b", base_url="http://localhost:11434")

    skills = {
        "analyze_data": "Analyze the used car dataset: compute overview, price statistics, brand ranking, "
                        "energy type distribution and top sales models. Returns structured analysis JSON.",
        "summarize": "Collect upstream analysis results and write the final markdown report with key findings.",
    }

    config = HiveMindConfig(
        hiveflow_config=HiveFlowConfig(blackboard_type="memory", max_audit_entries=500),
        llm=llm,
        embedding_llm=embed_llm,
        vector_store=InMemoryVectorStore(embedding_fn=embed_llm.embed),
        skill_registry=skills,
        enable_result_cleanup=False,
        max_replan_attempts=2,
    )
    app = HiveMindApp(config)
    await app.start()

    await app.create_skill_agent(
        "analyze_data", "analyze-agent", analyze_data_handler,
        read_keys=set(), write_keys={"hivemind:result:*"},
    )
    await app.create_skill_agent(
        "summarize", "sum-agent", summarize_handler,
        read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"},
    )

    goal = "分析二手车数据集：统计数据概况、价格分布、品牌 TOP10、能源类型占比和销量 TOP5 车型，并生成完整分析报告"

    # 1) 先看 LLM 规划效果
    print("\n[1/2] LLM 规划 (plan_only) ...")
    try:
        plan = await app.plan_only(goal, conversation_id="car-analysis-1")
        graph = plan.get("plan", {})
        print("  规划结果（LLM 生成 TaskGraph）:")
        for name, node in graph.items():
            print(f"    - {name}: task={node.get('task')}, depends_on={node.get('depends_on')}")
        print(f"  规划状态: {plan.get('status')}")
    except Exception as e:
        print(f"  规划失败: {e}")

    # 2) 全链路执行
    print("\n[2/2] 端到端执行 (run_query) ...")
    result = await app.run_query(goal, conversation_id="car-analysis-1")

    print("\n--- 最终答案 ---")
    print(result["answer"])
    print(f"\n--- 元信息 ---")
    print(f"intent_id: {result['intent_id']}")
    print(f"status: {result.get('status')}")

    # 审计轨迹
    audit = app.blackboard._audit_log[-8:]
    if audit:
        print("\n最近审计轨迹 (HiveFlow blackboard):")
        for entry in audit:
            print(f"  {entry}")

    await app.shutdown()
    print("\n项目运行完成。")


if __name__ == "__main__":
    asyncio.run(main())
