import { useEffect, useMemo, useRef, useState } from "react";
import catalog from "./catalog.json";
import WanPage from "./WanPage";
import { defaultSku, onImageError, productCover, productFrames, skuCover, skuFrames } from "./media";
import type { Catalog, Product, Sku } from "./types";

const data = catalog as Catalog;

function parseHash() {
  const hash = decodeURIComponent(window.location.hash.replace(/^#\/?/, ""));
  const wan = hash === "wan" || hash.startsWith("wan/") || hash.startsWith("wan?");
  let selectedId: string | null = null;
  if (hash.startsWith("product/")) {
    selectedId = hash.slice("product/".length);
  } else if (hash.startsWith("wan/product/")) {
    selectedId = hash.slice("wan/product/".length);
  }
  return { page: wan ? "wan" : "gallery", selectedId } as const;
}

function useHashProduct(products: Product[]) {
  const [{ page, selectedId }, setRoute] = useState(parseHash);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const selected = products.find((product) => product.id === selectedId) ?? null;
  const open = (product: Product) => {
    const prefix = page === "wan" ? "wan/" : "";
    window.location.hash = `${prefix}product/${encodeURIComponent(product.id)}`;
  };
  const close = () => {
    window.location.hash = page === "wan" ? "wan" : "";
    setRoute((current) => ({ ...current, selectedId: null }));
  };
  return { page, selected, open, close };
}

function CustomCursor({ active }: { active: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const move = (event: MouseEvent) => {
      node.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
    };
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);
  return <div ref={ref} className={`cursor-dot${active ? " is-on" : ""}`} />;
}

function HoverReel({ product, playing }: { product: Product; playing: boolean }) {
  const frames = productFrames(product);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!playing || frames.length < 2) {
      setIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % frames.length);
    }, 2600);
    return () => window.clearInterval(timer);
  }, [playing, frames.length]);

  const frame = frames[index] || productCover(product);
  return (
    <img
      src={frame}
      alt={product.name}
      className="reel-image"
      onError={onImageError(product.cover, product.cover_local)}
    />
  );
}

function FeaturedRow({ products, onOpen }: { products: Product[]; onOpen: (product: Product) => void }) {
  const [active, setActive] = useState(0);
  const [hovering, setHovering] = useState(false);

  return (
    <section
      className="featured"
      onMouseLeave={() => {
        setHovering(false);
        setActive(0);
      }}
    >
      {products.map((product, index) => {
        const isActive = index === active;
        return (
          <button
            key={product.id}
            type="button"
            className={`featured-card${isActive ? " is-active" : ""}`}
            style={{ background: product.plate_color || "#201910" }}
            onMouseEnter={() => {
              setHovering(true);
              setActive(index);
            }}
            onFocus={() => setActive(index)}
            onClick={() => onOpen(product)}
          >
            <HoverReel product={product} playing={isActive} />
            {isActive ? (
              <div className="glass-card">
                <div className="glass-kicker">{product.category}</div>
                <div className="glass-title">{product.name}</div>
                <div className="glass-line" />
                <div className="glass-meta">
                  {product.sku_count} 个规格 · {product.summary || product.dosage_forms[0]}
                </div>
              </div>
            ) : (
              <span className="spine-name">{product.name}</span>
            )}
          </button>
        );
      })}
      <CustomCursor active={hovering} />
    </section>
  );
}

function groupedSkus(product: Product): { form: string; skus: Sku[] }[] {
  if (product.dosage_forms.length <= 1) {
    return [{ form: "", skus: product.skus }];
  }
  const groups = product.dosage_forms
    .map((form) => ({ form, skus: product.skus.filter((item) => item.dosage_form === form) }))
    .filter((group) => group.skus.length > 0);
  const seen = new Set(groups.flatMap((group) => group.skus.map((item) => item.id)));
  const rest = product.skus.filter((item) => !seen.has(item.id));
  if (rest.length > 0) groups.push({ form: "其他", skus: rest });
  return groups;
}

function ProductDetail({ product, onClose }: { product: Product; onClose: () => void }) {
  const initial = defaultSku(product);
  const [skuId, setSkuId] = useState(initial?.id ?? "");
  const sku = product.skus.find((item) => item.id === skuId) ?? product.skus[0];
  const frames = skuFrames(sku, product);
  const [frame, setFrame] = useState(frames[0] || skuCover(sku, product));

  useEffect(() => {
    const next = skuFrames(sku, product);
    setFrame(next[0] || skuCover(sku, product));
  }, [skuId, product]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()} role="dialog" aria-label={product.name}>
        <button className="drawer-close" type="button" onClick={onClose}>
          关闭
        </button>
        <div className="drawer-media" style={{ background: sku?.plate_color || product.plate_color || "#201910" }}>
          <img src={frame} alt={`${product.name} ${sku?.spec_label || ""}`} onError={onImageError(sku?.cover || product.cover, sku?.cover_local || product.cover_local)} />
          {frames.length > 1 ? (
            <div className="thumbs">
              {frames.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={`thumb${item === frame ? " is-on" : ""}`}
                  onClick={() => setFrame(item)}
                >
                  <img src={item} alt="" />
                </button>
              ))}
            </div>
          ) : null}
        </div>
        <div className="drawer-body">
          <p className="eyebrow">主信息 · 产品层</p>
          <h2>{product.name}</h2>
          {product.aliases.length > 0 ? <p className="aliases">亦作 {product.aliases.join("、")}</p> : null}
          <p className="lead">{product.indications || product.summary}</p>
          <dl className="facts">
            <div>
              <dt>品类</dt>
              <dd>{product.category}</dd>
            </div>
            <div>
              <dt>剂型</dt>
              <dd>{product.dosage_forms.join(" / ")}</dd>
            </div>
            <div>
              <dt>规格数</dt>
              <dd>{product.sku_count}</dd>
            </div>
          </dl>

          <p className="eyebrow">次信息 · 规格层</p>
          <div className="sku-groups">
            {groupedSkus(product).map((group) => (
              <div key={group.form || "all"} className="sku-group">
                {group.form ? <p className="sku-group-label">{group.form}</p> : null}
                <div className="sku-list">
                  {group.skus.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`sku-chip${item.id === sku?.id ? " is-on" : ""}`}
                      onClick={() => {
                        setSkuId(item.id);
                        const next = skuFrames(item, product);
                        setFrame(next[0] || skuCover(item, product));
                      }}
                    >
                      {item.spec_label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          {sku ? (
            <dl className="facts secondary">
              <div>
                <dt>包装规格</dt>
                <dd>{sku.spec_label}</dd>
              </div>
              {sku.spec_label !== sku.specification ? (
                <div>
                  <dt>原标注</dt>
                  <dd>{sku.specification}</dd>
                </div>
              ) : null}
              <div>
                <dt>剂型</dt>
                <dd>{sku.dosage_form}</dd>
              </div>
              <div>
                <dt>生产企业</dt>
                <dd>{(sku.manufacturers && sku.manufacturers.length > 0 ? sku.manufacturers : [sku.manufacturer]).join(" / ")}</dd>
              </div>
              {sku.marketing_authorization_holder ? (
                <div>
                  <dt>上市许可持有人</dt>
                  <dd>{sku.marketing_authorization_holder}</dd>
                </div>
              ) : null}
              {sku.production_address ? (
                <div>
                  <dt>生产地址</dt>
                  <dd>{sku.production_address}</dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          {product.indication_variants.length > 0 ? (
            <>
              <p className="eyebrow">补充 · 说明书异文</p>
              <ul className="variants">
                {product.indication_variants.map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
            </>
          ) : null}

          {sku?.detail_url ? (
            <a className="official" href={sku.detail_url} target="_blank" rel="noreferrer">
              打开同仁堂官网详情
            </a>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

export default function App() {
  const featured = data.products.filter((product) => product.featured).slice(0, 6);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState("全部");
  const { page, selected, open, close } = useHashProduct(data.products);

  const forms = useMemo(() => {
    const bag = new Set<string>();
    data.products.forEach((product) => product.dosage_forms.forEach((item) => bag.add(item)));
    return ["全部", ...Array.from(bag).sort((a, b) => a.localeCompare(b, "zh-CN"))];
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim();
    return data.products.filter((product) => {
      if (form !== "全部" && !product.dosage_forms.includes(form)) return false;
      if (!needle) return true;
      const hay = [product.name, ...product.aliases, product.summary, product.indications, ...product.manufacturers].join(" ");
      return hay.includes(needle);
    });
  }, [form, query]);

  if (page === "wan") {
    return (
      <>
        <WanPage
          products={data.products}
          featured={data.products.filter((product) => product.featured)}
          onOpen={open}
          source={data.source}
        />
        {selected ? <ProductDetail key={selected.id} product={selected} onClose={close} /> : null}
      </>
    );
  }

  return (
    <div className="page">
      <header className="nav">
        <a className="brand" href="#top">
          同仁堂<sup>®</sup>
        </a>
        <nav>
          <a href="#featured">名方</a>
          <a href="#wan">药丸</a>
          <a href="#catalog">全部药品</a>
          <a href={data.source} target="_blank" rel="noreferrer">
            数据来源
          </a>
        </nav>
      </header>

      <main>
        <section className="intro" id="top">
          <p className="kicker">{data.section}</p>
          <h1>双龙标中成药</h1>
          <p className="deck">
            {data.product_count} 个产品 · {data.sku_count} 个包装规格。每张图已统一到 4:5 画布并按包装取色垫边，悬停名方卡可展开轮播。
          </p>
        </section>

        <div id="featured">
          <FeaturedRow products={featured} onOpen={open} />
        </div>

        <section className="catalog" id="catalog">
          <div className="catalog-bar">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索品名、主治、厂家"
            />
            <select value={form} onChange={(event) => setForm(event.target.value)}>
              {forms.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <span className="count">{filtered.length} 个产品</span>
          </div>
          <div className="grid">
            {filtered.map((product) => (
              <button key={product.id} type="button" className="grid-card" onClick={() => open(product)}>
                <span className="grid-photo" style={{ background: product.plate_color || "#201910" }}>
                  <img
                    src={productCover(product)}
                    alt={product.name}
                    loading="lazy"
                    onError={onImageError(product.cover, product.cover_local)}
                  />
                  <em>{product.sku_count} 规格</em>
                </span>
                <div className="grid-copy">
                  <strong>{product.name}</strong>
                  <span>{product.summary || product.dosage_forms[0]}</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      </main>
      {selected ? <ProductDetail key={selected.id} product={selected} onClose={close} /> : null}
    </div>
  );
}
