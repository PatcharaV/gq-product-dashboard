const data = window.GQ_DATA || { products: [] };
const products = data.products || [];
const state = {
  search: "", function: "", series: "", productType: "", innovation: "", recommended: "", stock: "", sort: "innovationDesc",
  page: 1, pageSize: 25,
};

const baht = new Intl.NumberFormat("th-TH", {
  style: "currency", currency: "THB", maximumFractionDigits: 0,
});
const number = new Intl.NumberFormat("th-TH");
const $ = (selector) => document.querySelector(selector);
const els = {
  scrapedAt: $("#scrapedAt"), kpis: $("#kpis"), search: $("#searchInput"),
  function: $("#functionFilter"), series: $("#seriesFilter"),
  innovation: $("#innovationFilter"), recommended: $("#recommendedFilter"),
  stock: $("#stockFilter"), sort: $("#sortSelect"),
  reset: $("#resetButton"), refresh: $("#refreshButton"),
  visibleCount: $("#visibleCount"), collectionDonut: $("#collectionDonut"),
  categoryDonut: $("#categoryDonut"), subcategoryTreemap: $("#subcategoryTreemap"),
  productGrid: $("#productGrid"), pagination: $("#pagination"), pageSize: $("#pageSizeSelect"),
  activeFilters: $("#activeFilters"),
};

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("th-TH", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok",
  }).format(new Date(value));
}

function uniqueValues(key) {
  return [...new Set(products.map((item) => item[key]).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
}

function uniqueInnovations() {
  return [...new Set(products.flatMap((item) => item.features || []))]
    .sort((a, b) => a.localeCompare(b));
}

function populateSelect(select, firstLabel, values) {
  select.innerHTML = [`<option value="">${firstLabel}</option>`]
    .concat(values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`))
    .join("");
}

function countBy(items, key) {
  return items.reduce((counts, item) => {
    const value = item[key] || "Other";
    counts[value] = (counts[value] || 0) + 1;
    return counts;
  }, {});
}

function uniqueBaseProducts(items) {
  const seen = new Set();
  return items.filter((item) => {
    const id = item.source_product_id || item.id;
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function countProductsBy(items, key) {
  return countBy(uniqueBaseProducts(items), key);
}

const recommendationLabels = {
  new: "สินค้าใหม่",
  bestseller: "สินค้าขายดี",
  bearsize: "ไซส์หมี",
  scrubs: "ชุดสครับ",
};

const recommendationBadgeLabels = {
  new: "ใหม่",
  bestseller: "ขายดี",
  bearsize: "ไซส์หมี",
  scrubs: "สครับ",
};

function visibleRecommendationGroups(item) {
  const groups = [...(item.recommendation_groups || [])];
  if (state.recommended && groups.includes(state.recommended)) {
    return [state.recommended, ...groups.filter((group) => group !== state.recommended)].slice(0, 2);
  }
  return groups.slice(0, 2);
}

function sorter(mode) {
  const price = (item) => item.min_price ?? 0;
  const date = (item) => new Date(item.published_at || item.created_at || 0).getTime();
  const sorters = {
    innovationDesc: (a, b) => (b.innovations || []).length - (a.innovations || []).length || price(a) - price(b),
    priceAsc: (a, b) => price(a) - price(b),
    priceDesc: (a, b) => price(b) - price(a),
    discountDesc: (a, b) => (b.discount_pct || 0) - (a.discount_pct || 0),
    variantsDesc: (a, b) => (b.variant_count || 0) - (a.variant_count || 0),
    newest: (a, b) => date(b) - date(a),
    name: (a, b) => a.title.localeCompare(b.title),
  };
  return sorters[mode] || sorters.innovationDesc;
}

function filteredProducts(excludeKey = "") {
  const query = state.search.trim().toLowerCase();
  return products.filter((item) => {
    const searchable = [
      item.title, item.brand, item.function, item.series, item.product_type, item.description, item.material,
      ...(item.features || []),
      ...(item.colors || []),
      ...(item.innovations || []).flatMap((i) => [i.category, i.benefit, i.evidence]),
    ].join(" ").toLowerCase();
    return (!query || searchable.includes(query))
      && (excludeKey === "function" || !state.function || item.function === state.function)
      && (excludeKey === "series" || !state.series || item.series === state.series)
      && (excludeKey === "productType" || !state.productType || item.product_type === state.productType)
      && (!state.innovation || (item.features || []).includes(state.innovation))
      && (!state.recommended || (item.recommendation_groups || []).includes(state.recommended))
      && (!state.stock || item.availability === state.stock);
  }).sort(sorter(state.sort));
}

function renderKpis(items) {
  const baseProducts = new Set(items.map((item) => item.source_product_id || item.id)).size;
  const rows = [
    ["รุ่นสินค้า", baseProducts],
    ["รายการสินค้า × สี", items.length],
    ["ไซซ์ / ตัวเลือก", items.reduce((sum, item) => sum + item.variant_count, 0)],
    ["มีสินค้า", items.filter((item) => item.availability === "In stock").length],
  ];
  els.kpis.innerHTML = rows.map(([label, value]) =>
    `<article class="kpi"><span>${label}</span><strong>${typeof value === "number" ? number.format(value) : value}</strong></article>`
  ).join("");
}

function renderBarChart(target, rows, limit = 8) {
  const sorted = Object.entries(rows).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, limit);
  const max = Math.max(...sorted.map((row) => row[1]), 1);
  target.innerHTML = sorted.length ? sorted.map(([label, value]) => `
    <div class="bar-row">
      <span title="${escapeHtml(label)}">${escapeHtml(label)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, value / max * 100)}%"></div></div>
      <strong>${number.format(value)}</strong>
    </div>`).join("") : `<p class="empty-note">ไม่พบข้อมูล</p>`;
}

const chartColors = [
  "#ef3340", "#111820", "#f5a623", "#4f7dbc", "#3ca078", "#6f5bd3",
  "#cb5c8d", "#8c684d", "#6f7d8d", "#a8b51a", "#2ca5a5", "#d95f49",
];

const websiteOrder = {
  function: ["Tops", "Bottoms", "Underwear", "Suits & Jackets"],
  series: ["Cool Tech", "Smellblock", "Perfect", "Minimal", "GQWhite", "ProMED", "Performance", "Smart", "GQMax", "Summer", "Sport", "Bear Size", "Other"],
};

function orderedValues(values, key) {
  const order = websiteOrder[key] || [];
  return [...values].sort((a, b) => {
    const aIndex = order.indexOf(a);
    const bIndex = order.indexOf(b);
    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;
    return aIndex - bIndex;
  });
}

function sortedRows(rows, limit = 10) {
  const entries = Object.entries(rows).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (entries.length <= limit) return entries;
  const visible = entries.slice(0, limit - 1);
  const other = entries.slice(limit - 1).reduce((sum, row) => sum + row[1], 0);
  return [...visible, ["Other", other]];
}

function applyChartFilter(key, value) {
  state[key] = state[key] === value ? "" : value;
  state.page = 1;
  if (els[key]) els[key].value = state[key];
  render();
}

function polarPoint(cx, cy, radius, angle) {
  const radians = (angle - 90) * Math.PI / 180;
  return { x: cx + radius * Math.cos(radians), y: cy + radius * Math.sin(radians) };
}

function donutSlicePath(startAngle, endAngle) {
  const start = polarPoint(100, 100, 92, endAngle);
  const end = polarPoint(100, 100, 92, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M 100 100 L ${start.x} ${start.y} A 92 92 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

function renderDonut(target, rows, centerLabel, filterKey) {
  const entries = sortedRows(rows, 20);
  const total = entries.reduce((sum, row) => sum + row[1], 0);
  let angle = 0;
  const slices = entries.map(([label, value], index) => {
    const start = angle;
    angle += total ? value / total * 360 : 0;
    return {
      label, value, start, end: angle,
      color: chartColors[index % chartColors.length],
    };
  });
  const sliceMarkup = slices.length === 1
    ? `<circle class="donut-slice ${state[filterKey] === slices[0].label ? "active" : ""}"
        cx="100" cy="100" r="92" fill="${slices[0].color}"
        data-filter-key="${filterKey}" data-filter-value="${escapeHtml(slices[0].label)}" tabindex="0">
        <title>${escapeHtml(slices[0].label)}: ${number.format(slices[0].value)} รุ่นสินค้า</title>
      </circle>`
    : slices.map((slice) => `
        <path class="donut-slice ${state[filterKey] === slice.label ? "active" : ""}"
          d="${donutSlicePath(slice.start, slice.end)}"
          fill="${slice.color}" data-filter-key="${filterKey}"
          data-filter-value="${escapeHtml(slice.label)}" tabindex="0">
          <title>${escapeHtml(slice.label)}: ${number.format(slice.value)} รุ่นสินค้า</title>
        </path>`).join("");
  target.innerHTML = `
    <div class="donut-wrap">
      <div class="donut-chart">
        <svg viewBox="0 0 200 200" role="img" aria-label="${escapeHtml(centerLabel)}">
          ${sliceMarkup}
        </svg>
        <div class="donut-hole">
          <strong>${number.format(total)}</strong>
          ${centerLabel ? `<span>${escapeHtml(centerLabel)}</span>` : ""}
        </div>
      </div>
    </div>
    <div class="chart-legend">
      ${entries.map(([label, value], index) => `
        <button class="legend-item ${state[filterKey] === label ? "active" : ""}" type="button"
          data-filter-key="${filterKey}" data-filter-value="${escapeHtml(label)}">
          <i style="background:${chartColors[index % chartColors.length]}"></i>
          <span title="${escapeHtml(label)}">${escapeHtml(label)}</span>
          <strong>${number.format(value)}</strong>
        </button>`).join("")}
    </div>`;
  target.querySelectorAll("[data-filter-key]").forEach((control) => {
    const activate = () => applyChartFilter(control.dataset.filterKey, control.dataset.filterValue);
    control.addEventListener("click", activate);
    control.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });
  });
}

function renderActiveFilters() {
  const labels = {
    function: "Category", series: "Collection",
    productType: "Sub-category", innovation: "Innovation",
    recommended: "สินค้าแนะนำ", stock: "สถานะ",
  };
  const active = Object.entries(labels).filter(([key]) => state[key]);
  const displayValue = (key, value) => {
    if (key === "recommended") {
      return recommendationLabels[value] || value;
    }
    if (key === "stock") {
      return value === "In stock" ? "มีสินค้า" : "สินค้าหมด";
    }
    return value;
  };
  if (!active.length && !state.search) {
    els.activeFilters.innerHTML = `<span class="filter-hint">คลิกชิ้นกราฟ, ชื่อใน Legend หรือบล็อก Treemap เพื่อเชื่อมโยงและกรองข้อมูลทุกส่วน</span>`;
    return;
  }
  const searchChip = state.search
    ? `<button type="button" data-clear-filter="search"><span>ค้นหา:</span> ${escapeHtml(state.search)} ×</button>`
    : "";
  els.activeFilters.innerHTML = `
    <strong>ตัวกรองที่เลือก</strong>
    ${searchChip}
    ${active.map(([key, label]) => `
      <button type="button" data-clear-filter="${key}"><span>${label}:</span> ${escapeHtml(displayValue(key, state[key]))} ×</button>
    `).join("")}
    <button type="button" class="clear-all" data-clear-all>ล้างทั้งหมด</button>`;
  els.activeFilters.querySelectorAll("[data-clear-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.clearFilter;
      state[key] = "";
      state.page = 1;
      if (els[key]) els[key].value = "";
      render();
    });
  });
  els.activeFilters.querySelector("[data-clear-all]")?.addEventListener("click", resetFilters);
}

function resetFilters() {
  Object.assign(state, {
    search: "", function: "", series: "", productType: "",
    innovation: "", recommended: "", stock: "", sort: "innovationDesc", page: 1,
  });
  Object.entries({
    search: "", function: "", series: "", innovation: "", recommended: "",
    stock: "", sort: "innovationDesc",
  }).forEach(([key, value]) => { els[key].value = value; });
  render();
}

function partitionTreemap(items, x, y, width, height) {
  if (!items.length) return [];
  if (items.length === 1) return [{ ...items[0], x, y, width, height }];
  const total = items.reduce((sum, item) => sum + item.value, 0);
  let running = 0;
  let splitIndex = 1;
  for (let index = 0; index < items.length - 1; index += 1) {
    running += items[index].value;
    splitIndex = index + 1;
    if (running >= total / 2) break;
  }
  const first = items.slice(0, splitIndex);
  const second = items.slice(splitIndex);
  const firstTotal = first.reduce((sum, item) => sum + item.value, 0);
  const ratio = firstTotal / total;
  if (width >= height) {
    const firstWidth = width * ratio;
    return [
      ...partitionTreemap(first, x, y, firstWidth, height),
      ...partitionTreemap(second, x + firstWidth, y, width - firstWidth, height),
    ];
  }
  const firstHeight = height * ratio;
  return [
    ...partitionTreemap(first, x, y, width, firstHeight),
    ...partitionTreemap(second, x, y + firstHeight, width, height - firstHeight),
  ];
}

function renderTreemap(target, rows) {
  const entries = sortedRows(rows, 16)
    .filter(([label]) => label !== "Other")
    .map(([label, value], index) => ({ label, value, color: chartColors[index % chartColors.length] }));
  const blocks = partitionTreemap(entries, 0, 0, 100, 100);
  target.innerHTML = blocks.map((block) => `
    <button class="treemap-block ${state.productType === block.label ? "active" : ""}" type="button"
      style="left:${block.x}%;top:${block.y}%;width:${block.width}%;height:${block.height}%;background:${block.color}"
      data-product-type="${escapeHtml(block.label)}" title="${escapeHtml(block.label)}: ${number.format(block.value)} รุ่นสินค้า">
      <strong>${escapeHtml(block.label)}</strong>
      <span>${number.format(block.value)} รุ่นสินค้า</span>
    </button>`).join("");
  target.querySelectorAll(".treemap-block").forEach((button) => {
    button.addEventListener("click", () => applyChartFilter("productType", button.dataset.productType));
  });
}

function innovationDetails(innovations) {
  if (!innovations.length) return "";
  return `<details>
    <summary>ดูรายละเอียด Innovation</summary>
    <div class="innovation-details">${innovations.map((innovation) => `
      <div class="innovation-item">
        <div><strong>${escapeHtml(innovation.name)}</strong><span>${escapeHtml(innovation.category)}</span></div>
        <p>${escapeHtml(innovation.benefit)}</p>
        <small>หลักฐานจากข้อมูลสินค้า: ${escapeHtml(innovation.evidence)}</small>
      </div>`).join("")}</div>
  </details>`;
}

function consolidateProducts(items) {
  const grouped = new Map();
  items.forEach((item) => {
    const id = item.source_product_id || item.id;
    if (!grouped.has(id)) {
      grouped.set(id, {
        ...item,
        id,
        url: `https://gqsize.com/products/${item.handle}`,
        colors: [],
        materials: [],
        variant_count: 0,
        available_variant_count: 0,
        min_price: null,
        max_price: null,
        compare_at_price: null,
        recommendation_groups: [],
        availability: "Sold out",
      });
    }
    const product = grouped.get(id);
    product.colors.push(item.color || (item.colors || [])[0]);
    if (item.material && item.material !== "ไม่ระบุ") product.materials.push(item.material);
    product.variant_count += item.variant_count || 0;
    product.available_variant_count += item.available_variant_count || 0;
    product.min_price = product.min_price == null
      ? item.min_price
      : Math.min(product.min_price, item.min_price ?? product.min_price);
    product.max_price = product.max_price == null
      ? item.max_price
      : Math.max(product.max_price, item.max_price ?? product.max_price);
    product.compare_at_price = Math.max(product.compare_at_price || 0, item.compare_at_price || 0) || null;
    product.recommendation_groups.push(...(item.recommendation_groups || []));
    if (item.availability === "In stock") {
      product.availability = "In stock";
      if (!product.image || product.image === grouped.get(id).image) product.image = item.image;
    }
  });
  return [...grouped.values()].map((product) => ({
    ...product,
    colors: [...new Set(product.colors.filter(Boolean))],
    materials: [...new Set(product.materials)],
    recommendation_groups: [...new Set(product.recommendation_groups)],
    color_count: new Set(product.colors.filter(Boolean)).size,
  }));
}

function renderProducts(items) {
  const consolidated = consolidateProducts(items);
  els.visibleCount.textContent = `${number.format(consolidated.length)} รุ่น`;
  if (!consolidated.length) {
    els.productGrid.innerHTML = `<div class="empty-state"><strong>ไม่พบสินค้าที่ตรงกับตัวกรอง</strong><span>ลองล้างตัวกรองหรือเปลี่ยนคำค้นหา</span></div>`;
    els.pagination.innerHTML = "";
    return;
  }
  const totalPages = Math.max(1, Math.ceil(consolidated.length / state.pageSize));
  state.page = Math.min(state.page, totalPages);
  const start = (state.page - 1) * state.pageSize;
  const pageItems = consolidated.slice(start, start + state.pageSize);
  els.productGrid.innerHTML = `<div class="product-table-wrap">
    <table class="product-table">
      <thead>
        <tr>
          <th class="image-column">รูป</th>
          <th>สินค้า</th>
          <th>ประเภท / ซีรีส์</th>
          <th>Material</th>
          <th>Innovation</th>
          <th>สี / ลาย</th>
          <th class="price-column">ราคา</th>
          <th>สถานะ</th>
          <th class="action-column"><span class="sr-only">เปิดสินค้า</span></th>
        </tr>
      </thead>
      <tbody>${pageItems.map((item) => {
    const innovations = item.innovations || [];
    const compare = item.compare_at_price && item.compare_at_price > item.min_price;
    const stockClass = item.availability === "In stock" ? "stock" : "sold";
    return `<tr>
      <td>
        <a class="table-product-image" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">
          <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}" loading="lazy" />
        </a>
      </td>
      <td>
        <a class="table-product-name" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
        <div class="table-subline">
          ${escapeHtml(item.brand)}
          ${visibleRecommendationGroups(item).map((group) => `
            <span class="recommended-badge">${escapeHtml(recommendationBadgeLabels[group] || group)}</span>
          `).join("")}
        </div>
      </td>
      <td>
        <strong class="cell-primary">${escapeHtml(item.function)}</strong>
        <span class="cell-secondary">${escapeHtml(item.series)}</span>
        <span class="cell-secondary">${escapeHtml(item.product_type)}</span>
      </td>
      <td class="material-cell">
        <span title="${escapeHtml(item.materials.join(", ") || "ไม่ระบุ")}">
          ${escapeHtml(item.materials.slice(0, 2).join(", ") || "ไม่ระบุ")}
          ${item.materials.length > 2 ? ` +${number.format(item.materials.length - 2)}` : ""}
        </span>
      </td>
      <td class="innovation-cell">
        ${innovations.length
          ? `<div class="innovation-chips">${innovations.slice(0, 2).map((i) => `<span class="innovation-chip">${escapeHtml(i.name)}</span>`).join("")}</div>
             ${innovations.length > 2 ? `<span class="more-count">+${number.format(innovations.length - 2)}</span>` : ""}
             ${innovationDetails(innovations)}`
          : `<span class="no-innovation">ไม่พบข้อมูล</span>`}
      </td>
      <td class="color-cell">
        <div class="table-color-list" title="${escapeHtml(item.colors.join(", "))}">
          ${item.colors.map((color) => `<span>${escapeHtml(color)}</span>`).join("")}
        </div>
        <small>${number.format(item.color_count)} สี · ${number.format(item.variant_count)} ไซซ์ / ตัวเลือก</small>
      </td>
      <td class="table-price">
        <strong>${baht.format(item.min_price || 0)}</strong>
        ${compare ? `<del>${baht.format(item.compare_at_price)}</del>` : ""}
      </td>
      <td><span class="pill ${stockClass}">${item.availability === "In stock" ? "มีสินค้า" : "สินค้าหมด"}</span></td>
      <td><a class="open-product" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer" title="เปิดหน้าสินค้า" aria-label="เปิด ${escapeHtml(item.title)}">↗</a></td>
    </tr>`;
  }).join("")}</tbody>
    </table>
  </div>`;
  renderPagination(consolidated.length, totalPages, start, pageItems.length);
}

function renderPagination(totalItems, totalPages, start, visibleItems) {
  const pageButtons = [];
  const first = Math.max(1, state.page - 2);
  const last = Math.min(totalPages, first + 4);
  for (let page = Math.max(1, last - 4); page <= last; page += 1) {
    pageButtons.push(`<button type="button" data-page="${page}" class="${page === state.page ? "active" : ""}">${number.format(page)}</button>`);
  }
  els.pagination.innerHTML = `
    <span>แสดง ${number.format(start + 1)}-${number.format(start + visibleItems)} จาก ${number.format(totalItems)}</span>
    <div>
      <button type="button" data-page="${state.page - 1}" ${state.page === 1 ? "disabled" : ""} aria-label="หน้าก่อนหน้า">‹</button>
      ${pageButtons.join("")}
      <button type="button" data-page="${state.page + 1}" ${state.page === totalPages ? "disabled" : ""} aria-label="หน้าถัดไป">›</button>
    </div>`;
  els.pagination.querySelectorAll("button[data-page]").forEach((button) => {
    button.addEventListener("click", () => {
      state.page = Number(button.dataset.page);
      renderProducts(filteredProducts());
      document.querySelector(".product-list-heading").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function render() {
  const items = filteredProducts();
  const collectionContext = filteredProducts("series");
  const categoryContext = filteredProducts("function");
  const subcategoryContext = filteredProducts("productType");
  renderKpis(items);
  renderActiveFilters();
  renderDonut(
    els.collectionDonut,
    countProductsBy(collectionContext, "series"),
    "PRODUCTS",
    "series"
  );
  renderDonut(
    els.categoryDonut,
    countProductsBy(categoryContext, "function"),
    "PRODUCTS",
    "function"
  );
  renderTreemap(els.subcategoryTreemap, countProductsBy(subcategoryContext, "product_type"));
  renderProducts(items);
}

function bind() {
  populateSelect(els.function, "ทุกประเภท", orderedValues(uniqueValues("function"), "function"));
  populateSelect(els.series, "ทุกซีรีส์", orderedValues(uniqueValues("series"), "series"));
  populateSelect(els.innovation, "ทุก Innovation", uniqueInnovations());
  els.scrapedAt.textContent = formatDate(data.scraped_at);
  [[els.search, "search"], [els.function, "function"],
    [els.series, "series"], [els.innovation, "innovation"], [els.recommended, "recommended"],
    [els.stock, "stock"], [els.sort, "sort"]]
    .forEach(([element, key]) => element.addEventListener("input", () => {
      state[key] = element.value;
      state.page = 1;
      render();
    }));

  els.pageSize.addEventListener("change", () => {
    state.pageSize = Number(els.pageSize.value);
    state.page = 1;
    renderProducts(filteredProducts());
  });

  els.reset.addEventListener("click", resetFilters);

  els.refresh.addEventListener("click", async () => {
    const original = els.refresh.textContent;
    els.refresh.textContent = "กำลังอัปเดต...";
    els.refresh.disabled = true;
    try {
      const response = await fetch("/api/refresh", { method: "POST" });
      if (!response.ok) throw new Error(`อัปเดตไม่สำเร็จ (HTTP ${response.status})`);
      window.location.reload();
    } catch (error) {
      alert(error.message || "อัปเดตข้อมูลไม่สำเร็จ");
      els.refresh.textContent = original;
      els.refresh.disabled = false;
    }
  });
}

bind();
render();
