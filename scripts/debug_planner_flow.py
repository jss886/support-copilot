"""
Planner 信息流追踪脚本：观察复杂任务从分解到综合的完整信息流向。

对比 debug_planner.py 侧重"节点边界 state 快照"，本脚本聚焦六个关键信息流：
  1. 路由决策流：orchestrator 输出 intent/complexity → 触发 planner 的条件
  2. 计划分解流：user_query → planner LLM → 解析后的 sub_tasks DAG
  3. 依赖注入流：前置子任务结果 → _build_worker_query → 后置子任务输入
  4. Worker 内部流：每个子任务内部 retrieval→quality_gate→answer 的 state 变化
  5. 结果汇总流：execution_results → ordered_results → plan_results
  6. 答案综合流：plan_results → synthesizer LLM → synthesized_answer

用法:
    # 基础用法：追踪复杂问题的完整信息流
    python scripts/debug_planner_flow.py "Redis 集群主从同步延迟排查，另外查 pg 最大连接数"

    # 逐步模式，每步暂停
    python scripts/debug_planner_flow.py --step "Nginx 502 排查 + 数据库连接池配置"

    # 显示 Worker 内部状态变化（retrieval → quality_gate → answer）
    python scripts/debug_planner_flow.py --verbose "如何排查微服务雪崩"

    # 只追踪信息流，不实际执行
    python scripts/debug_planner_flow.py --flow-only "对比 asyncio 和 goroutine"

    # 强制走 planner（即使 orchestrator 判断为 simple）
    python scripts/debug_planner_flow.py --force "什么是 Redis"

    # JSON 输出模式
    python scripts/debug_planner_flow.py --json "分布式追踪方案"

选项:
    --force      强制走 planner 链路
    --step       逐步模式，每完成一个信息流阶段暂停
    --verbose    显示 Worker 内部各节点的 state 变化
    --flow-only  只追踪信息流结构，不执行 LLM 调用
    --json       以 JSON 格式输出
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# 修复 Windows GBK 终端输出中文/特殊字符
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from supportAgents.graph import create_initial_state
from supportAgents.graph.state import SupportAgentState
from supportAgents.agents import run_orchestrator

# -- ANSI 颜色常量 --
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE_BOLD = "\033[1;97m"
RESET = "\033[0m"

INDENT = "  "
FLOW_ARROW = f"{DIM}→{RESET}"
FLOW_DOWN = f"{DIM}↓{RESET}"


# ============================================================================
# 工具函数
# ============================================================================


def _sep(char: str = "─", width: int = 72) -> str:
    return char * width


def _header(title: str) -> str:
    bar = _sep("━")
    return f"\n{BOLD}{CYAN}{bar}{RESET}\n{BOLD}{CYAN}  {title}{RESET}\n{BOLD}{CYAN}{bar}{RESET}"


def _stage(stage_num: str, title: str) -> str:
    return f"\n{BOLD}{WHITE_BOLD}[{stage_num}]{RESET} {BOLD}{title}{RESET}"


def _kv(key: str, value: object, color: str = "") -> str:
    val_str = str(value)
    if color:
        val_str = f"{color}{val_str}{RESET}"
    return f"{INDENT}{DIM}{key}:{RESET} {val_str}"


def _badge(text: str, color: str = GREEN) -> str:
    return f"{color}{BOLD}[{text}]{RESET}"


def _arrow(src: str, dst: str) -> str:
    return f"{INDENT}{YELLOW}{src}{RESET} {FLOW_ARROW} {CYAN}{dst}{RESET}"


def _flow_box(lines: list[str]) -> str:
    bar = _sep("·", 68)
    inner = "\n".join(lines)
    return f"{DIM}┌{bar}{RESET}\n{inner}\n{DIM}└{bar}{RESET}"


def _elapsed(start: float) -> str:
    t = time.time() - start
    if t < 1:
        return f"{t*1000:.0f}ms"
    return f"{t:.2f}s"


def _truncate(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"{DIM}...({len(text)}字符){RESET}"


def _wait(json_mode: bool):
    if json_mode:
        return
    try:
        input(f"\n  {DIM}[Enter] 继续下一步 (Ctrl+C 退出) ...{RESET}")
    except (EOFError, KeyboardInterrupt):
        print("\n  已退出")
        sys.exit(0)


# ============================================================================
# 流 1: 路由决策流 — orchestrator → planner gate
# ============================================================================


def trace_routing(state: dict, flow_only: bool = False) -> dict:
    """追踪 orchestrator 的路由决策：展示 intent/complexity 判定过程。"""
    result = {
        "flow": "routing",
        "user_query": state.get("user_query", ""),
        "intent": state.get("intent", "?"),
        "complexity": state.get("complexity", "simple"),
        "route_reason": state.get("route_reason", ""),
        "triggers_planner": state.get("complexity") == "complex",
    }
    return result


def render_routing(data: dict, mode: str = "text") -> str:
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    intent = data["intent"]
    complexity = data["complexity"]
    triggers_planner = data["triggers_planner"]

    intent_badge = {
        "knowledge_qa": _badge("KNOWLEDGE_QA", BLUE),
        "tool_only": _badge("TOOL_ONLY", YELLOW),
        "direct_answer": _badge("DIRECT", GREEN),
        "fallback": _badge("FALLBACK", RED),
    }.get(intent, str(intent))

    complexity_badge = _badge("COMPLEX → 触发 Planner", YELLOW) if triggers_planner else _badge("SIMPLE", GREEN)

    lines = [
        _stage("流 1", "路由决策流: orchestrator → planner gate"),
        _kv("用户问题", _truncate(data["user_query"])),
        _kv("意图分类", intent_badge),
        _kv("复杂度", complexity_badge),
        _kv("判断依据", data["route_reason"]),
    ]

    if triggers_planner:
        lines.append("")
        lines.append(_arrow("orchestrator","planner"))
    else:
        lines.append("")
        lines.append(f"{INDENT}{YELLOW}planner 不触发 (complexity=simple)，走普通链路{RESET}")

    return "\n".join(lines)


# ============================================================================
# 流 2: 计划分解流 — user_query → planner LLM → sub_tasks DAG
# ============================================================================


def trace_planning(state: dict, flow_only: bool = False) -> dict:
    """追踪 planner 的分解过程：原始问题 → 子任务 DAG。"""
    plan = state.get("plan") or {}
    sub_tasks = plan.get("sub_tasks", [])
    plan_reason = plan.get("plan_reason", "")

    dag_edges: list[tuple[int, int]] = []
    for i, st in enumerate(sub_tasks):
        for dep in st.get("depends_on", []):
            dag_edges.append((dep, i))

    from supportAgents.agents.planner_agent import _topological_order
    order = _topological_order(sub_tasks)

    return {
        "flow": "planning",
        "original_query": state.get("user_query", ""),
        "plan_reason": plan_reason,
        "sub_task_count": len(sub_tasks),
        "sub_tasks": [
            {
                "index": i,
                "sub_query": st.get("sub_query", ""),
                "sub_intent": st.get("sub_intent", ""),
                "depends_on": st.get("depends_on", []),
            }
            for i, st in enumerate(sub_tasks)
        ],
        "dag_edges": dag_edges,
        "topological_order": order,
    }


def render_planning(data: dict, mode: str = "text") -> str:
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    sub_tasks = data["sub_tasks"]
    dag_edges = data["dag_edges"]
    order = data["topological_order"]

    intent_color = {
        "knowledge_qa": BLUE,
        "tool_only": YELLOW,
        "direct_answer": GREEN,
    }

    lines = [
        _stage("流 2", "计划分解流: user_query → planner LLM → sub_tasks DAG"),
        _kv("分解思路", data["plan_reason"]),
        _kv("子任务数", len(sub_tasks)),
        "",
        f"{INDENT}{BOLD}DAG 依赖关系图:{RESET}",
    ]

    # 绘制 DAG
    for i, st in enumerate(sub_tasks):
        deps = st["depends_on"]
        sub_intent = st["sub_intent"]
        color = intent_color.get(sub_intent, RESET)

        dep_str = ""
        if deps:
            dep_labels = [f"T{d}" for d in deps]
            dep_str = f" {DIM}← 依赖 [{', '.join(dep_labels)}]{RESET}"

        query_preview = _truncate(st["sub_query"], 90)
        lines.append(f"{INDENT}{BOLD}T{i}{RESET} [{color}{sub_intent}{RESET}]{dep_str}")
        lines.append(f"{INDENT}{INDENT}{query_preview}")

    # 绘制拓扑序
    if order:
        arrows = f" {FLOW_ARROW} ".join(f"{CYAN}T{i}{RESET}" for i in order)
        lines.append("")
        lines.append(f"{INDENT}{BOLD}拓扑执行序:{RESET}")
        lines.append(f"{INDENT}{arrows}")

    # 绘制信息流箭头
    if dag_edges:
        lines.append("")
        lines.append(f"{INDENT}{BOLD}信息流向 (依赖注入):{RESET}")
        for src, dst in dag_edges:
            src_query = _truncate(sub_tasks[src]["sub_query"], 50)
            lines.append(f"{INDENT}{DIM}T{src} 结果{RESET} {FLOW_ARROW} {DIM}T{dst} 的 worker_query{RESET}")
            lines.append(f"{INDENT}{INDENT}{DIM}└ {src_query}{RESET}")

    return "\n".join(lines)


# ============================================================================
# 流 3: 依赖注入流 — 前置结果 → _build_worker_query → 子任务输入
# ============================================================================


def trace_dependency_injection(
    state: dict,
    task_id: int,
    sub_task: dict,
    execution_results: dict,
    flow_only: bool = False,
) -> dict:
    """追踪单个子任务的依赖注入过程。"""
    depends_on = sub_task.get("depends_on", [])
    sub_query = sub_task.get("sub_query", "")

    dependency_blocks: list[dict] = []
    for dep_idx in depends_on:
        dep_result = execution_results.get(dep_idx)
        if not dep_result:
            continue
        dep_text = dep_result.get("result", "")
        dep_error = dep_result.get("error", "")
        if dep_text:
            dependency_blocks.append({
                "source_task": dep_idx,
                "type": "result",
                "content_preview": dep_text[:200],
            })
        elif dep_error:
            dependency_blocks.append({
                "source_task": dep_idx,
                "type": "error",
                "content_preview": dep_error[:200],
            })

    # 模拟 worker_query 构造（不修改 state，只追踪）
    if dependency_blocks:
        injected_parts = []
        for block in dependency_blocks:
            if block["type"] == "result":
                injected_parts.append(f"[前置任务 {block['source_task']}] {block['content_preview'][:100]}")
            else:
                injected_parts.append(f"[前置任务 {block['source_task']} 失败] {block['content_preview'][:100]}")
        worker_query_preview = "\n".join(injected_parts) + f"\n当前子问题：{sub_query}"
    else:
        worker_query_preview = sub_query

    return {
        "flow": "dependency_injection",
        "task_id": task_id,
        "sub_query": sub_query,
        "depends_on": depends_on,
        "dependency_blocks": dependency_blocks,
        "has_injected_context": len(dependency_blocks) > 0,
        "worker_query_preview": worker_query_preview[:300],
    }


def render_dependency_injection(data: dict, mode: str = "text") -> str:
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    task_id = data["task_id"]
    has_injected = data["has_injected_context"]

    lines = [
        _stage(f"  依赖注入", f"子任务 T{task_id} 的输入构造"),
        _kv("子问题", _truncate(data["sub_query"], 100)),
        _kv("依赖任务", data["depends_on"] if data["depends_on"] else "(无)"),
    ]

    if has_injected:
        lines.append(f"{INDENT}{BOLD}注入的前置结果:{RESET}")
        for block in data["dependency_blocks"]:
            src = block["source_task"]
            typ = block["type"]
            content = _truncate(block["content_preview"], 120)
            badge = _badge("OK", GREEN) if typ == "result" else _badge("FAILED", RED)
            lines.append(f"{INDENT}{INDENT}{DIM}T{src}{RESET} {badge} {FLOW_ARROW} {content}")

        lines.append("")
        lines.append(f"{INDENT}{BOLD}拼接后的 worker_query:{RESET}")
        # 分行展示拼接结果
        for line in data["worker_query_preview"].split("\n"):
            if line.startswith("[前置任务"):
                lines.append(f"{INDENT}{INDENT}{MAGENTA}{line}{RESET}")
            elif line.startswith("当前子问题"):
                lines.append(f"{INDENT}{INDENT}{CYAN}{line}{RESET}")
            else:
                lines.append(f"{INDENT}{INDENT}{DIM}{line}{RESET}")
    else:
        lines.append(f"{INDENT}{DIM}无前置依赖，worker_query 直接使用子问题原文{RESET}")

    return "\n".join(lines)


# ============================================================================
# 流 4: Worker 内部流 — retrieval → quality_gate → answer (verbose 模式)
# ============================================================================


def trace_worker_internal(
    task_id: int,
    sub_intent: str,
    worker_state: SupportAgentState,
    flow_only: bool = False,
) -> dict:
    """追踪单个 worker 内部的执行链路。"""
    from supportAgents.agents.answer_agent import run_answer_agent
    from supportAgents.agents.quality_gate import run_quality_gate
    from supportAgents.agents.retrieval_agent import run_retrieval_agent
    from supportAgents.agents.action_agent import run_action_agent

    steps: list[dict] = []

    if sub_intent == "knowledge_qa":
        # retrieval → quality_gate → answer
        t0 = time.time()
        s1 = run_retrieval_agent(worker_state)
        retrieval_payload = s1.get("retrieval") or {}
        items = retrieval_payload.get("items", [])
        steps.append({
            "node": "retrieval",
            "elapsed": _elapsed(t0),
            "query": retrieval_payload.get("query", ""),
            "rewritten_queries": retrieval_payload.get("rewritten_queries", []),
            "recall_count": len(items),
            "top_scores": [round(it.get("score", 0), 4) for it in items[:3]],
            "error": s1.get("error", ""),
        })

        if s1.get("error"):
            return {"flow": "worker_internal", "task_id": task_id, "intent": sub_intent, "steps": steps, "final_answer": "", "error": s1["error"]}

        t1 = time.time()
        s2 = run_quality_gate(s1)
        steps.append({
            "node": "quality_gate",
            "elapsed": _elapsed(t1),
            "quality": s2.get("quality", ""),
        })

        t2 = time.time()
        s3 = run_answer_agent(s2)
        steps.append({
            "node": "answer",
            "elapsed": _elapsed(t2),
            "answer_length": len(s3.get("answer", "")),
        })

        return {
            "flow": "worker_internal",
            "task_id": task_id,
            "intent": sub_intent,
            "steps": steps,
            "final_answer": s3.get("answer", ""),
            "error": s3.get("error", ""),
        }

    elif sub_intent == "tool_only":
        # action → answer
        t0 = time.time()
        s1 = run_action_agent(worker_state)
        action_history = s1.get("action_history") or []
        steps.append({
            "node": "action",
            "elapsed": _elapsed(t0),
            "tool_calls": len(action_history),
            "action_summary": _truncate(s1.get("action_summary", ""), 100),
            "error": s1.get("error", ""),
        })

        if s1.get("error"):
            return {"flow": "worker_internal", "task_id": task_id, "intent": sub_intent, "steps": steps, "final_answer": "", "error": s1["error"]}

        t1 = time.time()
        s2 = run_answer_agent(s1)
        steps.append({
            "node": "answer",
            "elapsed": _elapsed(t1),
            "answer_length": len(s2.get("answer", "")),
        })

        return {
            "flow": "worker_internal",
            "task_id": task_id,
            "intent": sub_intent,
            "steps": steps,
            "final_answer": s2.get("answer", ""),
            "error": s2.get("error", ""),
        }

    else:
        # direct_answer
        t0 = time.time()
        s1 = run_answer_agent(worker_state)
        steps.append({
            "node": "answer",
            "elapsed": _elapsed(t0),
            "answer_length": len(s1.get("answer", "")),
        })
        return {
            "flow": "worker_internal",
            "task_id": task_id,
            "intent": sub_intent,
            "steps": steps,
            "final_answer": s1.get("answer", ""),
            "error": s1.get("error", ""),
        }


def render_worker_internal(data: dict, mode: str = "text") -> str:
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    task_id = data["task_id"]
    sub_intent = data["sub_intent"] if "sub_intent" in data else data["intent"]
    steps = data["steps"]

    lines = [
        f"{INDENT}{BOLD}Worker 内部链路 [{sub_intent}]:{RESET}",
    ]

    for step in steps:
        node = step["node"]
        elapsed = step.get("elapsed", "?")

        if node == "retrieval":
            lines.append(f"{INDENT}{INDENT}{DIM}{node}{RESET} ({elapsed})")
            lines.append(f"{INDENT}{INDENT}{INDENT}{_kv('召回数', step.get('recall_count', 0))}")
            if step.get("rewritten_queries"):
                lines.append(f"{INDENT}{INDENT}{INDENT}{_kv('改写查询', step['rewritten_queries'])}")
            if step.get("top_scores"):
                lines.append(f"{INDENT}{INDENT}{INDENT}{_kv('Top3 分数', step['top_scores'])}")
            if step.get("error"):
                lines.append(f"{INDENT}{INDENT}{INDENT}{RED}错误: {step['error']}{RESET}")

        elif node == "quality_gate":
            quality = step.get("quality", "?")
            q_color = GREEN if quality == "passed" else YELLOW
            lines.append(f"{INDENT}{INDENT}{DIM}{node}{RESET} ({elapsed}) {FLOW_ARROW} {q_color}{quality}{RESET}")

        elif node == "action":
            lines.append(f"{INDENT}{INDENT}{DIM}{node}{RESET} ({elapsed})")
            lines.append(f"{INDENT}{INDENT}{INDENT}{_kv('工具调用次数', step.get('tool_calls', 0))}")
            if step.get("action_summary"):
                lines.append(f"{INDENT}{INDENT}{INDENT}{_kv('总结', _truncate(step['action_summary'], 80))}")

        elif node == "answer":
            ans_len = step.get("answer_length", 0)
            lines.append(f"{INDENT}{INDENT}{DIM}{node}{RESET} ({elapsed}) {FLOW_ARROW} {_kv('答案长度', f'{ans_len} 字符')}")

    if data.get("error"):
        lines.append(f"{INDENT}{INDENT}{RED}Worker 异常: {data['error']}{RESET}")
    else:
        answer_preview = _truncate(data.get("final_answer", ""), 150)
        lines.append(f"{INDENT}{INDENT}{DIM}┌─ 答案预览:{RESET}")
        lines.append(f"{INDENT}{INDENT}{DIM}│{RESET} {answer_preview}")
        lines.append(f"{INDENT}{INDENT}{DIM}└─{RESET}")

    return "\n".join(lines)


# ============================================================================
# 流 5: 结果汇总流 — execution_results → plan_results
# ============================================================================


def trace_result_aggregation(state: dict, flow_only: bool = False) -> dict:
    """追踪执行结果的汇总过程。"""
    plan_results = state.get("plan_results") or []

    results = []
    for st in plan_results:
        results.append({
            "task_id": st.get("task_id", -1),
            "sub_query": st.get("sub_query", ""),
            "sub_intent": st.get("sub_intent", ""),
            "worker_name": st.get("worker_name", ""),
            "status": st.get("status", "error"),
            "result_length": len(st.get("result", "")),
            "result_preview": st.get("result", "")[:200],
            "error": st.get("error", ""),
        })

    return {
        "flow": "result_aggregation",
        "total_tasks": len(results),
        "success_count": sum(1 for r in results if r["status"] == "success"),
        "error_count": sum(1 for r in results if r["status"] != "success"),
        "results": results,
    }


def render_result_aggregation(data: dict, mode: str = "text") -> str:
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    total = data["total_tasks"]
    success = data["success_count"]
    error = data["error_count"]

    lines = [
        _stage("流 5", "结果汇总流: execution_results → plan_results"),
        _kv("子任务总数", total),
        _kv("成功", f"{GREEN}{success}{RESET}"),
        _kv("失败", f"{RED}{error}{RESET}" if error else "0"),
    ]

    for r in data["results"]:
        task_id = r["task_id"]
        status = r["status"]
        status_badge = _badge("OK", GREEN) if status == "success" else _badge("FAILED", RED)
        lines.append("")
        lines.append(f"{INDENT}{BOLD}T{task_id}{RESET} {status_badge} [{r['sub_intent']}] → {r['worker_name']}")
        lines.append(f"{INDENT}{INDENT}{_truncate(r['sub_query'], 80)}")
        lines.append(f"{INDENT}{INDENT}{DIM}结果长度: {r['result_length']} 字符{RESET}")

        if r["result_preview"]:
            lines.append(f"{INDENT}{INDENT}{DIM}┌ 预览:{RESET}")
            lines.append(f"{INDENT}{INDENT}{DIM}│{RESET} {_truncate(r['result_preview'], 120)}")
            lines.append(f"{INDENT}{INDENT}{DIM}└{RESET}")

    # 结果流向
    if total > 0:
        lines.append("")
        lines.append(f"{INDENT}{BOLD}结果流向 synthesizer:{RESET}")
        for r in data["results"]:
            lines.append(f"{INDENT}{DIM}T{r['task_id']} 结果 ({r['result_length']}字符){RESET} {FLOW_ARROW} {CYAN}synthesizer 输入{RESET}")

    return "\n".join(lines)


# ============================================================================
# 流 6: 答案综合流 — plan_results → synthesizer LLM → synthesized_answer
# ============================================================================


def trace_synthesis(state: dict, flow_only: bool = False) -> dict:
    """追踪 synthesizer 的综合过程。"""
    plan_results = state.get("plan_results") or []
    plan = state.get("plan") or {}
    plan_reason = plan.get("plan_reason", "")

    input_parts: list[dict] = []
    for st in plan_results:
        task_id = st.get("task_id", -1)
        result_text = st.get("result", "")
        input_parts.append({
            "task_id": task_id,
            "sub_query": st.get("sub_query", ""),
            "sub_intent": st.get("sub_intent", ""),
            "status": st.get("status", "error"),
            "result_length": len(result_text),
            "result_preview": result_text[:150],
        })

    return {
        "flow": "synthesis",
        "original_query": state.get("user_query", ""),
        "plan_reason": plan_reason,
        "input_task_count": len(input_parts),
        "input_parts": input_parts,
        "synthesized_answer": state.get("synthesized_answer", ""),
        "answer": state.get("answer", ""),
        "error": state.get("error", ""),
    }


def render_synthesis(data: dict, mode: str = "text") -> str:
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    lines = [
        _stage("流 6", "答案综合流: plan_results → synthesizer LLM → synthesized_answer"),
        _kv("原始问题", _truncate(data["original_query"], 100)),
        _kv("分解思路", data["plan_reason"]),
        _kv("输入子任务数", data["input_task_count"]),
    ]

    # 展示各子任务结果如何进入综合
    if data["input_parts"]:
        lines.append("")
        lines.append(f"{INDENT}{BOLD}输入综合的信号:{RESET}")
        for part in data["input_parts"]:
            status_badge = _badge("OK", GREEN) if part["status"] == "success" else _badge("FAILED", RED)
            lines.append(f"{INDENT}{INDENT}{DIM}T{part['task_id']}{RESET} {status_badge} [{part['sub_intent']}]")
            lines.append(f"{INDENT}{INDENT}{INDENT}{DIM}query:{RESET} {_truncate(part['sub_query'], 60)}")
            lines.append(f"{INDENT}{INDENT}{INDENT}{DIM}结果长度:{RESET} {part['result_length']} 字符")
            if part["result_preview"]:
                lines.append(f"{INDENT}{INDENT}{INDENT}{DIM}└{RESET} {_truncate(part['result_preview'], 80)}")

    # 展示综合结果
    final = data.get("synthesized_answer") or data.get("answer") or ""
    if final:
        lines.append("")
        lines.append(f"{INDENT}{BOLD}综合后的最终答案:{RESET}")
        lines.append(f"{INDENT}{_sep('─', 66)}")
        lines.append(final)
        lines.append(f"{INDENT}{_sep('─', 66)}")
    elif data.get("error"):
        lines.append(f"{INDENT}{RED}综合失败: {data['error']}{RESET}")

    return "\n".join(lines)


# ============================================================================
# 主追踪流程
# ============================================================================


def run_flow_trace(
    user_query: str,
    *,
    force_complex: bool = False,
    step_mode: bool = False,
    verbose: bool = False,
    flow_only: bool = False,
    json_mode: bool = False,
):
    """按六个信息流阶段逐步追踪 planner 链路的完整数据流动。"""
    state = create_initial_state(user_query=user_query, mode="auto")

    if not json_mode:
        print(_header("Planner 信息流追踪"))
        print(_kv("输入问题", user_query))
        print(_kv("强制 complex", force_complex))
        print(_kv("仅追踪流", flow_only))
        print(_kv("Verbose", verbose))

    # ============================================================
    # 流 1: 路由决策
    # ============================================================
    if not json_mode:
        print()
    t_start = time.time()
    state = run_orchestrator(state)

    if force_complex:
        state["complexity"] = "complex"
        state["route_reason"] = str(state.get("route_reason", "")) + " (forced_complex)"

    routing_data = trace_routing(state, flow_only=flow_only)
    if not json_mode:
        print(render_routing(routing_data))
        print(f"{INDENT}{DIM}耗时: {_elapsed(t_start)}{RESET}")
    else:
        routing_data["elapsed"] = _elapsed(t_start)
        print(json.dumps(routing_data, ensure_ascii=False, indent=2))

    if routing_data["complexity"] != "complex":
        if not json_mode:
            print(f"\n  {YELLOW}orchestrator 判断为 simple，不触发 planner 链路。退出追踪。{RESET}")
            print(f"  {DIM}提示: 用更复杂的问题，或加 --force 强制走 planner{RESET}")
        return state

    if step_mode:
        _wait(json_mode)

    # ============================================================
    # 流 2: 计划分解
    # ============================================================
    t_start = time.time()
    from supportAgents.agents.planner_agent import run_planner

    if not flow_only:
        state = run_planner(state)

    planning_data = trace_planning(state, flow_only=flow_only)
    if not json_mode:
        print(render_planning(planning_data))
        print(f"{INDENT}{DIM}耗时: {_elapsed(t_start)}{RESET}")
    else:
        planning_data["elapsed"] = _elapsed(t_start)
        print(json.dumps(planning_data, ensure_ascii=False, indent=2))

    plan = state.get("plan") or {}
    sub_tasks = plan.get("sub_tasks", [])
    if not sub_tasks:
        if not json_mode:
            print(f"\n  {RED}planner 未生成有效子任务，终止追踪{RESET}")
        return state

    if step_mode:
        _wait(json_mode)

    # ============================================================
    # 流 3+4: 依赖注入 + Worker 执行 (按拓扑波次并发)
    # ============================================================
    from supportAgents.agents.planner_agent import (
        _build_worker_state,
        _dispatch_worker,
        _topological_waves,
    )
    from concurrent.futures import ThreadPoolExecutor, as_completed

    waves = _topological_waves(sub_tasks)
    if waves is None:
        if not json_mode:
            print(f"\n  {RED}检测到循环依赖，终止追踪{RESET}")
        return state

    execution_results: dict = {}
    ordered_results: list = []

    if not json_mode:
        print()
        print(_stage("流 3+4", f"依赖注入流 + Worker 执行流 ({len(waves)} 波次, 波内并发)"))

    for wave_idx, wave in enumerate(waves):
        if not json_mode and len(waves) > 1:
            wave_label = f"第 {wave_idx+1}/{len(waves)} 波"
            wave_tasks = ", ".join(f"T{t}" for t in wave)
            print(f"\n  {BOLD}{YELLOW}{wave_label}{RESET} {DIM}({wave_tasks}){RESET}")

        # --- 流 3: 依赖注入追踪（串行，纯打印不耗时间）---
        for task_id in wave:
            sub_task = sub_tasks[task_id]
            sub_intent = sub_task.get("sub_intent", "direct_answer")

            injection_data = trace_dependency_injection(
                state, task_id, sub_task, execution_results, flow_only=flow_only
            )
            if not json_mode:
                print(f"{_sep('·', 68)}")
                print(f"  {BOLD}子任务 T{task_id}{RESET}  [{sub_intent}]")
                print(render_dependency_injection(injection_data))
            else:
                print(json.dumps(injection_data, ensure_ascii=False, indent=2))

        if flow_only:
            for task_id in wave:
                sub_task = sub_tasks[task_id]
                ordered_results.append({
                    "task_id": task_id,
                    "sub_query": sub_task.get("sub_query", ""),
                    "sub_intent": sub_task.get("sub_intent", "direct_answer"),
                    "depends_on": sub_task.get("depends_on", []),
                    "worker_name": f"{sub_task.get('sub_intent', 'direct_answer')}_worker",
                    "status": "success",
                    "result": f"[flow_only] 模拟 T{task_id} 结果",
                    "error": "",
                })
                execution_results[task_id] = ordered_results[-1]
            continue

        # --- 流 4: Worker 执行（波内并发）---
        if verbose:
            # verbose 模式：trace_worker_internal 内部串行多轮 LLM，波内用线程并发
            def _run_verbose(tid, st, si):
                ws = _build_worker_state(
                    parent_state=state,
                    task_id=tid,
                    sub_task=st,
                    execution_results=execution_results,
                )
                wtr = trace_worker_internal(tid, si, ws)
                return {
                    "task_id": tid,
                    "sub_query": st.get("sub_query", ""),
                    "sub_intent": si,
                    "depends_on": st.get("depends_on", []),
                    "worker_name": f"{si}_worker",
                    "status": "success" if wtr.get("final_answer") else "error",
                    "result": wtr.get("final_answer", ""),
                    "error": wtr.get("error", ""),
                    "_trace": wtr,
                }

            if len(wave) == 1:
                tid = wave[0]
                st = sub_tasks[tid]
                si = st.get("sub_intent", "direct_answer")
                tr = _run_verbose(tid, st, si)
                if not json_mode and "_trace" in tr:
                    print(render_worker_internal(tr.pop("_trace")))
                else:
                    tr.pop("_trace", None)
                    print(json.dumps(tr, ensure_ascii=False, indent=2))
                execution_results[tid] = tr
                ordered_results.append(tr)
            else:
                with ThreadPoolExecutor() as executor:
                    futs = {}
                    for tid in wave:
                        st = sub_tasks[tid]
                        si = st.get("sub_intent", "direct_answer")
                        futs[executor.submit(_run_verbose, tid, st, si)] = tid

                    wv_results: dict[int, dict] = {}
                    for fut in as_completed(futs):
                        tr = fut.result()
                        wv_results[tr["task_id"]] = tr

                for tid in wave:
                    tr = wv_results[tid]
                    if not json_mode and "_trace" in tr:
                        print(render_worker_internal(tr.pop("_trace")))
                    else:
                        tr.pop("_trace", None)
                        print(json.dumps(tr, ensure_ascii=False, indent=2))
                    execution_results[tid] = tr
                    ordered_results.append(tr)

        else:
            # 非 verbose：直接 dispatch，波内 I/O 并发
            if len(wave) == 1:
                tid = wave[0]
                st = sub_tasks[tid]
                ws = _build_worker_state(
                    parent_state=state,
                    task_id=tid,
                    sub_task=st,
                    execution_results=execution_results,
                )
                t0 = time.time()
                tr = dict(_dispatch_worker(task_id=tid, sub_task=st, worker_state=ws))
                elapsed = _elapsed(t0)
                if not json_mode:
                    status = tr.get("status", "error")
                    sb = _badge("OK", GREEN) if status == "success" else _badge("FAILED", RED)
                    print(f"  {DIM}T{tid} 完成 ({elapsed}){RESET} {sb}")
                    if tr.get("result"):
                        print(f"{INDENT}{DIM}└{RESET} {_truncate(tr['result'], 120)}")
                execution_results[tid] = tr
                ordered_results.append(tr)
            else:
                with ThreadPoolExecutor() as executor:
                    futs = {}
                    for tid in wave:
                        st = sub_tasks[tid]
                        ws = _build_worker_state(
                            parent_state=state,
                            task_id=tid,
                            sub_task=st,
                            execution_results=execution_results,
                        )
                        futs[executor.submit(
                            _dispatch_worker,
                            task_id=tid,
                            sub_task=st,
                            worker_state=ws,
                        )] = tid

                    wv_results: dict[int, dict] = {}
                    for fut in as_completed(futs):
                        tr = dict(fut.result())
                        tid = futs[fut]
                        wv_results[tid] = tr

                for tid in wave:
                    tr = wv_results[tid]
                    if not json_mode:
                        status = tr.get("status", "error")
                        sb = _badge("OK", GREEN) if status == "success" else _badge("FAILED", RED)
                        print(f"  {DIM}T{tid} 完成{FLOW_ARROW}{RESET} {sb}")
                        if tr.get("result"):
                            print(f"{INDENT}{DIM}└{RESET} {_truncate(tr['result'], 120)}")
                    execution_results[tid] = tr
                    ordered_results.append(tr)

        if step_mode:
            _wait(json_mode)

    # 写入 plan_results
    state["plan_results"] = ordered_results

    # ============================================================
    # 流 5: 结果汇总
    # ============================================================
    if not json_mode:
        print()
    aggregation_data = trace_result_aggregation(state, flow_only=flow_only)
    if not json_mode:
        print(render_result_aggregation(aggregation_data))
    else:
        print(json.dumps(aggregation_data, ensure_ascii=False, indent=2))

    if step_mode:
        _wait(json_mode)

    # ============================================================
    # 流 6: 答案综合
    # ============================================================
    if not flow_only:
        t_start = time.time()
        from supportAgents.agents.synthesizer_agent import run_synthesizer
        state = run_synthesizer(state)
        synthesis_elapsed = _elapsed(t_start)
    else:
        synthesis_elapsed = "0ms"

    synthesis_data = trace_synthesis(state, flow_only=flow_only)
    if not json_mode:
        print(render_synthesis(synthesis_data))
        print(f"{INDENT}{DIM}耗时: {synthesis_elapsed}{RESET}")
    else:
        synthesis_data["elapsed"] = synthesis_elapsed
        print(json.dumps(synthesis_data, ensure_ascii=False, indent=2))

    # ============================================================
    # 完成
    # ============================================================
    if not json_mode:
        print(f"\n{_sep('═')}")
        print(f"  {GREEN}信息流追踪完成{RESET}")
        print(f"{_sep('═')}\n")

    return state


# ============================================================================
# CLI 入口
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Planner 信息流追踪工具 — 观察复杂任务六个阶段的数据流动",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/debug_planner_flow.py "Redis 集群主从同步延迟排查，另外查 pg 最大连接数"
    python scripts/debug_planner_flow.py --step "Nginx 502 排查 + 数据库连接池"
    python scripts/debug_planner_flow.py --verbose "如何排查微服务雪崩"
    python scripts/debug_planner_flow.py --flow-only "对比 asyncio 和 goroutine"
    python scripts/debug_planner_flow.py --force "什么是 Redis"
    python scripts/debug_planner_flow.py --json "分布式追踪方案"
        """,
    )
    parser.add_argument("query", nargs="?", default=None, help="用户问题（建议用包含多个子问题的复杂描述）")
    parser.add_argument("--force", "-f", action="store_true",
                        help="强制走 planner 链路，忽略 orchestrator 的 complexity 判断")
    parser.add_argument("--step", "-s", action="store_true",
                        help="逐步模式，每个信息流阶段完成后暂停")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="显示 Worker 内部各节点的 state 变化")
    parser.add_argument("--flow-only", "-o", action="store_true",
                        help="只追踪信息流结构，不实际执行 LLM 调用")
    parser.add_argument("--json", "-j", action="store_true",
                        help="以 JSON 格式输出")
    args = parser.parse_args()

    query = args.query
    if not query:
        print("Planner 信息流追踪工具\n")
        print("六大信息流：")
        print("  流1  路由决策流：orchestrator → planner gate")
        print("  流2  计划分解流：user_query → planner LLM → sub_tasks DAG")
        print("  流3  依赖注入流：前置结果 → worker_query → 后置子任务")
        print("  流4  Worker内部流：retrieval→quality_gate→answer (--verbose)")
        print("  流5  结果汇总流：execution_results → plan_results")
        print("  流6  答案综合流：plan_results → synthesizer → 最终答案")
        print()
        print("提示: 输入 /q 退出")
        print("示例: Redis 集群主从同步延迟排查，另外查 pg 最大连接数配置\n")
        try:
            query = input("请输入问题: ").strip()
            if not query or query == "/q":
                return
        except (EOFError, KeyboardInterrupt):
            return

    run_flow_trace(
        user_query=query,
        force_complex=args.force,
        step_mode=args.step,
        verbose=args.verbose,
        flow_only=args.flow_only,
        json_mode=args.json,
    )


if __name__ == "__main__":
    main()
