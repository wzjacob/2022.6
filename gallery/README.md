# 同仁堂双龙标 · 中成药画廊

从同仁堂官网「中成药」栏目抓取公开目录，按品种聚合，做成两个可浏览的页面：

- **名方画廊**：悬停展开的货架卡 + 网格目录（参考 v0 hover portfolio）
- **药丸柜**：把作品集模版里的扁平胶囊标签，换成蜜丸 / 蜡壳 / 水丸等真实剂型（参考 [v0 Portfolio Website](https://v0.app/templates/portfolio-website-0lD8VbAP9yI)）

数据来源：[同仁堂双龙标产品 · 中成药](https://www.tongrentang.com/jtProductList/d502e93816624e6780a8e959701ec3af/1.html)

---

## 页面怎么用

```bash
cd gallery
pnpm install
pnpm dev
```

浏览器打开：

| 地址 | 页面 |
| --- | --- |
| http://127.0.0.1:5173/ | 名方画廊 |
| http://127.0.0.1:5173/#wan | 药丸柜 |
| http://127.0.0.1:5173/#product/安宫牛黄丸 | 画廊里打开某品种详情 |
| http://127.0.0.1:5173/#wan/product/安宫牛黄丸 | 药丸柜里打开同一详情 |

顶栏「名方 / 药丸 / 全部药品」可来回切。详情抽屉按 **Esc** 或点关闭；点某一品规会切换到该规格自己的包装图。

构建：

```bash
cd gallery && pnpm build
```

---

## 两个页面分别做什么

### 1. 名方画廊 `#`

上沿 6 张名方卡：未激活时竖排品名、包装取色底板；悬停展开并轮播该品种图片。下方是 442 个品种的 4:5 网格，可按品名 / 主治 / 厂家搜索，按剂型筛选。

详情分两层：

- **产品层**：品名、功能主治、剂型
- **规格层**：归一后的品规芯片；多剂型（如六味地黄丸）按大蜜丸 / 水蜜丸 / 浓缩丸分组

### 2. 药丸柜 `#wan`

对照作品集模版的结构，把「技能胶囊」整层换成药：

| 原模版 | 本页 |
| --- | --- |
| 人名 | 同仁堂 |
| 方头像 | 朱红蜡壳，悬停裂开，露出金蜜丸芯 |
| 白胶囊技能标签 | 442 粒品种药丸，按剂型上色 |
| 点标签无业务 | 点剂型药丸筛选，点品种进详情 |
| 暗 / 亮主题 | 黑漆柜 / 宣纸日间 |

剂型材质：大蜜丸金黄、蜡壳朱红、水蜜丸蜜棕、浓缩丸近墨、胶囊红白两截、片剂扁圆、颗粒散剂、酒液。

---

## 数据规模

| 项 | 数量 |
| --- | --- |
| 官网中成药条目（SKU） | 733 |
| 聚合后的品种 | 442 |
| 归一后的品规芯片 | 717 |
| 名方（featured） | 安宫牛黄丸、六味地黄丸、同仁乌鸡白凤丸、金匮肾气丸、同仁牛黄清心丸、同仁大活络丸、国公酒、阿胶 |
| 优化图（WebP） | 品种封面 + 画廊帧 + 每品规封面，约 77MB |

官网同一规格常有多种写法（`3g×2丸` 与 `每丸重3g，每盒装2丸。`）。聚合时先归一成短标签（`3克 × 2丸`），再合并重复品规。安宫牛黄丸从 13 条重复 chip 收成 8 个。

---

## 数据从哪来

流水线都在仓库根目录的 `scripts/`：

```text
官网列表 + 详情
    → scrape_tongrentang.py
    → data/tongrentang/products.json（.jsonl / .csv）
    → aggregate_products.py
    → products_aggregated.json（品种 + 品规）
    → optimize_product_images.py
    → gallery/public/optimized/*.webp
    → gallery/src/catalog.json
```

### 抓取

```bash
python3 scripts/scrape_tongrentang.py --download-images
```

只抓中成药栏目（约 46 页），字段包括名称、品类、包装规格、剂型、功能主治、生产企业、上市许可持有人、生产地址、详情图等。原图在 `data/tongrentang/images/`，体积大，用 Git LFS 存。

已有 JSON 时补下图片：

```bash
python3 scripts/scrape_tongrentang.py --from-json data/tongrentang/products.json --download-images
```

### 聚合

```bash
python3 scripts/aggregate_products.py
```

按去掉「【同仁堂】」和括号后的品名归并 SKU。产品层保留主治、剂型、厂家；规格层保留包装、生产企业、官网详情链接。

### 出图

```bash
python3 scripts/optimize_product_images.py
```

- 避开商标 / logo 图，优先包装正面
- 统一 800×1000（4:5），`contain` 居中，按包装主色垫边
- 导出 WebP；每个品规另有自己的封面，供详情切换

本地原图若仍是 LFS 指针，画廊会走官网 URL 或已生成的 `/optimized/` 图。

---

## 目录

```text
scripts/
  scrape_tongrentang.py      抓列表与详情
  aggregate_products.py      品种聚合、规格归一
  optimize_product_images.py 4:5 垫边 WebP
data/tongrentang/
  products.json              733 条原始 SKU
  products_aggregated.json   442 个品种
  schema.json                原始字段说明
  images/                    官网原图（LFS）
gallery/
  src/App.tsx                名方画廊 + 路由
  src/WanPage.tsx            药丸柜
  src/catalog.json           前端使用的目录
  public/optimized/          优化后的品种图与品规图
```

---

## 说明

本仓库展示用数据来自同仁堂官网公开产品页，功能主治以说明书为准，不能替代医师或药师指导。商标、包装图版权归权利人所有。
