"""
作用：导出项目里的 LangGraph 结构图，默认写入 aaagraph 目录。

用法：
    .venv\Scripts\python scripts/export_graph.py
    .venv\Scripts\python scripts/export_graph.py --name support_agents_v2
    .venv\Scripts\python scripts/export_graph.py --no-png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from supportAgents.graph.builder import build_support_graph


# 作用：构建项目当前使用的 LangGraph，并取出可绘图的 Graph 对象。
def build_drawable_graph():
    compiled_graph = build_support_graph()
    return compiled_graph.get_graph()


# 作用：把文本内容写入目标文件，统一使用 UTF-8 编码。
def write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# 作用：导出 Mermaid 源码和带代码块的 Markdown，方便直接查看和继续复用。
def export_mermaid_files(output_dir: Path, graph_name: str) -> tuple[Path, Path]:
    drawable_graph = build_drawable_graph()
    mermaid_text = drawable_graph.draw_mermaid()

    mmd_path = output_dir / f"{graph_name}.mmd"
    md_path = output_dir / f"{graph_name}.md"

    write_text_file(mmd_path, mermaid_text)
    write_text_file(md_path, f"# {graph_name}\n\n```mermaid\n{mermaid_text}\n```\n")
    return mmd_path, md_path


# 作用：尽量额外导出一份 PNG；如果本机缺少依赖或当前环境不支持，就返回失败原因。
def export_png_file(output_dir: Path, graph_name: str) -> tuple[Path | None, str | None]:
    drawable_graph = build_drawable_graph()
    png_path = output_dir / f"{graph_name}.png"

    try:
        drawable_graph.draw_png(str(png_path))
        return png_path, None
    except Exception as graphviz_error:
        try:
            drawable_graph.draw_mermaid_png(output_file_path=str(png_path))
            return png_path, None
        except Exception as mermaid_error:
            reason = (
                "PNG 导出失败。"
                f" 本地 Graphviz 方式失败：{graphviz_error};"
                f" Mermaid PNG 方式失败：{mermaid_error}"
            )
            return None, reason


# 作用：解析命令行参数，支持修改输出目录、文件名前缀和是否跳过 PNG。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出项目的 LangGraph 结构图")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "aaagraph"),
        help="输出目录，默认写入项目下的 aaagraph",
    )
    parser.add_argument(
        "--name",
        default="support_graph",
        help="输出文件名前缀，默认是 support_graph",
    )
    parser.add_argument(
        "--no-png",
        action="store_true",
        help="只导出 Mermaid 文本和 Markdown，不生成 PNG",
    )
    return parser.parse_args()


# 作用：执行完整导出流程，并把实际产物路径打印到终端。
def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    mmd_path, md_path = export_mermaid_files(output_dir, args.name)
    print(f"已生成 Mermaid 源文件：{mmd_path}")
    print(f"已生成 Markdown 文件：{md_path}")

    if args.no_png:
        return 0

    png_path, error_message = export_png_file(output_dir, args.name)
    if png_path is not None:
        print(f"已生成 PNG 文件：{png_path}")
        return 0

    print(error_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
