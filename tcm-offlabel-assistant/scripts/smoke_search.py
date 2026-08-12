"""无 UI 的检索自检脚本。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from gradio_app import KnowledgeStore, render_answer  # noqa: E402

KB = ROOT / "data" / "knowledge_base.json"


def main() -> None:
    store = KnowledgeStore.load(KB)
    cases = [
        "牛黄清心丸能解酒吗",
        "乌鸡白凤丸降尿酸",
        "尿酸高怎么办中成药",
        "藿香正气水蚊虫叮咬",
        "逍遥丸抑郁",
        "六味地黄丸糖尿病",
        "脂肪肝乌鸡白凤丸",
        "不存在的某某仙丹",
    ]
    ok = 0
    for q in cases:
        hits = store.search(q, top_k=3)
        print("=" * 60)
        print("Q:", q)
        print("hits:", [(h[0]["id"], round(h[1], 2), h[0]["offlabel_use"]) for h in hits])
        if q.startswith("不存在"):
            if not hits:
                ok += 1
        elif hits:
            ok += 1
        # 烟雾：确保能渲染
        _ = render_answer(q, hits, store)
    print(f"\nPASS {ok}/{len(cases)}")
    if ok < len(cases) - 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
