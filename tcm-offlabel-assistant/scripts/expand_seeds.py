#!/usr/bin/env python3
"""用 expand_seed.md 批量调用 OpenAI 兼容接口，把种子扩成 QA JSONL。

用法：
  export OPENAI_API_KEY=...
  export OPENAI_BASE_URL=https://.../v1
  export OPENAI_MODEL=gpt-4o-mini
  python scripts/expand_seeds.py --count 20 --limit 2
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "expand_seed.md"
KB_PATH = ROOT / "data" / "knowledge_base.json"
OUT_PATH = ROOT / "data" / "expanded_qa.jsonl"


def build_prompt(seed: dict, count: int) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{{SEED_JSON}}", json.dumps(seed, ensure_ascii=False, indent=2))
        .replace("{{COUNT}}", str(count))
    )


def extract_json_array(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20, help="每条种子生成条数")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 条种子，0=全部")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key or not base_url:
        raise SystemExit("需要 OPENAI_API_KEY 与 OPENAI_BASE_URL")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    seeds = kb["entries"]
    if args.limit:
        seeds = seeds[: args.limit]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with args.out.open("w", encoding="utf-8") as fout:
        for seed in seeds:
            prompt = build_prompt(seed, args.count)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            content = resp.choices[0].message.content or "[]"
            items = extract_json_array(content)
            for item in items:
                fout.write(json.dumps(item, ensure_ascii=False) + "\n")
                n += 1
            print(f"seed={seed['id']} -> {len(items)} qa")
    print(f"wrote {n} lines -> {args.out}")


if __name__ == "__main__":
    main()
