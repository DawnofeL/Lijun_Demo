/* 前端唯一的请求出口。所有视图都不直接调 fetch，只调这里。
   统一附加 token、统一解析、统一处理 401 与错误提示。 */

const Api = (() => {
  /* token 只存在记忆体，不落 localStorage。
     重整页面即失效，每次开启都必须重新登入。
     这既是鑑权演示的重点，也避免 token 留在浏览器里。 */
  let current = null;

  const token = {
    get: () => current,
    set: (value) => { current = value; },
    clear: () => { current = null; },
  };

  let onUnauthorized = () => {};

  async function request(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    const active = token.get();
    if (active) headers.Authorization = "Bearer " + active;
    if (options.json !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.json);
      options.method = options.method || "POST";
    }

    let response;
    try {
      response = await fetch("/api" + path, Object.assign({}, options, { headers }));
    } catch (error) {
      throw new Error("無法連線到服務，請確認服務仍在執行");
    }

    if (response.status === 401) {
      token.clear();
      onUnauthorized();
      throw new Error("登入已失效，請重新登入");
    }

    if (!response.ok) {
      let message = "請求失敗（" + response.status + "）";
      try {
        const body = await response.json();
        if (body && body.detail) message = body.detail;
      } catch (_) { /* 回应不是 JSON，沿用预设讯息 */ }
      throw new Error(message);
    }

    if (response.headers.get("content-type")?.includes("application/json")) {
      return response.json();
    }
    return response;
  }

  /* 探针：给「權限自檢」用。

     和 request() 的差别只有一个，但很关键：request() 遇到非 2xx 会 throw，
     而且把状态码揉进了字串（「請求失敗（403）」），拿不到结构化的 status。
     自检页要把 403 当「资料」而不是「错误」——那正是它要展示的东西。

     它也刻意不触发全域的 401 跳转：自检页本来就在打会被拒的介面，
     一旦顺手把人踢回登入页，整页就白跑了。真的 401（token 过期）
     会照实回传，由呼叫端自己决定怎么办。

     回传 { ok, status, detail, count, ms }，永远不抛错（连线失败回 status 0）。 */
  async function probe(method, path, options = {}) {
    const headers = {};
    const active = token.get();
    if (active) headers.Authorization = "Bearer " + active;
    if (options.json !== undefined) headers["Content-Type"] = "application/json";

    const started = performance.now();
    let response;
    try {
      response = await fetch("/api" + path, {
        method,
        headers,
        body: options.json !== undefined ? JSON.stringify(options.json)
            : options.body !== undefined ? options.body : undefined,
      });
    } catch (_) {
      return { ok: false, status: 0, detail: "無法連線到服務", count: null,
               ms: Math.round(performance.now() - started) };
    }
    const ms = Math.round(performance.now() - started);

    let body = null;
    try { body = await response.json(); } catch (_) { /* 不是 JSON，当没有 */ }

    // 计数从回传体里挖：多数介面是 { items: [...] }，少数直接给 total
    let count = null;
    if (body && typeof body === "object") {
      if (Array.isArray(body)) count = body.length;
      else if (Array.isArray(body.items)) count = body.items.length;
      else if (typeof body.total === "number") count = body.total;
    }

    return {
      ok: response.ok,
      status: response.status,
      detail: (body && body.detail) || null,
      body,
      count,
      ms,
    };
  }

  return {
    token,
    probe,
    setUnauthorizedHandler: (fn) => { onUnauthorized = fn; },
    get: (path) => request(path),
    post: (path, json) => request(path, { json }),
    del: (path) => request(path, { method: "DELETE" }),
    /* SSE：逐段回呼，用於助理的串流回覆 */
    stream: async (path, json, onPiece) => {
      const headers = { "Content-Type": "application/json" };
      const active = token.get();
      if (active) headers.Authorization = "Bearer " + active;
      const response = await fetch("/api" + path, {
        method: "POST", headers, body: JSON.stringify(json),
      });
      if (response.status === 401) { token.clear(); onUnauthorized(); throw new Error("登入已失效"); }
      if (!response.ok) throw new Error("請求失敗（" + response.status + "）");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (data === "[DONE]") return;
          try { onPiece(JSON.parse(data).t); } catch (_) { /* 半截的 JSON，等下一輪 */ }
        }
      }
    },
    upload: (path, file) => {
      const form = new FormData();
      form.append("file", file);
      return request(path, { method: "POST", body: form });
    },
    download: async (path, filename) => {
      const response = await request(path);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    },
  };
})();
