/* 液態玻璃球。

   著色器是 web/orb.wgsl，原封不動，一行未改。
   uniformSeed 也照搬，只換掉顏色槽位，讓球落進專案的暖紙加森林綠色系。
   其餘每一個參數（style、glass、warp、ridge、metal、palette……）都保持原值。

   球只用在一個地方：等模型回應時的思考膠囊。不當 logo，不當裝飾。
   WebGPU 不可用時靜默退到 CSS 畫的靜態球，裝飾件絕不拖垮頁面。 */

const Orb = (() => {

  /* ── uniformSeed 的欄位位置 ──────────────────────────────────────────
     scalar 區佔 index 0–31，之後每個顏色是一個 vec4（4 個 float）。
     colorA 從 32 起算，依序每 4 個一組。 */
  const SLOT = {
    colorA: 32, colorB: 36, colorC: 40, colorD: 44,
    highlight: 48, shellInner: 52, shellMid: 56, shellEdge: 60,
    sheen: 64, spec: 68, canvas: 72, glow: 76,
  };

  /* 專案色板 */
  const RGB = {
    moss:  [0.290, 0.404, 0.255],
    kombu: [0.176, 0.306, 0.188],
    arti:  [0.494, 0.584, 0.439],
    lime:  [0.714, 0.784, 0.286],
    teal:  [0.227, 0.416, 0.400],
    cream: [0.976, 0.965, 0.937],
    paper: [0.918, 0.910, 0.878],
    white: [1.000, 1.000, 1.000],
  };

  const SEED = [1,1,0,0.8199999928474426,0.7200000286102295,0.36000001430511475,3.200000047683716,0.5,2.200000047683716,0.11999999731779099,0.2800000011920929,0.23999999463558197,0.18000000715255737,0.18000000715255737,2,9,0.004999999888241291,0,0,1,0.4399999976158142,0,2,0.41999998688697815,0.7699999809265137,0.23000000417232513,65,0,0,1,0.2199999988079071,0.25,1,0.8470588326454163,0.41960784792900085,1,0.5098039507865906,0.95686274766922,1,1,1,0.48235294222831726,0.8352941274642944,1,0.5568627715110779,0.42352941632270813,1,1,1,1,1,1,1,1,1,1,0.6078431606292725,0.95686274766922,1,1,0.772549033164978,0.6627451181411743,1,1,0.9176470637321472,0.95686274766922,1,1,0.8627451062202454,0.9176470637321472,1,1,0.0117647061124444,0.01568627543747425,0.03529411926865578,1,0.5843137502670288,0.42352941632270813,1,1,0.9686274528503418,0.9843137264251709,1,1,0.9372549057006836,0.9647058844566345,0.9921568632125854,1,0.8784313797950745,0.9333333373069763,0.9764705896377563,1,0.8313725590705872,0.9019607901573181,0.9686274528503418,1,0.7333333492279053,0.8352941274642944,0.9529411792755127,1,0.6509804129600525,0.7803921699523926,0.9411764740943909,1,0.529411792755127,0.6901960968971252,0.9215686321258545,1,0.43529412150382996,0.6196078658103943,0.9098039269447327,1,0.43529412150382996,0.6196078658103943,0.9098039269447327,1,0.43529412150382996,0.6196078658103943,0.9098039269447327,1,0.43529412150382996,0.6196078658103943,0.9098039269447327,1,0.43529412150382996,0.6196078658103943,0.9098039269447327,1];

  /* 場景適配：uniform 換值，著色器檔案一行不動。

     原版是 style 9（Siri）。它的暗底是寫死在自己的 atmosphere 項裡的，
     換 canvasColor 沒有用——我渲了六組底色比對，六顆一樣黑。

     改用 style 19（聲音薄膜）。同樣是一道橫貫球體的波浪，動態一致，
     但它的底色由 colorA 與 colorD 決定（mix(colorA*0.7, colorD*0.34)），
     所以停位給亮就是一顆淺色玻璃球，波浪照舊在裡面流動。 */
  const SLOT_STYLE = 15, SLOT_SHADE = 9, SLOT_EXPOSURE = 14;

  function tint(seed) {
    const v = Float32Array.from(seed);
    const put = (slot, rgb) => { v[slot] = rgb[0]; v[slot + 1] = rgb[1]; v[slot + 2] = rgb[2]; };

    v[SLOT_STYLE] = 19;        // 聲音薄膜：一道橫貫球體的波
    v[SLOT_SHADE] = 0.08;      // 球面明暗收一點，小尺寸下不糊
    v[SLOT_EXPOSURE] = 1.7;    // 原值 2 是為暗底準備的

    put(SLOT.colorA, [1.000, 1.000, 1.000]);   // 球體上半的底
    put(SLOT.colorB, [0.702, 0.839, 0.341]);   // 波峰上緣，萊姆
    put(SLOT.colorC, [0.459, 0.678, 0.459]);   // 波峰下緣，苔綠
    put(SLOT.colorD, [1.000, 1.000, 0.973]);   // 球體下半的底
    put(SLOT.highlight, [1.0, 1.0, 1.0]);
    put(SLOT.glow, [0.702, 0.839, 0.341]);
    return v;
  }

  let shaderPromise = null;
  let devicePromise = null;

  const loadShader = () => (shaderPromise ||= fetch("/orb.wgsl").then((r) => r.text()));

  function getDevice() {
    if (!navigator.gpu) return Promise.reject(new Error("no webgpu"));
    return (devicePromise ||= navigator.gpu.requestAdapter().then((adapter) => {
      if (!adapter) throw new Error("no adapter");
      return adapter.requestDevice();
    }));
  }

  async function mount(wrap) {
    // 先掛上 CSS 回退球，立刻就有東西可看。
    // GPU 裝置與著色器就緒之後才換成 canvas，換不成就一直是回退。
    // 之前的寫法是等 GPU 好了才畫，第一次開啟時裝置初始化比膠囊活得久，
    // 於是那一次完全看不到球，第二次才有——就是你看到的「只有一個人的會顯示」。
    wrap.classList.add("fallback");

    const canvas = document.createElement("canvas");
    wrap.appendChild(canvas);

    let device, code;
    try {
      [device, code] = await Promise.all([getDevice(), loadShader()]);
    } catch (_) {
      return;
    }
    if (!wrap.isConnected) return;

    const context = canvas.getContext("webgpu");
    if (!context) return;

    try {
      const format = navigator.gpu.getPreferredCanvasFormat();
      context.configure({ device, format, alphaMode: "premultiplied" });

      const module = device.createShaderModule({ code });
      const info = await module.getCompilationInfo();
      if (info.messages.some((m) => m.type === "error")) throw new Error("shader");

      const pipeline = device.createRenderPipeline({
        layout: "auto",
        vertex: { module, entryPoint: "vs_main" },
        fragment: {
          module, entryPoint: "fs_main",
          targets: [{
            format,
            blend: {
              color: { srcFactor: "one", dstFactor: "one-minus-src-alpha" },
              alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha" },
            },
          }],
        },
        primitive: { topology: "triangle-list" },
      });

      const values = tint(SEED);
      const buffer = device.createBuffer({
        size: values.byteLength,
        usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
      });
      const bindGroup = device.createBindGroup({
        layout: pipeline.getBindGroupLayout(0),
        entries: [{ binding: 0, resource: { buffer } }],
      });

      const startedAt = performance.now();
      let stopped = false;
      let live = false;
      device.lost.then(() => { stopped = true; wrap.classList.add("fallback"); });

      function frame(now) {
        if (stopped || !wrap.isConnected) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = Math.max(1, Math.round(wrap.clientWidth * dpr));
        const h = Math.max(1, Math.round(wrap.clientHeight * dpr));
        if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
        values[0] = w;
        values[1] = h;
        values[2] = (now - startedAt) / 1000;
        device.queue.writeBuffer(buffer, 0, values);

        const encoder = device.createCommandEncoder();
        const pass = encoder.beginRenderPass({
          colorAttachments: [{
            view: context.getCurrentTexture().createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 0 },
            loadOp: "clear", storeOp: "store",
          }],
        });
        pass.setPipeline(pipeline);
        pass.setBindGroup(0, bindGroup);
        pass.draw(3);
        pass.end();
        device.queue.submit([encoder.finish()]);
        if (!live) { live = true; wrap.classList.remove("fallback"); }
        requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    } catch (_) {
      /* 保持回退，不做事 */
    }
  }

  /* 生成一個球的容器節點，呼叫方決定尺寸類。 */
  function node(sizeClass) {
    const wrap = document.createElement("div");
    wrap.className = "orb-wrap " + sizeClass;
    requestAnimationFrame(() => mount(wrap));   // 先掛 DOM，拿得到真實尺寸
    return wrap;
  }

  /* 預熱：登入頁就把裝置與著色器準備好，思考膠囊出現時不再等。 */
  function warm() {
    Promise.all([getDevice(), loadShader()]).catch(() => {});
  }

  return { node, warm };
})();
