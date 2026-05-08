"""
调试脚本：专门观察 planner 链路每一步的 state 变化。

Planner 链路：orchestrator -> planner -> execute_subtasks -> synthesizer -> END

用法:
    # 用复杂问题触发 planner 链路（推荐）
    python scripts/debug_planner.py "Redis 集群模式下如何排查主从同步延迟问题？另外 pg_query 要怎么查连接数"

    # 强制将任何问题都走 planner 链路
    python scripts/debug_planner.py --force "什么是 Redis"

    # 逐步模式，每步暂停
    python scripts/debug_planner.py --step "如何排查 Nginx 502 错误，同时检查数据库连接池配置"

    # JSON 输出（便于管道）
    python scripts/debug_planner.py --json "对比 Python asyncio 和 Go goroutine 的并发模型"

    # 只跑 planner 分解，不执行子任务
    python scripts/debug_planner.py --plan-only "微服务架构下如何做分布式追踪"

选项:
    --force     强制走 planner 链路，即使 orchestrator 判断为 simple
    --step      逐步模式，每执行完一个节点暂停
    --json      以 JSON 格式输出每一步的 state
    --plan-only 只跑 orchestrator + planner，不执行子任务和综合
"""

import argparse
import json
import sys
from pathlib import Path

# 修复 Windows GBK 终端输出中文/特殊字符的编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from supportAgents.graph import create_initial_state
from supportAgents.agents import run_orchestrator


# -- ANSI 颜色常量 --
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


def _sep(char: str = "-", width: int = 72) -> str:
    return char * width


def _header(title: str) -> str:
    bar = _sep("=")
    return f"\n{BOLD}{CYAN}{bar}{RESET}\n{BOLD}{CYAN}  {title}{RESET}\n{BOLD}{CYAN}{bar}{RESET}"


def _sub_header(title: str) -> str:
    return f"\n{BOLD}{BLUE}  >> {title}{RESET}"


def _fmt_kv(key: str, value: object, indent: int = 2) -> str:
    prefix = " " * indent
    return f"{prefix}{DIM}{key}:{RESET} {value}"


def _fmt_badge(value: str, color: str = GREEN) -> str:
    return f"{color}{BOLD}[{value}]{RESET}"


def _wait(json_mode: bool):
    if json_mode:
        return
    try:
        input(f"\n  {DIM}[Enter] 按回车继续下一步 (Ctrl+C 退出) ...{RESET}")
    except (EOFError, KeyboardInterrupt):
        print("\n  已退出")
        sys.exit(0)


# -- 格式化输出 --

def format_orchestrator(state: dict, mode: str = "text") -> str:
    """格式化 orchestrator 节点的关键输出。"""
    if mode == "json":
        keys = ["user_query", "normalized_query", "intent", "complexity", "route_reason"]
        return json.dumps({k: state.get(k) for k in keys}, ensure_ascii=False, indent=2)

    intent = state.get("intent", "?")
    complexity = state.get("complexity", "simple")
    complexity_badge = _fmt_badge("COMPLEX", YELLOW) if complexity == "complex" else _fmt_badge("SIMPLE", GREEN)

    lines = [
        _sub_header("orchestrator 路由结果"),
        _fmt_kv("user_query", state.get("user_query", "")),
        _fmt_kv("intent", intent),
        _fmt_kv("complexity", f"{complexity} {complexity_badge}"),
        _fmt_kv("route_reason", state.get("route_reason", "")),
    ]
    return "\n".join(lines)


def format_planner(state: dict, mode: str = "text") -> str:
    """格式化 planner 节点的关键输出：分解后的子任务计划。"""
    plan = state.get("plan") or {}
    sub_tasks = plan.get("sub_tasks", [])
    plan_reason = plan.get("plan_reason", "")

    if mode == "json":
        serializable = {
            "plan_reason": plan_reason,
            "sub_tasks": [],
        }
        for st in sub_tasks:
            serializable["sub_tasks"].append({
                "sub_query": st.get("sub_query", ""),
                "sub_intent": st.get("sub_intent", ""),
                "depends_on": st.get("depends_on", []),
            })
        return json.dumps(serializable, ensure_ascii=False, indent=2)

    lines = [
        _sub_header("planner 分解结果"),
        _fmt_kv("plan_reason", plan_reason),
        _fmt_kv("子任务数", len(sub_tasks)),
    ]

    # 构建依赖关系可视化
    deps_map: dict[int, list[int]] = {}
    for i, st in enumerate(sub_tasks):
        deps_map[i] = st.get("depends_on", [])

    lines.append(f"\n  {BOLD}子任务依赖关系 (DAG):{RESET}")
    for i, st in enumerate(sub_tasks):
        deps = deps_map[i]
        deps_str = f" <-- 依赖 [{', '.join(map(str, deps))}]" if deps else " (无依赖)"
        sub_intent = st.get("sub_intent", "?")
        sub_query = st.get("sub_query", "")
        query_preview = sub_query[:80] + "..." if len(sub_query) > 80 else sub_query

        intent_color_map = {
            "knowledge_qa": BLUE,
            "tool_only": YELLOW,
            "direct_answer": GREEN,
        }
        color = intent_color_map.get(sub_intent, RESET)

        lines.append(f"  {BOLD}[{i}]{RESET} {color}{sub_intent}{RESET}{deps_str}")
        lines.append(f"      {query_preview}")

    if sub_tasks:
        lines.append(f"\n  {BOLD}拓扑序执行顺序:{RESET}")
        from supportAgents.agents.planner_agent import _topological_order
        order = _topological_order(sub_tasks)
        if order:
            arrows = " -> ".join(str(i) for i in order)
            lines.append(f"  {arrows}")
        else:
            lines.append(f"  {RED}[!] 检测到循环依赖！{RESET}")

    return "\n".join(lines)


def format_execute(state: dict, mode: str = "text") -> str:
    """格式化 execute_subtasks 节点的关键输出：每个子任务的执行结果。"""
    plan_results = state.get("plan_results") or []

    if mode == "json":
        results = []
        for st in plan_results:
            results.append({
                "sub_query": st.get("sub_query", ""),
                "sub_intent": st.get("sub_intent", ""),
                "depends_on": st.get("depends_on", []),
                "result": st.get("result", "")[:500],
            })
        return json.dumps(results, ensure_ascii=False, indent=2)

    lines = [
        _sub_header("execute_subtasks 执行结果"),
        _fmt_kv("完成子任务数", len(plan_results)),
    ]

    for i, st in enumerate(plan_results):
        sub_intent = st.get("sub_intent", "?")
        result = st.get("result", "")
        sub_query = st.get("sub_query", "")

        has_error = result.startswith("[子任务执行失败]")
        is_empty = not result
        if has_error:
            status = _fmt_badge("FAILED", RED)
        elif is_empty:
            status = _fmt_badge("EMPTY", YELLOW)
        else:
            status = _fmt_badge("OK", GREEN)

        lines.append(f"\n  {BOLD}---- 子任务 [{i}] {status} ----{RESET}")
        lines.append(f"  intent: {sub_intent}")
        lines.append(f"  query : {sub_query[:100]}")

        if result:
            result_preview = result[:300].replace("\n", "\n  | ")
            if len(result) > 300:
                result_preview += f"\n  | {DIM}... (剩余 {len(result) - 300} 字符){RESET}"
            lines.append(f"  result:")
            lines.append(f"  | {result_preview}")

    return "\n".join(lines)


def format_synthesizer(state: dict, mode: str = "text") -> str:
    """格式化 synthesizer 节点的关键输出：最终综合答案。"""
    answer = state.get("answer", "")
    synthesized = state.get("synthesized_answer", "")
    final = synthesized or answer

    if mode == "json":
        return json.dumps({
            "synthesized_answer": final[:1000],
            "answer": answer[:1000] if answer else "",
        }, ensure_ascii=False, indent=2)

    lines = [
        _sub_header("synthesizer 综合答案"),
        _fmt_kv("答案长度", f"{len(final)} 字符"),
    ]

    if final:
        lines.append(f"\n  {_sep('-', 68)}")
        lines.append(final)
        lines.append(f"  {_sep('-', 68)}")
    else:
        lines.append(f"  {YELLOW}(未生成答案){RESET}")

    error = state.get("error", "")
    if error:
        lines.append(f"\n  {RED}[!] error: {error}{RESET}")

    return "\n".join(lines)


# -- 主流程 --

def run_planner_debug(
    user_query: str,
    force_complex: bool = False,
    step_mode: bool = False,
    json_mode: bool = False,
    plan_only: bool = False,
):
    state = create_initial_state(user_query=user_query, mode="auto")

    if not json_mode:
        print(_header(f"Planner 链路调试"))
        print(_fmt_kv("输入问题", user_query))
        print(_fmt_kv("强制 complex", force_complex))
        print(_fmt_kv("只分解不执行", plan_only))

    # -- Step 1: orchestrator --
    if not json_mode:
        print(_header("Step 1/4: orchestrator -- 路由判断"))
    state = run_orchestrator(state)

    # 强制走 complex
    if force_complex:
        state["complexity"] = "complex"
        state["route_reason"] = str(state.get("route_reason", "")) + " (forced_complex)"

    print(format_orchestrator(state, mode="json" if json_mode else "text"))

    complexity = state.get("complexity", "simple")
    if complexity != "complex":
        if not json_mode:
            print(f"\n  {YELLOW}[!] orchestrator 判断为 simple，不走 planner 链路。{RESET}")
            print(f"  {DIM}提示: 尝试用更复杂的问题，或加 --force 强制走 planner{RESET}")
        return state
    else:
        if not json_mode:
            print(f"\n  {GREEN}[OK] 触发 planner 链路！{RESET}")

    if step_mode:
        _wait(json_mode)

    # -- Step 2: planner --
    if not json_mode:
        print(_header("Step 2/4: planner -- 任务分解"))
    from supportAgents.agents.planner_agent import run_planner
    state = run_planner(state)
    print(format_planner(state, mode="json" if json_mode else "text"))

    plan = state.get("plan") or {}
    sub_tasks = plan.get("sub_tasks", [])
    if not sub_tasks:
        if not json_mode:
            print(f"\n  {RED}[!] planner 未生成有效子任务，终止{RESET}")
        return state

    if plan_only:
        if not json_mode:
            print(f"\n  {DIM}--plan-only 模式，跳过执行和综合{RESET}")
        return state

    if step_mode:
        _wait(json_mode)

    # -- Step 3: execute_subtasks --
    if not json_mode:
        print(_header("Step 3/4: execute_subtasks -- 按拓扑序执行"))
    from supportAgents.agents.planner_agent import run_execute_subtasks
    state = run_execute_subtasks(state)
    print(format_execute(state, mode="json" if json_mode else "text"))

    if state.get("error"):
        if not json_mode:
            print(f"\n  {RED}[!] 执行异常: {state['error']}{RESET}")
        return state

    if step_mode:
        _wait(json_mode)

    # -- Step 4: synthesizer --
    if not json_mode:
        print(_header("Step 4/4: synthesizer -- 答案综合"))
    from supportAgents.agents.synthesizer_agent import run_synthesizer
    state = run_synthesizer(state)
    print(format_synthesizer(state, mode="json" if json_mode else "text"))

    if not json_mode:
        print(f"\n{_sep('=')}")
        print(f"  {GREEN}执行完成{RESET}")
        print(f"{_sep('=')}\n")

    return state


def main():
    parser = argparse.ArgumentParser(
        description="Planner 链路调试工具 -- 观察复杂任务分解、执行、综合的 state 变化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/debug_planner.py "Redis 集群主从同步延迟怎么排查？另外怎么查 PostgreSQL 连接数"
    python scripts/debug_planner.py --force "什么是 Redis"
    python scripts/debug_planner.py --step "如何排查 Nginx 502 并检查数据库连接池"
    python scripts/debug_planner.py --json "对比 Python 和 Go 的并发模型"
    python scripts/debug_planner.py --plan-only "微服务分布式追踪方案"
        """,
    )
    parser.add_argument("query", nargs="?", default=None, help="用户问题（建议用复杂问题触发 planner）")
    parser.add_argument("--force", "-f", action="store_true",
                        help="强制走 planner 链路，忽略 orchestrator 的 complexity 判断")
    parser.add_argument("--step", "-s", action="store_true",
                        help="逐步模式，每步完成后暂停等待回车")
    parser.add_argument("--json", "-j", action="store_true",
                        help="以 JSON 格式输出每一步的 state")
    parser.add_argument("--plan-only", "-p", action="store_true",
                        help="只跑 orchestrator + planner 分解，不执行子任务和综合")
    args = parser.parse_args()

    query = args.query
    if not query:
        print("Planner 链路调试工具")
        print("输入 /q 退出\n")
        print("提示: 用包含多个子问题的复杂描述更容易触发 planner 链路")
        print("例如: '如何排查 Redis 主从延迟，同时查一下 PostgreSQL 最大连接数配置'\n")
        try:
            query = input("请输入问题: ").strip()
            if not query or query == "/q":
                return
        except (EOFError, KeyboardInterrupt):
            return

    run_planner_debug(
        user_query=query,
        force_complex=args.force,
        step_mode=args.step,
        json_mode=args.json,
        plan_only=args.plan_only,
    )


if __name__ == "__main__":
    main()
