"""
调试脚本：分步验证飞书文档的图片处理链路（不写库）。

用法:
    python scripts/debug_image_caption.py <doc_id>
    python scripts/debug_image_caption.py JMZww2Vj5inn1IkznH0ch86LnCc
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import settings
from rag.feishu_loader import (
    _load_document_blocks,
    _load_document_metadata,
    _extract_image_block,
    _extract_rich_block,
    get_tenant_access_token,
)


def step(label: str):
    """打印当前步骤，方便定位耗时点。"""
    print(f"  [{time.strftime('%H:%M:%S')}] {label} ...", flush=True)


def done():
    print("      完成", flush=True)


def main():
    parser = argparse.ArgumentParser(description="分步验证飞书文档图片处理链路")
    parser.add_argument("doc_id", help="飞书文档 ID")
    args = parser.parse_args()

    doc_id = args.doc_id
    print(f"文档 ID: {doc_id}")
    print(f"Gemini model: {settings.gemini.model}")
    print(f"Gemini api_key: {'已设置' if settings.gemini.api_key else '未设置'}")
    print()

    # ── 第 1 步: 获取飞书 token ──
    step("获取飞书 tenant_access_token")
    token = get_tenant_access_token()
    done()

    # ── 第 2 步: 获取文档元信息 ──
    step("获取文档元信息")
    title, revision_id = _load_document_metadata(doc_id, token)
    print(f"      标题: {title}, revision: {revision_id}")
    done()

    # ── 第 3 步: 获取文档 blocks ──
    step("获取文档 blocks")
    blocks = _load_document_blocks(doc_id, token)
    print(f"      共 {len(blocks)} 个 block")
    done()

    # ── 第 4 步: 筛选图片 block 并逐个处理 ──
    image_blocks = []
    for i, block in enumerate(blocks):
        block_type = block.get("block_type")
        if block_type == 20:  # image
            image_blocks.append((i + 1, block))

    # 同时列出所有未知类型 block 的原始结构，方便排查
    unknown_blocks = [
        (i + 1, b) for i, b in enumerate(blocks)
        if b.get("block_type") not in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                                         12, 13, 14, 15, 16, 17, 18, 19, 20,
                                         21, 22, 23, 24, 25, 26}
    ]

    if not image_blocks:
        print()
        print("该文档没有图片 block (block_type=20)。")
        type_counts = {}
        for b in blocks:
            bt = b.get("block_type", "?")
            type_counts[bt] = type_counts.get(bt, 0) + 1
        print(f"现有 block 类型分布: {type_counts}")

    if unknown_blocks:
        print(f"\n发现 {len(unknown_blocks)} 个未知类型的 block:")
        import json as _json
        for pos, block in unknown_blocks[:3]:  # 只打印前 3 个
            print(f"\n--- block #{pos} (type={block.get('block_type')}) ---")
            # 递归看看里面有没有 image token
            block_type = block.get("block_type")
            from rag.feishu_loader import _find_first_token, TOKEN_KEYS
            tokens = []
            for key in TOKEN_KEYS:
                val = block.get(key)
                if val:
                    tokens.append((key, str(val)[:80]))
            if not tokens:
                # 深层搜索
                found = _find_first_token(block, TOKEN_KEYS)
                if found:
                    tokens.append(("deep_search", found))
            print(f"  tokens: {tokens}")
            # 打印 block 的顶层 keys
            print(f"  top-level keys: {list(block.keys())[:15]}")
            # 如果 block 不大，直接 dump
            block_str = _json.dumps(block, ensure_ascii=False, default=str)
            if len(block_str) <= 2000:
                print(f"  完整内容:\n{block_str}")
            else:
                print(f"  内容(截断):\n{block_str[:1000]}...")

    if not image_blocks and not unknown_blocks:
        return

    if not image_blocks and unknown_blocks:
        print()
        print("=" * 70)
        print("对未知类型 block 实测 _extract_rich_block，看看能否命中:")
        for pos, block in unknown_blocks[:2]:
            rich_text, counters = _extract_rich_block(block, pos, token)
            print(f"  block #{pos}: rich_text={'有内容' if rich_text else '空'}, counters={counters}")
            if rich_text:
                print(f"    预览: {rich_text[:300]}")
        return

    print(f"\n找到 {len(image_blocks)} 个图片 block\n")
    print("=" * 70)

    for img_i, (pos, block) in enumerate(image_blocks, start=1):
        print(f"\n>>> 图片 {img_i}/{len(image_blocks)} (原始位置 #{pos})")

        step("  OCR 识别 (RapidOCR)")
        t0 = time.time()
        try:
            ocr_result = None
            # 这里直接复用 _extract_image_block 的逻辑，但要先拿到 image_bytes
            # 先走 _extract_rich_block 看结果
            rich_text, counters = _extract_rich_block(block, pos, token)
            print(f"      耗时 {time.time() - t0:.1f}s, OCR次数={counters['image_ocr_count']}")
            if rich_text:
                print(f"      内容长度: {len(rich_text)} 字符")
                print(f"      预览:\n{rich_text[:500]}")
                if len(rich_text) > 500:
                    print("      ... (截断)")
        except Exception as exc:
            print(f"      失败: {exc}")
        done()

        print()

    print("=" * 70)
    print("验证完成。")


if __name__ == "__main__":
    main()
