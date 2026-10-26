import { useMemo, useState } from "react";
import { onImageError, productCover } from "./media";
import type { Product } from "./types";
import "./wan.css";

const FORM_KIND: Record<string, string> = {
  大蜜丸: "honey",
  小蜜丸: "honey",
  丸剂: "honey",
  水蜜丸: "water",
  浓缩水蜜丸: "water",
  浓缩丸: "dense",
  水丸: "dense",
  糊丸: "dense",
  微丸: "dense",
  滴丸剂: "dense",
  浓缩水丸: "dense",
  包糖衣的浓缩水丸: "dense",
  胶囊剂: "capsule",
  软胶囊: "capsule",
  片剂: "tablet",
  薄膜衣片: "tablet",
  素片: "tablet",
  糖衣片: "tablet",
  颗粒剂: "granule",
  散剂: "granule",
  酒剂: "liquid",
  酊剂: "liquid",
  口服液: "liquid",
  合剂: "liquid",
  糖浆剂: "liquid",
  膏滋: "paste",
  煎膏剂: "paste",
  胶剂: "paste",
};

const LEGEND = [
  ["honey", "大蜜丸"],
  ["wax", "蜡壳"],
  ["water", "水蜜丸"],
  ["dense", "浓缩丸 / 水丸"],
  ["capsule", "胶囊"],
  ["tablet", "片剂"],
  ["granule", "颗粒 / 散"],
  ["liquid", "酒 / 液"],
];

function pillKind(product: Product): string {
  if (product.name.includes("安宫") || product.skus.some((sku) => sku.spec_label.includes("蜡壳"))) {
    return "wax";
  }
  return FORM_KIND[product.dosage_forms[0]] || "honey";
}

function formKind(form: string): string {
  return FORM_KIND[form] || "honey";
}

export default function WanPage({
  products,
  featured,
  onOpen,
  source,
}: {
  products: Product[];
  featured: Product[];
  onOpen: (product: Product) => void;
  source: string;
}) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [form, setForm] = useState("全部");
  const [hoverId, setHoverId] = useState<string | null>(null);

  const forms = useMemo(() => {
    const bag = new Map<string, number>();
    products.forEach((product) => {
      product.dosage_forms.forEach((item) => bag.set(item, (bag.get(item) || 0) + 1));
    });
    return Array.from(bag.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN"))
      .slice(0, 14);
  }, [products]);

  const cloud = useMemo(() => {
    const list = form === "全部" ? products : products.filter((item) => item.dosage_forms.includes(form));
    return [...list].sort((a, b) => Number(b.featured) - Number(a.featured) || b.sku_count - a.sku_count);
  }, [form, products]);

  return (
    <div className="wan-shell" data-theme={theme}>
      <header className="wan-nav">
        <a className="brand" href="#wan">
          同仁堂<sup>®</sup>
        </a>
        <nav>
          <a href="#top">名方画廊</a>
          <a href="#wan" className="is-on">
            药丸
          </a>
          <a href="#catalog">全部药品</a>
          <a href={source} target="_blank" rel="noreferrer">
            数据来源
          </a>
        </nav>
        <button
          type="button"
          className="wan-toggle"
          aria-label={theme === "dark" ? "切换日间" : "切换夜间"}
          onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
        >
          {theme === "dark" ? "日" : "夜"}
        </button>
      </header>

      <section className="wan-hero">
        <p className="wan-kicker">双龙标 · 药丸柜</p>
        <h1>同仁堂</h1>
        <button type="button" className="brand-orb" onClick={() => featured[0] && onOpen(featured[0])} aria-label="打开安宫牛黄丸">
          <span className="core">同</span>
          <span className="shell shell-left" />
          <span className="shell shell-right" />
        </button>
        <p className="wan-deck">
          原模版用扁平胶囊标签陈列技能。这里改成可开合的蜡壳，并用蜜丸、水丸、浓缩丸、片剂的真实剂型材质，承载 442 个品种。悬停可开壳看主治，点击进入该品。
        </p>
      </section>

      <div className="form-tray" role="tablist" aria-label="按剂型筛选">
        <button
          type="button"
          className={`pill-wan honey${form === "全部" ? " is-on" : ""}`}
          onClick={() => setForm("全部")}
        >
          全部 · {products.length}
        </button>
        {forms.map(([name, count]) => (
          <button
            key={name}
            type="button"
            className={`pill-wan ${formKind(name)}${form === name ? " is-on" : ""}`}
            onClick={() => setForm(name)}
          >
            {name}
            <small>{count}</small>
          </button>
        ))}
      </div>

      <div className="pill-cloud">
        {cloud.map((product) => (
          <button
            key={product.id}
            type="button"
            className={`pill-wan ${pillKind(product)}${product.featured ? " is-featured" : ""}`}
            onMouseEnter={() => setHoverId(product.id)}
            onMouseLeave={() => setHoverId((current) => (current === product.id ? null : current))}
            onFocus={() => setHoverId(product.id)}
            onBlur={() => setHoverId((current) => (current === product.id ? null : current))}
            onClick={() => onOpen(product)}
          >
            {product.name}
            {hoverId === product.id ? (
              <span className="pill-tip">
                {product.dosage_forms.join(" / ")}
                <br />
                {product.summary || product.indications.slice(0, 36)}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      <section className="wan-about">
        <h2>从胶囊标签到一粒药</h2>
        <p>
          作品集模版把技能做成白胶囊 chip。中成药的「胶囊」本来就是剂型：大蜜丸是金黄蜡光，水蜜丸更小更密，浓缩丸近墨，安宫等名方用朱红蜡壳。点开中间蜡壳，里面是蜜丸芯；点一粒药丸，进入该品种详情与品规图。
        </p>
        <div className="wan-legend">
          {LEGEND.map(([kind, label]) => (
            <span key={kind}>
              <i className={`pill-wan ${kind}`} />
              {label}
            </span>
          ))}
        </div>
      </section>

      <section className="wan-works">
        <h2>名方陈列</h2>
        <div className="work-grid">
          {featured.map((product) => (
            <button key={product.id} type="button" className="work-card" onClick={() => onOpen(product)}>
              <img
                src={productCover(product)}
                alt={product.name}
                style={{ background: product.plate_color || "#201910" }}
                onError={onImageError(product.cover, product.cover_local)}
              />
              <strong>{product.name}</strong>
              <em>{product.summary || product.dosage_forms[0]}</em>
            </button>
          ))}
        </div>
      </section>

      <footer className="wan-foot">同仁堂双龙标中成药 · 药丸柜 · 对应 v0 作品集胶囊模块</footer>
    </div>
  );
}
