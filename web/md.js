/* 極簡 Markdown 渲染。

   只處理模型實際會吐的那幾種：標題、粗體、斜體、行內程式碼、程式碼區塊、
   無序與有序清單、引用、分隔線、連結。不引外部套件，一個檔案兩百行。

   安全前提：先把整段文字做 HTML 轉義，之後才套用格式。
   模型輸出是不可信來源，先轉義再加標籤，任何 <script> 都只會變成字面文字。
   連結只放行 http(s)，其餘一律當純文字。

   串流時會被反覆呼叫（每次拿到的是目前為止的全文），所以必須夠快，
   而且要能容忍未閉合的語法——最後一行常常是半截的 **粗體。 */

const MD = (() => {

  const escapeHtml = (text) => text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  /* 行內語法。輸入已經轉義過，所以這裡只認轉義後的字元。 */
  function inline(text) {
    return text
      // 行內程式碼優先，裡面的其他符號不再解讀
      .replace(/`([^`\n]+)`/g, (_, code) => `<code>${code}</code>`)
      // 粗體、斜體。粗體先於斜體，否則 ** 會被拆成兩個 *
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      // 連結：只放行 http(s)，其餘保持原樣當純文字
      .replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,
               '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }

  function render(source) {
    const lines = String(source || "").split("\n");
    const out = [];
    let inCode = false;
    let codeBuffer = [];
    let listType = null;      // "ul" | "ol" | null
    let paragraph = [];

    const flushParagraph = () => {
      if (!paragraph.length) return;
      out.push("<p>" + inline(paragraph.join("<br>")) + "</p>");
      paragraph = [];
    };
    const closeList = () => {
      if (listType) { out.push(`</${listType}>`); listType = null; }
    };
    const openList = (type) => {
      if (listType === type) return;
      closeList();
      out.push(`<${type}>`);
      listType = type;
    };

    for (const raw of lines) {
      const line = raw.replace(/\s+$/, "");

      // 程式碼區塊：內容原樣保留，不套任何行內語法
      const fence = line.match(/^\s*```(\w*)\s*$/);
      if (fence) {
        if (inCode) {
          out.push(`<pre><code>${escapeHtml(codeBuffer.join("\n"))}</code></pre>`);
          codeBuffer = []; inCode = false;
        } else {
          flushParagraph(); closeList(); inCode = true;
        }
        continue;
      }
      if (inCode) { codeBuffer.push(raw); continue; }

      if (!line.trim()) { flushParagraph(); closeList(); continue; }

      const heading = line.match(/^(#{1,4})\s+(.*)$/);
      if (heading) {
        flushParagraph(); closeList();
        const level = Math.min(heading[1].length + 2, 6);   // # → h3，不搶頁面標題
        out.push(`<h${level}>${inline(escapeHtml(heading[2]))}</h${level}>`);
        continue;
      }

      if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(line)) {
        flushParagraph(); closeList(); out.push("<hr>"); continue;
      }

      const quote = line.match(/^>\s?(.*)$/);
      if (quote) {
        flushParagraph(); closeList();
        out.push(`<blockquote>${inline(escapeHtml(quote[1]))}</blockquote>`);
        continue;
      }

      const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
      if (bullet) {
        flushParagraph(); openList("ul");
        out.push(`<li>${inline(escapeHtml(bullet[1]))}</li>`);
        continue;
      }

      const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (numbered) {
        flushParagraph(); openList("ol");
        out.push(`<li>${inline(escapeHtml(numbered[1]))}</li>`);
        continue;
      }

      closeList();
      paragraph.push(escapeHtml(line));
    }

    // 串流時最後一段常常還沒收尾，這裡一律補齊，畫面才不會缺一塊
    if (inCode && codeBuffer.length) {
      out.push(`<pre><code>${escapeHtml(codeBuffer.join("\n"))}</code></pre>`);
    }
    flushParagraph();
    closeList();
    return out.join("");
  }

  /* 把渲染結果寫進節點。串流時每次都重寫，量小不必做 diff。 */
  function into(node, source) {
    node.innerHTML = render(source);
  }

  return { render, into, escapeHtml };
})();
