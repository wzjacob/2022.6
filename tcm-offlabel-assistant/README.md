# 中成药另类用法助手（MVP）

「说明书之外」的中成药或然症 / 老药新用知识库 + 检索问答原型。

> **合规声明**：内容仅供学习与科研参考，不构成诊疗建议。超说明书用药须遵医嘱。

## 为什么做这个

通用大模型常按说明书否定真实探索用法；你的内部线索 + 研究院背书 + 证据分级，才是信息差护城河。

详见 [docs/research_notes.md](docs/research_notes.md)。

## 目录

```
tcm-offlabel-assistant/
├── data/
│   ├── knowledge_base.json   # 结构化知识库（试点 5 药）
│   └── seed_template.csv     # Excel 可打开的种子模板
├── prompts/
│   └── expand_seed.md        # GPT 扩展 1→20+ QA 的 prompt
├── app/
│   └── gradio_app.py         # Gradio + BM25 检索 MVP
├── scripts/
│   ├── smoke_search.py       # 离线检索自检
│   └── feedback_schema.json  # 用户反馈回流字段
└── docs/
    └── research_notes.md
```

## 试点药品

| 药品 | 示例或然症 | 证据要点 |
|------|------------|----------|
| 牛黄清心丸 | 解酒、酒精性脑损伤 | 同仁堂研究院 + 发明专利（A） |
| 乌鸡白凤丸 | 高尿酸/痛风探索、肝损伤 | 研究院探索 + 临床观察，公众有争议（B） |
| 六味地黄丸 | 糖尿病肾病等辅助 | 文献较多，须辨证阴虚（B） |
| 逍遥丸 | 抑郁、乳腺增生等 | 临床/媒体新用途整理（B/C） |
| 藿香正气水 | 蚊虫叮咬外用等 | 经验用法；高乙醇与头孢禁忌（C） |

## 快速开始

```bash
cd tcm-offlabel-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 离线检索自检
python scripts/smoke_search.py

# 启动 Gradio
python app/gradio_app.py
# 浏览器打开 http://127.0.0.1:7860
```

### 可选：LLM 润色

设置兼容 OpenAI 的接口后，在界面勾选「润色」：

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://your-endpoint/v1
export OPENAI_MODEL=qwen2.5-7b-instruct
```

## 数据扩展

1. 用 `data/seed_template.csv` 追加内部偏方（统一字段）。
2. 把行转成 JSON 并入 `knowledge_base.json`（保持 `evidence_level` / `source_urls`）。
3. 用 `prompts/expand_seed.md` 把每条种子扩成 20+ 问答，人工审核后可做 LoRA 微调语料。

## 架构路线

```
MVP（本仓库）：BM25 检索 + 模板回答 + 证据卡片
V2：症状反查 + Embedding 混合检索
V3：Qwen LoRA（辨证语气）+ RAG（事实）+ 药店/诊所账号
```

## 证据等级

- **A**：研究院正式药效学 / 发明专利 / 获批新适应症  
- **B**：同行评议临床研究 / 临床观察  
- **C**：权威媒体或药监科普中的经验总结  
- **D**：民间报道（仅线索）
