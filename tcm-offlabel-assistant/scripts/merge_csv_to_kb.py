#!/usr/bin/env python3
"""把 seed_template.csv 合并进 knowledge_base.json（按 id 去重更新）。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "seed_template.csv"
KB_PATH = ROOT / "data" / "knowledge_base.json"


def row_to_entry(row: dict[str, str]) -> dict:
    return {
        "id": row["id"].strip(),
        "drug": row["药品"].strip(),
        "aliases": [a.strip() for a in row.get("别名", "").split("|") if a.strip()],
        "otc": row.get("是否OTC", "是").strip() in {"是", "Y", "y", "true", "True", "1"},
        "manufacturer_note": row.get("备注", "").strip(),
        "standard_indication": row.get("常规适应症", "").strip(),
        "offlabel_use": row.get("或然症/新用途", "").strip(),
        "syndrome": row.get("适用证型", "").strip(),
        "dosage_note": row.get("用法用量备注", "").strip(),
        "evidence_level": row.get("证据等级", "D").strip().upper(),
        "evidence_source": row.get("证据来源", "").strip(),
        "source_urls": [u.strip() for u in row.get("来源URL", "").split("|") if u.strip()],
        "precautions": [p.strip() for p in row.get("注意事项", "").split("|") if p.strip()],
        "symptoms": [s.strip() for s in row.get("关联症状标签", "").split("|") if s.strip()],
        "tags": [],
    }


def main() -> None:
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in kb["entries"]}
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("id"):
                continue
            entry = row_to_entry(row)
            # CSV 字段较简，合并时保留 JSON 里更完整的字段
            if entry["id"] in by_id:
                old = by_id[entry["id"]]
                for k, v in entry.items():
                    if v in ("", [], None):
                        continue
                    if k in {"aliases", "source_urls", "precautions", "symptoms"} and not v:
                        continue
                    old[k] = v
            else:
                by_id[entry["id"]] = entry
    kb["entries"] = list(by_id.values())
    KB_PATH.write_text(json.dumps(kb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"entries={len(kb['entries'])} -> {KB_PATH}")


if __name__ == "__main__":
    main()
