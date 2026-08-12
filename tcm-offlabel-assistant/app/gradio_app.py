"""中成药另类用法查询器 — Gradio + BM25 RAG MVP。

默认不调用大模型：检索后用模板渲染，保证可溯源、可离线演示。
若设置 OPENAI_API_KEY + OPENAI_BASE_URL，可选用兼容接口润色回答。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gradio as gr
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
KB_PATH = ROOT / "data" / "knowledge_base.json"

DISCLAIMER = (
    "本内容仅供学习与科研参考，不构成诊疗建议。"
    "超说明书用药请在执业医师或药师指导下进行，请遵医嘱。"
)


def tokenize(text: str) -> list[str]:
    """轻量中文分词：汉字按字、英文数字按词，附带双字 gram。"""
    text = text.lower().strip()
    chars = re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text)
    grams = ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]
    return chars + grams


@dataclass
class KnowledgeStore:
    meta: dict[str, Any]
    entries: list[dict[str, Any]]
    bm25: BM25Okapi
    corpus_tokens: list[list[str]]

    @classmethod
    def load(cls, path: Path) -> "KnowledgeStore":
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["entries"]
        docs: list[str] = []
        for e in entries:
            parts = [
                e.get("drug", ""),
                " ".join(e.get("aliases", [])),
                e.get("standard_indication", ""),
                e.get("offlabel_use", ""),
                e.get("syndrome", ""),
                e.get("evidence_source", ""),
                " ".join(e.get("symptoms", [])),
                " ".join(e.get("tags", [])),
                " ".join(e.get("precautions", [])),
            ]
            docs.append(" ".join(parts))
        corpus_tokens = [tokenize(d) for d in docs]
        return cls(
            meta=data,
            entries=entries,
            bm25=BM25Okapi(corpus_tokens),
            corpus_tokens=corpus_tokens,
        )

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        q = query.strip()
        if not q:
            return []

        def names_of(e: dict[str, Any]) -> list[str]:
            return [n for n in [e.get("drug", "")] + e.get("aliases", []) if n]

        def has_drug_hit(e: dict[str, Any]) -> bool:
            return any(n in q for n in names_of(e))

        def has_symptom_hit(e: dict[str, Any]) -> bool:
            keys = list(e.get("symptoms", [])) + list(e.get("tags", []))
            # 也用新用途短词：按顿号/逗号切开
            for part in re.split(r"[、，,/；;]", e.get("offlabel_use", "")):
                part = part.strip()
                if len(part) >= 2:
                    keys.append(part)
            return any(k and len(k) >= 2 and k in q for k in keys)

        # 精确药名优先
        exact: list[tuple[dict[str, Any], float]] = []
        for e in self.entries:
            if has_drug_hit(e):
                exact.append((e, 100.0))

        scores = self.bm25.get_scores(tokenize(q))
        ranked = sorted(
            ((self.entries[i], float(scores[i])) for i in range(len(self.entries))),
            key=lambda x: x[1],
            reverse=True,
        )

        merged: dict[str, tuple[dict[str, Any], float]] = {}
        for e, s in exact + ranked:
            eid = e["id"]
            if eid not in merged or s > merged[eid][1]:
                merged[eid] = (e, s)

        results = sorted(merged.values(), key=lambda x: x[1], reverse=True)
        any_drug_in_query = any(has_drug_hit(e) for e, _ in results)
        # 有药名时：同药条目 + 高分；无药名时：必须症状/标签字段命中，避免 BM25 噪音
        filtered: list[tuple[dict[str, Any], float]] = []
        for e, s in results:
            if has_drug_hit(e) or has_symptom_hit(e):
                filtered.append((e, s))
            elif any_drug_in_query and s >= 8.0:
                filtered.append((e, s))
        return filtered[:top_k]


def evidence_label(level: str, levels: dict[str, str]) -> str:
    return f"{level} — {levels.get(level, '未定义')}"


def render_card(entry: dict[str, Any], score: float, levels: dict[str, str]) -> str:
    precautions = "\n".join(f"- {p}" for p in entry.get("precautions", []))
    urls = "\n".join(f"- {u}" for u in entry.get("source_urls", []))
    symptoms = "、".join(entry.get("symptoms", []))
    return f"""### {entry['drug']} · {entry['offlabel_use']}
**相关度**：{score:.2f}　|　**证据等级**：{evidence_label(entry.get('evidence_level', '?'), levels)}　|　**OTC**：{'是' if entry.get('otc') else '否/请核对'}

| 字段 | 内容 |
|------|------|
| 常规适应症 | {entry.get('standard_indication', '')} |
| 或然症/新用途 | {entry.get('offlabel_use', '')}（超说明书 / 探索性） |
| 适用证型 | {entry.get('syndrome', '')} |
| 用法备注 | {entry.get('dosage_note', '')} |
| 证据来源 | {entry.get('evidence_source', '')} |
| 关联症状 | {symptoms} |

**注意事项**
{precautions}

**来源链接**
{urls}
"""


def render_answer(query: str, hits: list[tuple[dict[str, Any], float]], store: KnowledgeStore) -> str:
    levels = store.meta.get("evidence_levels", {})
    if not hits:
        return (
            f"未在知识库中检索到与「{query}」高度相关的条目。\n\n"
            "可尝试：药品名（如牛黄清心丸）或症状（如尿酸高、解酒、蚊虫叮咬）。\n\n"
            f"> {DISCLAIMER}"
        )

    header = (
        f"**查询**：{query}\n\n"
        f"共命中 **{len(hits)}** 条相关知识（按相关度排序）。"
        "下列用法若超出说明书，均属探索/文献线索，须辨证与遵医嘱。\n\n"
    )
    cards = "\n---\n".join(render_card(e, s, levels) for e, s in hits)
    return header + cards + f"\n\n---\n> {store.meta.get('disclaimer', DISCLAIMER)}"


def maybe_llm_polish(query: str, grounded: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key or not base_url:
        return grounded

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        system = (
            "你是中成药信息助手。只能依据用户提供的「检索卡片」作答，"
            "不得编造未出现的适应症或文献。必须保留证据等级、注意事项与免责声明。"
            "不做诊断，不使用「特效/根治」等词。"
        )
        user = f"用户问题：{query}\n\n检索卡片：\n{grounded}\n\n请用简洁中文重新组织回答。"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content or grounded
        if DISCLAIMER not in text and "仅供" not in text:
            text = text.rstrip() + f"\n\n> {DISCLAIMER}"
        return text
    except Exception as exc:  # noqa: BLE001
        return grounded + f"\n\n（LLM 润色失败，已回退模板回答：{exc}）"


def build_demo() -> gr.Blocks:
    store = KnowledgeStore.load(KB_PATH)
    drug_list = sorted({e["drug"] for e in store.entries})
    examples = [
        "牛黄清心丸能解酒吗？",
        "乌鸡白凤丸可以降尿酸吗？",
        "尿酸高有哪些中成药探索用法？",
        "应酬多想护肝，有什么线索？",
        "藿香正气水能涂蚊虫叮咬吗？",
        "逍遥丸对抑郁有用吗？",
        "六味地黄丸能辅助糖尿病吗？",
    ]

    def answer(query: str, top_k: int, use_llm: bool) -> tuple[str, str]:
        hits = store.search(query, top_k=int(top_k))
        grounded = render_answer(query, hits, store)
        final = maybe_llm_polish(query, grounded) if use_llm else grounded
        debug = json.dumps(
            [{"id": e["id"], "drug": e["drug"], "score": round(s, 3), "use": e["offlabel_use"]} for e, s in hits],
            ensure_ascii=False,
            indent=2,
        )
        return final, debug

    with gr.Blocks(title="中成药另类用法查询器") as demo:
        gr.Markdown(
            f"""# 中成药另类用法查询器（MVP）

覆盖试点：{'、'.join(drug_list)}。

检索你的「说明书之外」知识库：常规适应症 + 或然症 + **证据等级** + 注意事项。

> {DISCLAIMER}
"""
        )
        with gr.Row():
            query = gr.Textbox(
                label="输入药品名或症状",
                placeholder="例如：牛黄清心丸解酒 / 尿酸高",
                lines=2,
            )
        with gr.Row():
            top_k = gr.Slider(1, 8, value=4, step=1, label="返回条数")
            use_llm = gr.Checkbox(
                label="用 OpenAI 兼容接口润色（需环境变量）",
                value=False,
            )
        btn = gr.Button("查询", variant="primary")
        out = gr.Markdown(label="回答")
        debug = gr.Code(label="检索命中（调试）", language="json")
        gr.Examples(examples, inputs=[query])
        btn.click(answer, inputs=[query, top_k, use_llm], outputs=[out, debug])
        query.submit(answer, inputs=[query, top_k, use_llm], outputs=[out, debug])

    return demo


if __name__ == "__main__":
    demo = build_demo()
    demo.launch(
        server_name=os.getenv("HOST", "0.0.0.0"),
        server_port=int(os.getenv("PORT", "7860")),
    )
