/* 動效系統。

   全站只用三條曲線，定義在 tokens.css：
     --spring  交互反饋（hover、按下）
     --glide   位置移動（側欄指示器、視圖切換）
     --fade    淡入淡出

   這裡放的是需要 JS 才做得到的三件事：列表錯峰入場、數字滾動、
   進度條生長。純 CSS 能做的都留在 style.css，不重複實作。

   全部尊重 prefers-reduced-motion：使用者關掉動畫時一律瞬時完成，
   不是放慢，是不做。 */

const Motion = (() => {

  const reduced = () =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

  /* 數字從 0 滾到目標。只對整數用，小數滾起來像壞掉。 */
  function countUp(node, target, duration = 620) {
    if (reduced() || target === 0) { node.textContent = String(target); return; }
    const startedAt = performance.now();
    node.textContent = "0";
    function step(now) {
      const t = Math.min((now - startedAt) / duration, 1);
      node.textContent = String(Math.round(target * easeOutExpo(t)));
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* 進度條從 0 長到目標，延遲起跑讓版面先落定。 */
  function growBar(node, rate, delay = 140) {
    if (reduced()) { node.style.width = Math.min(rate, 100) + "%"; return; }
    node.style.width = "0%";
    setTimeout(() => { node.style.width = Math.min(rate, 100) + "%"; }, delay);
  }

  /* 列表錯峰入場。逐行延遲，但只算前 12 行，
     再多的話最後一行要等半秒才出現，那不是流暢是卡頓。 */
  function stagger(nodes, step = 18, cap = 12) {
    if (reduced()) return;
    nodes.forEach((node, index) => {
      node.style.setProperty("--d", Math.min(index, cap) * step + "ms");
      node.classList.add("rise");
    });
  }

  /* 視圖離場：各元素分別退場，不是整塊一起淡掉。
     由下往上依序滑走，看起來像一疊卡片被抽掉，而不是一張圖片消失。 */
  function leaveMain(main) {
    if (reduced()) return Promise.resolve();
    const parts = [...main.children].flatMap((child) => {
      if (child.classList.contains("page-head")) return [child];
      const inner = [...child.children];
      return inner.length > 1 ? inner : [child];
    });
    parts.forEach((node, index) => {
      node.style.setProperty("--d", Math.min(parts.length - 1 - index, 6) * 26 + "ms");
      node.classList.add("fly-out");
    });
    return wait(Math.min(parts.length - 1, 6) * 26 + 200);
  }

  /* 視圖入場：頂層區塊由上而下依序浮起。
     只做頂層，內部的表格行由 enter() 另外錯峰，兩層疊在一起會太吵。 */
  function enterMain(main) {
    if (reduced()) return;
    [...main.children].forEach((node, index) => {
      node.style.setProperty("--d", Math.min(index, 5) * 42 + "ms");
      node.classList.add("fly-in");
      node.addEventListener("animationend", () => {
        node.classList.remove("fly-in");
        node.style.removeProperty("--d");
      }, { once: true });
    });
  }

  /* 一個視圖渲染完之後統一處理：表格行錯峰、數字滾動、進度條生長。
     視圖層不必各自記得呼叫這些。 */
  function enter(root) {
    stagger([...root.querySelectorAll("tbody tr")]);
    stagger([...root.querySelectorAll(".log-row")], 14);
    stagger([...root.querySelectorAll(".risk")], 26, 8);

    root.querySelectorAll(".stat .v[data-count]").forEach((node) => {
      countUp(node, Number(node.dataset.count));
    });
    root.querySelectorAll(".bar > i[data-rate]").forEach((node) => {
      growBar(node, Number(node.dataset.rate));
    });
  }

  /* 換內容時的交接。舊的先淡出上移，容器高度同時收起來，
     新的再接上去。中間不留空檔，看起來是一件事而不是兩件事。 */
  async function swapOut(box) {
    if (reduced() || !box.firstChild) return;
    box.style.height = box.offsetHeight + "px";
    box.classList.add("swapping");
    await wait(150);
  }

  function swapIn(box) {
    if (reduced()) { box.style.height = ""; return; }
    box.classList.remove("swapping");
    const target = box.scrollHeight;
    box.style.height = "0px";
    requestAnimationFrame(() => {
      box.style.transition = "height .42s var(--glide)";
      box.style.height = target + "px";
      setTimeout(() => { box.style.transition = ""; box.style.height = ""; }, 460);
    });
  }

  /* ── 緩衝吐字 ────────────────────────────────────────────────────────
     模型回來的節奏是不均勻的：有時一口氣塞十幾個字，有時停半秒。
     直接照著畫就是一卡一卡的。

     這裡先讓它在後台跑一段（預設 900ms）只收不吐，攢下一段存貨，
     之後才按固定節奏一個字一個字放出來。速度由存貨量回推：
     存貨多就吐快一點，存貨少就放慢，讓它永遠不會斷流也不會落後太多。
     模型收完之後把剩下的加速吐完。

     使用者看到的是一條穩定的字流，實際上前面那 0.9 秒已經悄悄跑掉了。 */
  function typer(onText, { lead = 900, min = 22, max = 90 } = {}) {
    let queue = "";
    let shown = "";
    let done = false;
    let started = false;
    let raf = 0;
    let last = 0;
    let credit = 0;
    const openedAt = performance.now();
    let resolveAll;
    const finished = new Promise((r) => { resolveAll = r; });

    function rate() {
      // 目標：把手上的存貨在 600ms 內放完，夾在 min–max 之間
      const pending = queue.length - shown.length;
      const perSecond = (pending / 0.6) || min;
      return Math.max(min, Math.min(max, done ? Math.max(perSecond, 60) : perSecond));
    }

    function tick(now) {
      if (!last) last = now;
      credit += ((now - last) / 1000) * rate();
      last = now;

      if (credit >= 1) {
        const take = Math.floor(credit);
        credit -= take;
        shown = queue.slice(0, shown.length + take);
        onText(shown);
      }

      if (done && shown.length >= queue.length) { resolveAll(); return; }
      raf = requestAnimationFrame(tick);
    }

    function maybeStart() {
      if (started) return;
      const waited = performance.now() - openedAt >= lead;
      if (!waited && !done) return;      // 還在攢存貨
      started = true;
      raf = requestAnimationFrame(tick);
    }

    const timer = setTimeout(maybeStart, lead + 10);

    return {
      push(piece) { queue += piece; maybeStart(); },
      async end() {
        done = true;
        clearTimeout(timer);
        maybeStart();
        if (reduced()) { cancelAnimationFrame(raf); onText(queue); return; }
        await finished;
      },
      cancel() { cancelAnimationFrame(raf); clearTimeout(timer); onText(queue); resolveAll(); },
    };
  }

  return { reduced, wait, countUp, growBar, stagger, enter,
           swapOut, swapIn, leaveMain, enterMain, typer };
})();
