/* 渲染原件。接收资料回传 DOM 节点的纯函数。
   视图层只负责取数与组装，不写具体的 DOM 细节。 */

const UI = (() => {

  function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "html") node.innerHTML = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
      else node.setAttribute(key, value);
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined || child === false) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  const badge = (kind, label) => el("span", { class: "badge " + kind, text: label });

  /* 數值帶 data-count，渲染完由 Motion.enter 統一滾動。 */
  const stat = (key, value, meta, tone = "") => {
    const numeric = Number.isInteger(value);
    return el("div", { class: "stat " + tone }, [
      el("div", { class: "k", text: key }),
      el("div", Object.assign({ class: "v", text: String(value) },
        numeric ? { "data-count": String(value) } : {})),
      meta ? el("div", { class: "m", text: meta }) : null,
    ]);
  };

  function bar(level, rate) {
    return el("div", { class: "bar " + level }, [
      el("i", { "data-rate": String(rate), style: "width:0%" }),
    ]);
  }

  /* columns: [{ key, label, num?, render? }] */
  function table(columns, rows, emptyText = "沒有資料") {
    if (!rows.length) return el("div", { class: "empty", text: emptyText });

    const head = el("tr", {}, columns.map((c) =>
      el("th", { class: c.num ? "num" : "", text: c.label })));

    const body = rows.map((row) =>
      el("tr", {}, columns.map((c) => {
        const cell = el("td", { class: c.num ? "num" : "" });
        const content = c.render ? c.render(row) : row[c.key];
        if (content === null || content === undefined) cell.textContent = "";
        else if (typeof content === "object") cell.appendChild(content);
        else cell.textContent = String(content);
        return cell;
      })));

    return el("div", { class: "table-wrap" }, [
      el("table", {}, [el("thead", {}, [head]), el("tbody", {}, body)]),
    ]);
  }

  const loading = (text = "載入中") => el("div", { class: "loading", text });

  /* AI 思考指示。液態玻璃球加一行掃光文字，只在等模型時出現。 */
  function thinking(text = "檢索中") {
    return el("div", { style: "padding:22px 2px" }, [
      el("div", { class: "think" }, [
        Orb.node("orb-xs"),
        el("span", { class: "lbl", text: text }),
      ]),
    ]);
  }
  const empty = (text) => el("div", { class: "empty", text });
  const notice = (kind, text) => el("div", { class: "notice " + kind, text });
  const scopeTag = (text) => el("div", { class: "scope-tag", text });

  function card(title, note, children) {
    const head = el("div", { class: "card-head" }, [
      el("h3", { text: title }),
      note ? el("div", { class: "card-note", text: note }) : null,
    ]);
    return el("div", { class: "card" }, [head].concat(children || []));
  }

  /* ornament 是右侧可选的装饰件，目前只有液态玻璃球用它 */
  /* 區塊：靠留白與小標題分隔，不套框。頁面的主結構用它，
     只有真正需要獨立成一張紙的東西才用 card。 */
  function section(title, note, children) {
    const head = el("div", { class: "section-head" }, [
      el("h3", { text: title }),
      note ? el("div", { class: "section-note" }, [
        typeof note === "string" ? document.createTextNode(note) : note]) : null,
    ]);
    return el("section", { class: "section" }, [head].concat(children || []));
  }

  function pageHead(eyebrow, title, description, ornament) {
    return el("div", { class: "page-head" }, [
      el("div", { class: "txt" }, [
        el("div", { class: "eyebrow", text: eyebrow }),
        el("h2", { text: title }),
        description ? el("p", { text: description }) : null,
      ]),
      ornament || null,
    ]);
  }

  /* 視圖統一走這裡掛內容，不要自己 replaceChildren。

     它做三件事：等舊視圖的離場動畫播完（資料請求是在動畫期間並行發出的，
     所以通常等不到什麼）、換上新內容、再讓頂層區塊依序浮起。
     token 用來擋住快速連點造成的競態：晚到的舊請求不會蓋掉新視圖。 */
  async function mount(main, nodes, token) {
    /* token 是「這一輪渲染」的編號，由 render() 產生、視圖原樣傳進來。

       必須由呼叫端傳入，不能在這裡讀 main.dataset.token：讀的時候拿到的
       永遠是「當前最新」那個號，跟自己比一定相等，於是過期的視圖會若無其事
       地把新視圖蓋掉。症狀是登入後立刻點側欄，落在新頁上的卻是今日工作台。
       非同步的續行必須自己記得屬於哪一輪，這件事只能靠傳參。 */
    const mine = token !== undefined ? token : main.dataset.token;
    if (main.__flyDone) await main.__flyDone;
    if (main.dataset.token !== mine) return false;
    main.replaceChildren(...[].concat(nodes).filter(Boolean));
    Motion.enterMain(main);
    Motion.enter(main);
    return true;
  }

  let toastTimer = null;
  function toast(message, bad = false) {
    document.querySelectorAll(".toast").forEach((n) => n.remove());
    const node = el("div", { class: "toast" + (bad ? " bad" : ""), text: message });
    document.body.appendChild(node);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.remove(), 3200);
  }

  /* 把答案里的 [1] [2] 标成高亮，让引用一眼可见 */
  /* 把答案切成行，逐行浮現，並把 [1] [2] 標成高亮引用。 */
  function withCitations(text) {
    const node = el("div", { class: "answer" });
    const lines = String(text).split("\n");
    lines.forEach((line, index) => {
      const row = el("div", { class: "line" });
      row.style.setProperty("--d", Math.min(index, 10) * 55 + "ms");
      for (const part of line.split(/(\[\d+\])/g)) {
        if (/^\[\d+\]$/.test(part)) row.appendChild(el("span", { class: "cite-mark", text: part }));
        else if (part) row.appendChild(document.createTextNode(part));
      }
      if (!line) row.innerHTML = "&nbsp;";
      node.appendChild(row);
    });
    return node;
  }

  return { el, badge, stat, bar, table, loading, thinking, empty, notice, scopeTag,
           card, section, pageHead, toast, withCitations, mount };
})();
