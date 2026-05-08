"""
调试脚本：逐步运行 support graph 的最小闭环，观察每一步的 state 变化。

用法:
    python scripts/debug_graph.py "什么是 Redis"
    python scripts/debug_graph.py --mode direct "什么是 Redis"
    python scripts/debug_graph.py --mode rag "如何配置 Nginx"
    python scripts/debug_graph.py --step "这个接口怎么调用"
    python scripts/debug_graph.py --json "什么是 SQL 注入"
    python scripts/debug_graph.py --dry "查询用户表"

选项:
    --mode     执行模式: auto(默认,自动路由) / direct(跳过检索直接回答) / rag(强制走检索)
    --step     逐步模式，每执行完一个节点暂停，回车后才继续下一步
    --json     以 JSON 格式打印每一步的 state（便于管道或存文件）
    --dry      纯路由分析模式，只跑 orchestrator，不跑后续的 retrieval 和 answer
"""

import argparse
import json
import sys
from pathlib import Path

# 把项目根目录加入 sys.path，方便从任意位置运行本脚本
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from supportAgents.graph import create_initial_state, build_support_graph
from supportAgents.agents import run_orchestrator, decide_intent


def format_state(state: dict, mode: str = "text") -> str:
    """把 graph state 格式化成可读文本或 JSON。"""
    if mode == "json":
        # 过滤掉不可序列化的字段（如 ChunkRecord 对象）
        serializable = {}
        for key, value in state.items():
            try:
                json.dumps(value, default=str)
                serializable[key] = value
            except (TypeError, ValueError):
                serializable[key] = str(value)
        return json.dumps(serializable, ensure_ascii=False, indent=2, default=str)

    lines = []
    lines.append("─" * 60)
    lines.append(f"  mode       : {state.get('mode', 'auto')}")
    lines.append(f"  session_id : {state.get('session_id', '(未设置)')}")
    lines.append(f"  user_query : {state.get('user_query', '')}")
    lines.append(f"  intent     : {state.get('intent', '(待定)')}")
    lines.append(f"  route_reason: {state.get('route_reason', '(待定)')}")
    quality = state.get("quality", "")
    if quality:
        quality_label = {
            "passed": "通过",
            "degraded_empty": "降级(零结果)",
            "degraded_low_score": "降级(低分)",
        }.get(quality, quality)
        lines.append(f"  quality    : {quality_label}")
    else:
        lines.append(f"  quality    : (未评估)")

    action_history = state.get("action_history") or []
    action_summary = state.get("action_summary", "")
    if action_history:
        lines.append(f"  action     : 工具调用 {len(action_history)} 次")
        for i, act in enumerate(action_history, start=1):
            tool_name = act.get("tool_name", "?")
            status = act.get("status", "?")
            status_label = "成功" if status == "success" else f"失败: {act.get('error_message', '')}"
            lines.append(f"               [{i}] {tool_name} → {status_label}")
        if action_summary:
            lines.append(f"               summary: {action_summary[:200]}")
    else:
        lines.append("  action     : (未执行)")

    retrieval = state.get("retrieval") or {}
    if retrieval:
        items = retrieval.get("items", [])
        lines.append(f"  retrieval  : query={retrieval.get('query', '')}")
        lines.append(f"               rewritten_queries={retrieval.get('rewritten_queries', [])}")
        lines.append(f"               召回文档数: {len(items)}")
        if items:
            lines.append("               ── 召回文档 ──")
            for i, item in enumerate(items, start=1):
                source = item.get("source", "?")
                score = item.get("score", 0)
                text = item.get("text", "")
                preview = text[:100].replace("\n", " ")
                lines.append(f"               [{i}] score={score:.4f}  source={source}")
                lines.append(f"                   预览: {preview}...")
            lines.append("               ─────────────")
    else:
        lines.append("  retrieval  : (未执行)")

    answer = state.get("answer", "")
    if answer:
        lines.append(f"  answer     :")
        lines.append("-" * 40)
        lines.append(answer)
        lines.append("-" * 40)
    else:
        lines.append("  answer     : (未生成)")

    error = state.get("error", "")
    if error:
        lines.append(f"  error      : {error}")

    lines.append("─" * 60)
    return "\n".join(lines)


def run_step_by_step(user_query: str, mode: str = "auto", json_mode: bool = False):
    """逐步执行，每步打印 state。"""
    state = create_initial_state(user_query=user_query, mode=mode)
    if not json_mode:
        print(f"\n{'=' * 60}")
        print(f"  输入问题: {user_query}")
        print(f"{'=' * 60}")

    # ── 第一步: orchestrator ──
    if not json_mode:
        print("\n[步骤 1] orchestrator — 路由判断\n")
    state = run_orchestrator(state)
    print(format_state(state, mode="json" if json_mode else "text"))

    _wait_for_next_step("orchestrator", json_mode)

    # ── 第二步: retrieval ──
    intent = state.get("intent", "fallback")
    if intent == "knowledge_qa":
        if not json_mode:
            print("\n[步骤 2] retrieval — 检索知识库\n")
        try:
            from supportAgents.agents import run_retrieval_agent

            state = run_retrieval_agent(state)
            print(format_state(state, mode="json" if json_mode else "text"))
        except Exception as exc:
            state["error"] = f"retrieval 执行失败: {exc}"
            if not json_mode:
                print(f"  ? retrieval 失败: {exc}")
                print("  ? 提示: 检查 PostgreSQL 是否运行、数据是否已入库")
            print(format_state(state, mode="json" if json_mode else "text"))
        _wait_for_next_step("retrieval", json_mode)

        # ── 第 2.5 步: quality_gate — 检索质量评估 ──
        if not json_mode:
            print("\n[步骤 2.5] quality_gate — 检索质量评估\n")
        from supportAgents.agents import run_quality_gate

        state = run_quality_gate(state)
        print(format_state(state, mode="json" if json_mode else "text"))
        _wait_for_next_step("quality_gate", json_mode)
    else:
        if not json_mode:
            print(f"\n[步骤 2] retrieval — 跳过 (intent={intent}，不需要检索)\n")

        # ── 第 2b 步: action — 工具执行 (仅 tool_only) ──
        if intent == "tool_only":
            if not json_mode:
                print("\n[步骤 2b] action — 工具执行\n")
            try:
                from supportAgents.agents import run_action_agent

                state = run_action_agent(state)
                print(format_state(state, mode="json" if json_mode else "text"))
            except Exception as exc:
                state["error"] = f"action 执行失败: {exc}"
                if not json_mode:
                    print(f"  ? action 失败: {exc}")
                print(format_state(state, mode="json" if json_mode else "text"))
            _wait_for_next_step("action", json_mode)

    # ── 第三步: answer ──
    if not json_mode:
        print("\n[步骤 3] answer — 生成回答\n")
    try:
        from supportAgents.agents import run_answer_agent

        state = run_answer_agent(state)
        print(format_state(state, mode="json" if json_mode else "text"))
    except Exception as exc:
        state["error"] = f"answer 执行失败: {exc}"
        if not json_mode:
            print(f"  ? answer 失败: {exc}")
        print(format_state(state, mode="json" if json_mode else "text"))

    if not json_mode:
        print(f"\n{'=' * 60}")
        print("  执行完成")
        print(f"{'=' * 60}\n")
    return state


def run_dry_analysis(user_query: str, mode: str = "auto"):
    """纯分析模式：只跑路由，不执行检索和回答。"""
    state = create_initial_state(user_query=user_query, mode=mode)
    state = run_orchestrator(state)

    print(f"\n{'=' * 60}")
    print(f"  输入问题: {user_query}")
    print(f"{'=' * 60}")
    print()
    print(format_state(state))

    intent = state.get("intent", "fallback")
    route_reason = state.get("route_reason", "")

    print("  路由分析:")
    print(f"    意图       : {intent}")
    print(f"    判断依据   : {route_reason}")
    print()
    print("  后续链路:")
    if intent == "knowledge_qa":
        print(f"    orchestrator → retrieval → answer")
    else:
        print(f"    orchestrator → answer (跳过检索)")
    print(f"{'=' * 60}\n")


def _wait_for_next_step(node_name: str, json_mode: bool):
    """逐步模式下等待用户按键。"""
    if json_mode:
        return
    try:
        input(f"\n  ? 按回车继续下一步 (Ctrl+C 退出) ...")
    except (EOFError, KeyboardInterrupt):
        print("\n  已退出")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Support Graph 调试工具 — 观察每一步的 state 变化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/debug_graph.py "什么是 Redis"
    python scripts/debug_graph.py --mode direct "什么是 Redis"
    python scripts/debug_graph.py --step "SQL 注入怎么排查"
    python scripts/debug_graph.py --json "如何配置 Nginx"
    python scripts/debug_graph.py --dry "查询用户表"
        """,
    )
    parser.add_argument("query", nargs="?", default=None, help="用户问题")
    parser.add_argument(
        "--mode", "-m",
        choices=["auto", "direct", "rag"],
        default="auto",
        help="执行模式: auto(自动路由) / direct(跳过检索) / rag(强制检索)",
    )
    parser.add_argument(
        "--step", "-s", action="store_true", help="逐步模式，每步暂停"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="以 JSON 格式输出 state"
    )
    parser.add_argument(
        "--dry", "-d", action="store_true", help="纯路由分析，不执行检索和回答"
    )
    args = parser.parse_args()

    query = args.query
    if not query:
        # 如果没有传参数，交互式输入
        print("Support Graph 调试工具")
        print("输入 /q 退出")
        print()
        try:
            query = input("请输入问题: ").strip()
            if not query or query == "/q":
                return
        except (EOFError, KeyboardInterrupt):
            return

    if args.dry:
        run_dry_analysis(query, mode=args.mode)
    elif args.step:
        run_step_by_step(query, mode=args.mode, json_mode=args.json)
    else:
        # 默认：一次性执行并打印每一步
        run_step_by_step(query, mode=args.mode, json_mode=args.json)


if __name__ == "__main__":
    main()
