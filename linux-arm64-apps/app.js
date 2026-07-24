(() => {
  const apps = window.ARM64_APPS || [];
  const categories = window.ARM64_CATEGORIES || [];
  const statusMap = window.ARM64_STATUS || {};

  const filtersEl = document.getElementById("filters");
  const listEl = document.getElementById("app-list");
  const searchEl = document.getElementById("search");
  const metaEl = document.getElementById("result-meta");

  let activeCategory = "all";
  let query = "";

  function categoryLabel(id) {
    return categories.find((c) => c.id === id)?.label || id;
  }

  function renderFilters() {
    filtersEl.innerHTML = "";
    categories.forEach((cat) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "filter-btn";
      btn.id = `filter-${cat.id}`;
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", String(cat.id === activeCategory));
      btn.textContent = cat.label;
      btn.addEventListener("click", () => {
        activeCategory = cat.id;
        renderFilters();
        renderList();
      });
      filtersEl.appendChild(btn);
    });
  }

  function filteredApps() {
    const q = query.trim().toLowerCase();
    return apps.filter((app) => {
      if (activeCategory !== "all" && app.category !== activeCategory) return false;
      if (!q) return true;
      const hay = [app.name, app.summary, app.install, categoryLabel(app.category)]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }

  function renderList() {
    const items = filteredApps().sort((a, b) => a.name.localeCompare(b.name, "en"));
    metaEl.textContent = `共 ${items.length} 款应用`;

    if (!items.length) {
      listEl.innerHTML = `<p class="empty">没有匹配的应用。试试其他关键词，或切换到「全部」。</p>`;
      return;
    }

    listEl.innerHTML = items
      .map((app) => {
        const statusClass = app.status === "official" ? "" : app.status;
        const statusLabel = statusMap[app.status] || app.status;
        return `
          <article class="app-item" data-id="${app.id}">
            <div>
              <h3><a href="${app.homepage}" target="_blank" rel="noopener noreferrer">${app.name}</a></h3>
              <p class="app-summary">${app.summary}</p>
              <p class="app-install">安装提示<br /><code>${app.install}</code></p>
            </div>
            <div class="app-side">
              <span class="status ${statusClass}">${statusLabel}</span>
              <span class="category-tag">${categoryLabel(app.category)}</span>
            </div>
          </article>
        `;
      })
      .join("");
  }

  let searchTimer = 0;
  searchEl.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      query = searchEl.value;
      renderList();
    }, 120);
  });

  renderFilters();
  renderList();
})();
