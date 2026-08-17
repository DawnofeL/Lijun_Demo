/* 路由与各视图。hash 路由，每个视图是一个 async 函数：
   调 Api 取数、调 UI 渲染。侧栏依角色决定显示哪些入口，
   但那只是介面便利，真正的权限判断在后端，前端隐藏入口不构成安全边界。 */

const { el } = UI;

const NAV = [
  { group: "起點", items: [
    { hash: "today",      label: "今日工作台" },
  ]},
  { group: "每日", items: [
    { hash: "sessions",   label: "工作計劃" },
    { hash: "residents",  label: "住客主檔" },
  ]},
  { group: "合規", items: [
    { hash: "compliance", label: "合規看板" },
    { hash: "audit",      label: "操作留痕", roles: ["supervisor", "admin"] },
  ]},
  { group: "智能", items: [
    { hash: "assistant",  label: "智能助理" },
    { hash: "knowledge",  label: "規範問答" },
  ]},
  { group: "專案", items: [
    { hash: "roadmap",    label: "待辦與風險" },
  ]},
];

const DEMO_ACCOUNTS = [
  ["chan",  "職員 · 陳美儀", "只看得到自己的節次"],
  ["wong",  "組長 · 黃淑芬", "看得到本院舍全部"],
  ["admin", "管理員 · 吳偉明", "看得到三間院舍"],
];

const state = { user: null, banner: "示範資料，非真實住客" };

/* ------------------------------------------------------------------ 登入 */

function renderLogin(message) {
  Orb.warm();   // 提前準備 GPU 裝置與著色器，思考膠囊出現時不用等
  const username = el("input", { type: "text", id: "u", value: "wong", autocomplete: "username" });
  const password = el("input", { type: "password", id: "p", value: "demo1234", autocomplete: "current-password" });
  const button = el("button", { class: "btn primary", text: "登入" });

  async function submit() {
    button.disabled = true;
    button.textContent = "登入中";
    try {
      const result = await Api.post("/login", { username: username.value.trim(), password: password.value });
      Api.token.set(result.token);
      state.user = result.user;
      history.replaceState(null, "", location.pathname + "#today");
      render();
    } catch (error) {
      UI.toast(error.message, true);
      button.disabled = false;
      button.textContent = "登入";
    }
  }

  button.addEventListener("click", submit);
  [username, password].forEach((input) =>
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); }));

  const accounts = el("div", { class: "accounts" }, [
    el("div", { class: "k", text: "示範帳號 · 密碼一律 demo1234" }),
  ].concat(DEMO_ACCOUNTS.map(([name, title, note]) =>
    el("div", { class: "row", onclick: () => { username.value = name; password.value = "demo1234"; submit(); } }, [
      el("span", { text: title }),
      el("code", { text: name }),
    ]))));

  document.getElementById("root").replaceChildren(
    el("div", { class: "login-wrap" }, [
      el("div", { class: "login" }, [
        el("div", { class: "card" }, [
          el("div", { class: "eyebrow", text: "SEDNA CARE" }),
          el("h2", { text: "院舍照護管理原型" }),
          el("p", { class: "hint", text: "自研原型，非任何既有系統的複製。資料為生成的示範資料，與真實住客無關。" }),
          message ? UI.notice("info", message) : null,
          el("div", { class: "field" }, [el("label", { text: "帳號" }), username]),
          el("div", { class: "field" }, [el("label", { text: "密碼" }), password]),
          button,
          accounts,
        ]),
      ]),
    ]),
  );
}

/* ------------------------------------------------------------------ 外框 */

/* 外殼常駐。視圖切換只換 main 的內容，側欄整棵樹不重建，
   指示器才有前後兩個位置可量，才滑得起來。 */
let shell = null;

function renderShell(activeHash) {
  if (shell && shell.owner === state.user.id) {
    shell.root.querySelectorAll(".nav-item").forEach((a) => {
      a.classList.toggle("active", a.getAttribute("href") === "#" + activeHash);
    });
    placeMarker(true);
    return shell.main;
  }
  return buildShell(activeHash);
}

function buildShell(activeHash) {
  const groups = NAV.map((group) => {
    const items = group.items.filter((item) => !item.roles || item.roles.includes(state.user.role));
    if (!items.length) return null;
    return el("div", { class: "nav-group" }, [
      el("span", { text: group.group }),
    ].concat(items.map((item) => el("a", {
      class: "nav-item" + (item.hash === activeHash ? " active" : ""),
      href: "#" + item.hash,
    }, [el("i", { class: "dot" }), item.label]))));
  }).filter(Boolean);

  const sidebar = el("aside", { class: "rail" }, [
    el("div", { class: "brand" }, [
      el("div", { class: "mark", text: "SEDNA CARE" }),
      el("h1", { text: "院舍照護管理" }),
      el("div", { class: "sub", text: "原型 v0.1 · 自研" }),
    ]),
    // 整個導航共用一枚指示器。每組一枚的話跨組切換時舊的消失、
    // 新的憑空出現，中間沒有位移可以動畫。
    el("nav", { class: "nav" }, [el("i", { class: "nav-marker" })].concat(groups)),
    el("div", { class: "rail-foot" }, [
      el("div", { class: "demo-chip", text: state.banner }),
    ]),
  ]);

  const main = el("main", { class: "main" });
  const root = el("div", { class: "shell" }, [sidebar, main, identityMenu()]);
  document.getElementById("root").replaceChildren(root);
  shell = { root, main, owner: state.user.id };
  requestAnimationFrame(() => placeMarker(false));   // 首次不動畫
  return main;
}

/* 把滑動指示器擺到目前選中項的位置。
   animate 為 false 時關掉過渡，用於首次渲染。 */
function placeMarker(animate = true) {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  const marker = nav.querySelector(".nav-marker");
  const active = nav.querySelector(".nav-item.active");
  if (!marker) return;
  if (!active) { marker.classList.remove("on"); return; }

  // offsetTop 是相對 .nav（它是 position: relative 的），不必逐層累加
  const skip = !animate || Motion.reduced();
  if (skip) marker.style.transition = "none";
  marker.style.height = active.offsetHeight + "px";
  marker.style.transform = "translateY(" + active.offsetTop + "px)";
  marker.classList.add("on");
  if (skip) requestAnimationFrame(() => { marker.style.transition = ""; });
}

/* 右上角常驻的身份入口。演示时要频繁切换三个角色，这个必须显眼。 */
function identityMenu() {
  const user = state.user;
  const panel = el("div", { class: "id-panel" }, [
    el("div", { class: "id-panel-head" }, [
      el("div", { class: "id-name", text: user.display_name }),
      el("div", { class: "id-meta", text: user.role_label + " · " + user.position
        + (user.facility_name ? " · " + user.facility_name : "") }),
      el("div", { class: "id-scope", text: user.scope_label }),
    ]),
    el("div", { class: "id-sep" }),
    el("button", { class: "id-act", text: "切換帳號", onclick: () => signOut("切換帳號，請重新登入。") }),
    el("button", { class: "id-act danger", text: "登出", onclick: () => signOut() }),
  ]);

  const trigger = el("button", { class: "id-trigger" }, [
    el("span", { class: "id-avatar", text: user.display_name.slice(-2) }),
    el("span", { class: "id-label", text: user.role_label }),
    el("span", { class: "id-caret", text: "▾" }),
  ]);

  const wrap = el("div", { class: "identity" }, [trigger, panel]);
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    wrap.classList.toggle("open");
  });
  // 委派到 document 上的關閉行為只掛一次。原本每次建外殼都掛一個，
  // 登出再登入就會累積，久了每次點擊要跑一串殭屍監聽。
  if (!document.__idClose) {
    document.__idClose = true;
    document.addEventListener("click", () => {
      document.querySelectorAll(".identity.open").forEach((n) => n.classList.remove("open"));
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        document.querySelectorAll(".identity.open").forEach((n) => n.classList.remove("open"));
      }
    });
  }
  return wrap;
}

function signOut(message) {
  Api.token.clear();
  state.user = null;
  shell = null;
  history.replaceState(null, "", location.pathname);
  renderLogin(message || "已登出。");
}

/* ------------------------------------------------------------------ 今日工作台 */

async function viewToday(main) {
  const data = await Api.get("/today");
  const a = data.attention;

  const stat = (k, v, m, tone) => UI.stat(k, v, m, tone);

  /* 時間線：按時間排，不按功能分。進行中那一節的圓點是亮的。 */
  const timeline = el("div", { class: "tl" }, data.timeline.map((row) => {
    const mark = row.is_now ? "now"
               : row.status === "已完成" ? "done"
               : row.status === "未能出席" ? "absent" : "";
    return el("div", { class: "ev " + mark }, [
      el("div", { class: "t mono", text: row.start_time }),
      el("div", { class: "who" }, [
        el("span", { text: row.resident_name }),
        el("small", { text: "（" + row.bed_no + "）· " + row.service_type }),
      ]),
      el("div", { class: "ev-right" }, [
        row.is_now ? el("span", { class: "now-tag", text: "進行中" }) : null,
        el("span", { class: "dim", style: "font-size:12.5px", text: row.staff_name }),
        UI.badge(row.badge, row.status),
      ]),
    ]);
  }));

  /* 入口卡：功能從導航降級成入口，有事才進去。 */
  const entry = (title, desc, badges, hash) => {
    const node = el("div", { class: "entry", onclick: () => { location.hash = "#" + hash; } }, [
      el("div", { class: "h" }, [el("b", { text: title }), el("span", { class: "arrow", text: "→" })]),
      el("p", { text: desc }),
      el("div", { class: "badge-row" }, badges),
    ]);
    return node;
  };

  const canSeeAudit = ["supervisor", "admin"].includes(state.user.role);

  await UI.mount(main, [
    UI.pageHead("TODAY", "今日工作台",
      data.facility + "　·　" + data.scope_label + "　·　進來先看到今天要做什麼，而不是一份功能目錄"),

    el("div", { class: "grid c4", style: "margin-bottom:38px" }, [
      stat("今日節次", data.summary.total, data.date),
      stat("已完成", data.summary.done, null, "ok"),
      stat("待接收", data.summary.pending, "含已接收未開始", "warn"),
      stat("未能出席", data.summary.absent, "需記錄原因", "bad"),
    ]),

    UI.section("今日時間線", "按時間排，不按功能分", [
      data.timeline.length ? timeline : UI.empty("今天沒有排定的節次"),
      data.summary.total > data.timeline.length
        ? el("div", { class: "dim", style: "font-size:12px;margin-top:14px",
            text: "僅顯示前 " + data.timeline.length + " 節，其餘請到工作計劃查看。" })
        : null,
    ]),

    UI.section("需要處理", "側欄的紅點在這裡展開成具體的事", [
      el("div", { class: "entries" }, [
        entry("未填表的節次", "已完成但沒有服務表單，稽查時無法舉證。",
              [UI.badge(a.gaps ? "behind" : "met", a.gaps + " 節待補")], "compliance"),
        entry("評估即將到期", "180 天周期內未重評，逾期需列明原因補做。",
              [UI.badge("at_risk", a.due_soon + " 位 30 天內"),
               UI.badge("overdue", a.overdue + " 位已逾期或從未評估")], "compliance"),
        entry("服務量落後", "本週資助目標達成不足六成的住客。",
              [UI.badge(a.behind ? "behind" : "met", a.behind + " 位")], "compliance"),
      ]),
    ]),

    canSeeAudit && data.recent.length
      ? UI.section("最近操作", "誰在什麼時候做了什麼", [
          el("div", { class: "log" }, data.recent.map((row) => el("div", { class: "log-row" }, [
            el("div", { class: "log-when" }, [
              el("div", { class: "log-date mono", text: row.created_at.slice(0, 10) }),
              el("div", { class: "log-time mono", text: row.created_at.slice(11, 16) }),
            ]),
            el("div", { class: "log-body" }, [
              el("div", { class: "log-text" }, [
                el("strong", { text: row.actor_name }),
                el("span", { class: "log-role", text: "（" + row.actor_role + "）" }),
                el("span", { text: "　" + row.summary }),
              ]),
            ]),
            el("div", { class: "log-more dim", text: "" }),
          ]))),
        ])
      : null,
  ]);
}

/* ------------------------------------------------------------------ 工作計劃 */

async function viewSessions(main) {
  const bounds = await Api.get("/sessions/dates");
  const picker = el("input", { type: "date", value: bounds.today,
    min: bounds.first_date || "", max: bounds.last_date || "" });

  async function load() {
    const body = main.querySelector("#session-body");
    body.replaceChildren(UI.loading());
    const data = await Api.get("/sessions?session_date=" + picker.value);

    const summary = el("div", { class: "grid c4", style: "margin-bottom:16px" }, [
      UI.stat("節次總數", data.items.length, picker.value),
      UI.stat("已完成", data.summary["已完成"] || 0, null, "ok"),
      UI.stat("待接收", (data.summary["待接收"] || 0) + (data.summary["已接收"] || 0), "含已接收", "warn"),
      UI.stat("未能出席", data.summary["未能出席"] || 0, null, "bad"),
    ]);

    const columns = [
      { label: "時間", render: (r) => el("span", { class: "mono", text: r.start_time + "–" + r.end_time }) },
      { label: "服務", key: "service_type" },
      { label: "住客", render: (r) => r.resident_name + "（" + r.bed_no + "）" },
      { label: "資助類別", render: (r) => UI.badge("plain", r.funding_type) },
      { label: "軌道", render: (r) => el("span", { class: "dim", text: r.service_track }) },
      { label: "治療師", key: "staff_name" },
      { label: "院舍", render: (r) => el("span", { class: "dim", text: r.facility_name }) },
      { label: "狀態", render: (r) => UI.badge(r.badge, r.status) },
    ];

    body.replaceChildren(summary, UI.table(columns, data.items, "當日沒有節次"));
  }

  picker.addEventListener("change", load);

  await UI.mount(main, [
    UI.pageHead("WORK SESSIONS", "工作計劃",
      "同一個頁面，三種角色看到的資料範圍不同。範圍判斷在後端，前端只顯示結果。"),
    UI.section("節次列表", null, [
      el("div", { class: "toolbar" }, [
        el("span", { class: "dim", text: "日期" }), picker,
        UI.scopeTag(state.user.scope_label),
      ]),
      el("div", { id: "session-body" }),
    ]),
  ]);
  await load();
}

/* ------------------------------------------------------------------ 住客主檔 */

async function viewResidents(main) {
  const canImport = ["supervisor", "admin"].includes(state.user.role);
  const fileInput = el("input", { type: "file", accept: ".xlsx,.xlsm", style: "display:none" });
  const resultBox = el("div");

  fileInput.addEventListener("change", async () => {
    if (!fileInput.files.length) return;
    resultBox.replaceChildren(UI.loading("匯入中"));
    try {
      const result = await Api.upload("/residents/import", fileInput.files[0]);
      const rows = result.errors.map((e) =>
        el("div", { class: "dim", style: "font-size:13px", text: "第 " + e.line + " 列　" + (e.bed_no || "—") + "　" + e.reason }));
      resultBox.replaceChildren(
        UI.notice(result.failed ? "warn" : "info",
          "匯入完成：成功 " + result.imported + " 筆，失敗 " + result.failed + " 筆"),
        ...rows);
      UI.toast("匯入完成");
      load();
    } catch (error) {
      resultBox.replaceChildren(UI.notice("warn", error.message));
    }
    fileInput.value = "";
  });

  async function load() {
    const box = main.querySelector("#resident-body");
    box.replaceChildren(UI.loading());
    const data = await Api.get("/residents");
    const columns = [
      { label: "床號", render: (r) => el("span", { class: "mono", text: r.bed_no }) },
      { label: "姓名", key: "name" },
      { label: "性別", key: "gender" },
      { label: "資助類別", render: (r) => UI.badge("plain", r.funding_type) },
      { label: "服務軌道", render: (r) => el("span", { class: "dim", text: r.service_track }) },
      { label: "週目標", key: "weekly_target", num: true },
      { label: "上次評估", render: (r) => el("span", { class: "mono dim", text: r.last_assessed || "—" }) },
      { label: "評估狀態", render: (r) => UI.badge(r.assessment.level, r.assessment.level_label) },
      { label: "院舍", render: (r) => el("span", { class: "dim", text: r.facility_name }) },
    ];
    if (canImport) {
      columns.push({ label: "", render: (r) => {
        const btn = el("button", { class: "row-del", title: "從名單移除" }, [
          el("span", { text: "移除" })]);
        btn.addEventListener("click", async () => {
          if (btn.dataset.armed !== "1") {
            btn.dataset.armed = "1";
            btn.classList.add("armed");
            btn.firstChild.textContent = "確認移除";
            setTimeout(() => {
              if (!btn.isConnected) return;
              btn.dataset.armed = ""; btn.classList.remove("armed");
              btn.firstChild.textContent = "移除";
            }, 3200);
            return;
          }
          btn.disabled = true;
          try {
            await Api.del("/residents/" + r.id);
            const row = btn.closest("tr");
            row.classList.add("removing");
            await Motion.wait(Motion.reduced() ? 0 : 280);
            UI.toast(r.name + "（" + r.bed_no + "）已從名單移除");
            load();
          } catch (error) {
            UI.toast(error.message, true);
            btn.disabled = false;
            btn.dataset.armed = "";
            btn.classList.remove("armed");
            btn.firstChild.textContent = "移除";
          }
        });
        return btn;
      }});
    }
    box.replaceChildren(
      el("div", { class: "dim", style: "font-size:13px;margin-bottom:14px",
        text: "共 " + data.items.length + " 位住客" + (canImport ? "　·　移除採軟刪除，歷史紀錄保留可查" : "") }),
      UI.table(columns, data.items));
  }

  await UI.mount(main, [
    UI.pageHead("RESIDENTS", "住客主檔", "支援 Excel 批次匯入，逐列校驗，失敗的列會列明原因。"),
    UI.section("名單", null, [
      el("div", { class: "toolbar" }, [
        UI.scopeTag(state.user.scope_label),
        el("button", { class: "btn ghost", text: "下載匯入模板",
          onclick: () => Api.download("/residents/template", "residents_template.xlsx") }),
        canImport
          ? el("button", { class: "btn primary", text: "匯入 Excel", onclick: () => fileInput.click() })
          : el("span", { class: "dim", style: "font-size:13px", text: "匯入僅限組長與管理員" }),
        fileInput,
      ]),
      resultBox,
      el("div", { id: "resident-body" }),
    ]),
  ]);
  await load();
}

/* ------------------------------------------------------------------ 合規看板 */

async function viewCompliance(main) {
  const [targets, assessments, gaps] = await Promise.all([
    Api.get("/compliance/targets"),
    Api.get("/compliance/assessments"),
    Api.get("/compliance/gaps"),
  ]);

  const targetCols = [
    { label: "床號", render: (r) => el("span", { class: "mono", text: r.bed_no }) },
    { label: "住客", key: "name" },
    { label: "資助類別", render: (r) => UI.badge("plain", r.funding_type) },
    { label: "本週", render: (r) => el("span", { class: "mono", text: r.completed + " / " + r.target }) },
    { label: "達成率", render: (r) => el("div", { style: "display:flex;align-items:center;gap:10px" }, [
      UI.bar(r.level, r.rate), el("span", { class: "mono", text: r.rate + "%" })]) },
    { label: "狀態", render: (r) => UI.badge(r.level, r.level_label) },
  ];

  const assessCols = [
    { label: "床號", render: (r) => el("span", { class: "mono", text: r.bed_no }) },
    { label: "住客", key: "name" },
    { label: "上次評估", render: (r) => el("span", { class: "mono dim", text: r.last_assessed || "—" }) },
    { label: "剩餘天數", num: true, render: (r) => el("span", { class: "mono", text: r.days_left === null ? "—" : r.days_left }) },
    { label: "狀態", render: (r) => UI.badge(r.level, r.level_label) },
  ];

  const gapCols = [
    { label: "日期", render: (r) => el("span", { class: "mono", text: r.session_date }) },
    { label: "時間", render: (r) => el("span", { class: "mono dim", text: r.start_time }) },
    { label: "服務", key: "service_type" },
    { label: "住客", render: (r) => r.resident_name + "（" + r.bed_no + "）" },
    { label: "治療師", key: "staff_name" },
  ];

  await UI.mount(main, [
    UI.pageHead("COMPLIANCE", "合規看板",
      "資助目標達成率與 180 天評估周期。判斷邏輯是純函數，可單獨測試。"),

    UI.section("資助目標達成率", targets.week.label, [
      targets.week.auto_switched ? UI.notice("info", targets.week.reason) : null,
      el("div", { class: "grid c3", style: "margin-bottom:22px" }, [
        UI.stat("已達標", targets.summary.met, "住客數", "ok"),
        UI.stat("有風險", targets.summary.at_risk, "達成 60% 以上", "warn"),
        UI.stat("落後", targets.summary.behind, "達成不足 60%", "bad"),
      ]),
      UI.table(targetCols, targets.items.slice(0, 20)),
      el("div", { class: "dim", style: "font-size:12px;margin-top:14px",
        text: "依達成率由低至高排序，僅顯示前 20 筆。" }),
    ]),

    UI.section("評估周期追蹤", "每 " + assessments.cycle_days + " 天一次", [
      el("div", { class: "grid c4", style: "margin-bottom:22px" }, [
        UI.stat("從未評估", assessments.summary.never, "須於入住 30 日內完成", "bad"),
        UI.stat("已逾期", assessments.summary.overdue, null, "bad"),
        UI.stat("即將到期", assessments.summary.due_soon, "30 天內", "warn"),
        UI.stat("正常", assessments.summary.normal, null, "ok"),
      ]),
      UI.table(assessCols, assessments.items.slice(0, 15)),
    ]),

    UI.section("已完成但未填表", "共 " + gaps.total + " 節", [
      UI.notice("warn", "紙本轉系統時最常見的缺口。節次已完成，服務表單卻沒有對應紀錄，稽查時無法舉證。"),
      UI.table(gapCols, gaps.items.slice(0, 15), "沒有缺口"),
    ]),
  ]);
}

/* ------------------------------------------------------------------ 操作留痕 */

async function viewAudit(main) {
  const head = () => UI.pageHead("AUDIT TRAIL", "操作留痕",
    "紙本紀錄有個隱性優點，塗改的痕跡擦不掉。系統若不留痕，在監管與投訴面前反而比紙更弱。");

  const data = await Api.get("/audit");

  /* 一行一件事，用一句中文說完。需要細節才點開，
     展開的是「欄位、原本、改為」三欄，不讓使用者去讀 JSON。 */
  function row(item) {
    const line = el("div", { class: "log-row" }, [
      el("div", { class: "log-when" }, [
        el("div", { class: "log-date mono", text: item.date }),
        el("div", { class: "log-time mono", text: item.time }),
      ]),
      el("div", { class: "log-body" }, [
        el("div", { class: "log-text" }, [
          el("strong", { text: item.actor_name }),
          el("span", { class: "log-role", text: "（" + item.actor_role + "）" }),
          el("span", { text: "　" + item.summary }),
        ]),
        el("div", { class: "log-tag" }, [UI.badge("plain", item.action)]),
      ]),
    ]);

    if (!item.details.length) {
      line.appendChild(el("div", { class: "log-more dim", text: "無細節" }));
      return line;
    }

    const table = el("table", { class: "log-detail" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: "欄位" }), el("th", { text: "原本" }), el("th", { text: "改為" })])]),
      el("tbody", {}, item.details.map((d) => el("tr", {}, [
        el("td", { text: d.field }),
        el("td", { class: "dim", text: d.before }),
        el("td", { text: d.after }),
      ]))),
    ]);

    // 收合用 grid-template-rows 0fr→1fr，裁切必須靠中間這層 div，
    // overflow:hidden 直接放在 table 上瀏覽器不會照做。
    const box = el("div", { class: "log-detail-box" }, [
      el("div", { class: "log-detail-inner" }, [table]),
    ]);
    const toggle = el("button", { class: "log-more", text: "詳細" });
    toggle.addEventListener("click", () => {
      const open = line.classList.toggle("open");
      toggle.textContent = open ? "收起" : "詳細";
    });
    line.appendChild(toggle);
    line.appendChild(box);
    return line;
  }

  await UI.mount(main, [
    head(),
    UI.section("留痕紀錄", "最近 " + data.items.length + " 筆", [
      UI.notice("info", data.note),
      el("div", { class: "log" }, data.items.map(row)),
    ]),
  ]);
}

/* ------------------------------------------------------------------ 智能助理 */

async function viewAssistant(main) {
  const head = () => UI.pageHead("ASSISTANT", "智能助理",
    "回答流程與系統問題。規範條文請到「規範問答」查，那裡每句都標註原文出處。");

  const status = await Api.get("/assistant/status");

  const history = [];                       // 只在前端保存，重整即清空
  const thread = el("div", { class: "chat-thread" });
  const input = el("input", { type: "text", placeholder: "問點什麼，例如：三種角色分別看得到什麼資料？" });
  const send = el("button", { class: "btn primary", text: "送出" });

  function bubble(role, text) {
    const node = el("div", { class: "bubble " + role }, [
      role === "assistant" ? Orb.node("orb-xs") : null,
      el("div", { class: "bubble-body", text: text }),
    ]);
    thread.appendChild(node);
    // 只滾對話區。scrollIntoView 會把整頁一起帶著滾，頁面會跳。
    thread.scrollTo({ top: thread.scrollHeight, behavior: Motion.reduced() ? "auto" : "smooth" });
    return node.querySelector(".bubble-body");
  }

  async function ask(text) {
    const question = (text || input.value).trim();
    if (!question || send.disabled) return;
    input.value = "";
    send.disabled = true;
    thread.classList.add("live");

    bubble("user", question);
    history.push({ role: "user", content: question });

    const body = bubble("assistant", "");
    body.classList.add("typing");

    // 先在後台收 0.9 秒只攢不吐，之後按穩定節奏放出來。
    // 直接照模型的節奏畫會一卡一卡，攢一段再吐才是一條順的字流。
    let answer = "";
    const type = Motion.typer((text) => {
      MD.into(body, text);                       // 模型輸出走 Markdown 渲染
      thread.scrollTop = thread.scrollHeight;
    });
    try {
      await Api.stream("/assistant/chat", { messages: history }, (piece) => {
        answer += piece;
        type.push(piece);
      });
      await type.end();
      history.push({ role: "assistant", content: answer });
    } catch (error) {
      type.cancel();
      body.textContent = error.message;
      body.classList.add("failed");
    }
    body.classList.remove("typing");
    send.disabled = false;
    input.focus();
  }

  send.addEventListener("click", () => ask());
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !send.disabled) ask();
  });

  const starters = el("div", { class: "chips" }, status.starters.map((text) =>
    el("div", { class: "chip", text: text, onclick: () => ask(text) })));

  await UI.mount(main, [
    head(),
    el("div", { class: "card chat" }, [
      el("div", { class: "card-head" }, [
        el("h3", { text: "對話" }),
        el("div", { class: "card-note" }, [
          el("span", { class: "pulse" + (status.available ? " on" : "") }),
          el("span", { text: status.available
            ? "已連接 " + status.model + " · 人設 " + status.persona_chars + " 字"
            : "未設定模型金鑰" }),
        ]),
      ]),
      thread,
      starters,
      el("div", { class: "ask-row", style: "margin-top:16px" }, [input, send]),
      el("div", { class: "dim", style: "font-size:12px;margin-top:12px",
        text: "助理不提供任何臨床判斷或醫療建議。對話僅保存在本次瀏覽階段，重整即清空。" }),
    ]),
  ]);
}

/* ------------------------------------------------------------------ 規範問答 */

async function viewKnowledge(main) {
  const status = await Api.get("/knowledge/status");

  const input = el("input", { type: "text", placeholder: "例如：住客跌倒之後的處理流程是什麼" });
  const button = el("button", { class: "btn primary", text: "查詢" });
  const output = el("div");

  async function ask(question) {
    input.value = question || input.value;
    if (!input.value.trim()) return;
    button.disabled = true;
    output.replaceChildren(UI.thinking("檢索中，正在比對規範原文"));
    // 最短显示 700ms。检索走本地索引时几十毫秒就回来了，
    // 不压一下加载态会一闪而过，看起来像没反应。这是防闪烁，不是假装在算。
    const shownAt = performance.now();
    const settle = async () => {
      const left = 700 - (performance.now() - shownAt);
      if (left > 0) await new Promise((r) => setTimeout(r, left));
    };
    try {
      const result = await Api.post("/knowledge/ask", { question: input.value.trim() });
      await settle();
      await Motion.swapOut(output);
      const sources = result.passages.map((p) =>
        el("details", { class: "source" }, [
          el("summary", {}, [el("span", { class: "n", text: p.rank }), p.citation]),
          el("div", { class: "body", text: p.text }),
        ]));
      output.replaceChildren(
        UI.withCitations(result.answer),
        result.passages.length
          ? el("div", { class: "sources" }, [
              el("div", { class: "lbl", text: "引用出處 · " + result.passages.length + " 段" }),
              ...sources,
            ])
          : null,
      );
      Motion.swapIn(output);
      Motion.stagger([...output.querySelectorAll(".source")], 40, 6);
    } catch (error) {
      await settle();
      await Motion.swapOut(output);
      output.replaceChildren(UI.notice("warn", error.message));
      Motion.swapIn(output);
    }
    button.disabled = false;
  }

  button.addEventListener("click", () => ask());
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });

  const modeText = status.llm_available
    ? "已連接模型 · " + status.chunks + " 個段落"
    : "未設定模型金鑰，走預置答案 · " + status.chunks + " 個段落";

  await UI.mount(main, [
    UI.pageHead("KNOWLEDGE", "規範問答",
      "答案只依據已入庫的文件，每句標註出處。庫中沒有依據時會明確回覆找不到，不會自由發揮。"),
    el("div", { class: "card" }, [
      el("div", { class: "card-head" }, [
        el("h3", { text: "內部規範查詢" }),
        el("div", { class: "card-note" }, [
          el("span", { class: "pulse" + (status.llm_available ? " on" : "") }),
          el("span", { text: modeText }),
        ]),
      ]),
      el("div", { class: "ask-row" }, [input, button]),
      el("div", { class: "chips" }, status.suggestions.map((s) =>
        el("div", { class: "chip", text: s, onclick: () => ask(s) }))),
      output,
    ]),
    el("details", { class: "design-note" }, [
      el("summary", { text: "為什麼這樣設計" }),
      el("div", { class: "design-body" }, [
        el("p", { text: "受監管的場景裡，答錯比答不出來嚴重得多。所以這裡的設計目標不是什麼都能答，"
                      + "而是答的每一句都能追回原文，答不出來會明說。" }),
        el("p", { text: "切段按標題層級而不是固定字數。規範文件的一條條款就是一個語義單元，"
                      + "硬切會把條款劈成兩半，檢索出來的片段就沒法當作出處使用。" }),
        el("p", { text: "檢索用關鍵詞加權而非向量。查詢詞與原文用詞高度重合，這個做法效果穩定且完全可解釋，"
                      + "出錯能立刻看出是哪一步的問題。打分只算二元詞不算單字，否則無關提問會誤命中。" }),
        el("p", { class: "dim", text: "文件為示範文本，依公開資料改寫，非官方版本。"
                      + "本原型為自研，介面、資訊架構與資料模型均獨立設計。" }),
      ]),
    ]),
  ]);
}

/* ------------------------------------------------------------------ 待辦與風險 */

async function viewRoadmap(main) {
  const data = await Api.get("/roadmap");

  const tone = (status) =>
    status === "原型限制" || status === "本原型不做" ? "plain"
      : status === "待確認" || status === "待訪談" ? "at_risk" : "behind";

  const items = data.items.map((item) =>
    el("div", { class: "risk" }, [
      el("div", { class: "top" }, [
        el("h4", { text: item.item }),
        UI.badge(tone(item.status), item.status),
      ]),
      el("div", { class: "why", text: item.why }),
      el("div", { class: "by", text: "卡在：" + item.blocked_by }),
    ]));

  await UI.mount(main, [
    UI.pageHead("ROADMAP", "待辦與風險",
      "這個原型是兩天寫的骨架。真系統的工作量不在這些畫面上，在下面這些事情上。"),
    UI.section("刻意不做的部分", data.items.length + " 項", [
      UI.notice("info", data.note),
      ...items,
    ]),
  ]);
}

/* ------------------------------------------------------------------ 路由 */

const VIEWS = {
  today: viewToday,
  sessions: viewSessions,
  assistant: viewAssistant,
  residents: viewResidents,
  compliance: viewCompliance,
  audit: viewAudit,
  knowledge: viewKnowledge,
  roadmap: viewRoadmap,
};

let currentHash = null;
let renderToken = 0;

async function render() {
  if (!state.user) { shell = null; renderLogin(); return; }

  let hash = (location.hash || "#today").slice(1);
  if (!VIEWS[hash]) hash = "today";

  const switching = currentHash !== null && currentHash !== hash && shell;
  const main = renderShell(hash);
  currentHash = hash;

  // 每次渲染換一個 token，用來擋住快速連點造成的競態
  main.dataset.token = String(++renderToken);

  // 舊視圖各元素分別滑走。這裡「不 await」是關鍵：
  // 視圖的資料請求在動畫期間就發出去，兩件事並行。
  // 之前是先播完動畫才開始請求，中間那段空窗就是你看到的「卡一下」。
  main.__flyDone = switching ? Motion.leaveMain(main) : Promise.resolve();

  try {
    await VIEWS[hash](main);
  } catch (error) {
    // 出錯也要有完整的頁面：標題、說明、回去的路。
    // 只丟一條錯誤訊息的話，使用者連自己在哪一頁都看不出來。
    const forbidden = /僅限|403/.test(error.message);
    await UI.mount(main, [
      UI.pageHead(forbidden ? "NO ACCESS" : "ERROR",
        forbidden ? "沒有存取權限" : "這一頁載入失敗",
        forbidden
          ? "你目前的角色看不到這個模組。權限判斷在後端，前端把入口藏起來只是介面便利。"
          : "請稍後再試一次。若持續失敗，服務可能已經停止。"),
      UI.section(forbidden ? "說明" : "錯誤訊息", null, [
        UI.notice("warn", error.message),
        el("button", { class: "btn ghost", text: "回到今日工作台",
          onclick: () => { location.hash = "#today"; } }),
      ]),
    ]);
  }
}

async function boot() {
  Api.setUnauthorizedHandler(() => { state.user = null; renderLogin("登入已失效，請重新登入。"); });

  try {
    const health = await Api.get("/health");
    if (health.banner) state.banner = health.banner;
  } catch (_) { /* 服务未起时仍显示登入页 */ }

  // 不做自动恢复。token 只在记忆体里，重整即失效，一律从登入页进。
  render();
}

window.addEventListener("hashchange", render);
boot();
