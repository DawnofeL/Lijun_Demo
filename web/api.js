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

  return {
    token,
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
