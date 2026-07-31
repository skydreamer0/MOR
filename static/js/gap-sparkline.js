/**
 * gap-sparkline.js — 進貨間隔迷你長條圖（Product Monitor 展開列）
 *
 * 配色來自 mor.css 的 :root design token，於載入時一次性讀出並快取，
 * 之後每次 canvas 繪製都只是純物件取值，沒有 CSS 變數查詢成本
 * （與 analytics-renderer.js:11-15 相同的考量，但這裡改為真的讀 token）。
 *
 * Token 對應（fallback 即現行硬編色，token 缺席時外觀完全不變）：
 *   near / avgLine / label  --muted-light         #94a3b8  ← mor.css:12 完全相符
 *   below                   --chart-gap-below     #22c55e  ← 尚無此 token，暫用 fallback
 *   above                   --chart-gap-above     #ef4444  ← 尚無此 token，暫用 fallback
 *   current                 --chart-gap-current   #f97316  ← 尚無此 token，暫用 fallback
 *
 * 三個 --chart-gap-* 目前在 mor.css 中不存在，因此讀取結果為空字串、
 * 一律落到 fallback。最接近的既有 token 值都與現行色不同
 * （--success-text #047857 / --danger #dc2626 / --accent-2 #d97706），
 * 直接套用會改變畫面，故不採用；待 mor.css 補上對應 token 後即自動生效。
 */
(function () {
  const BAR_RADIUS = 2;

  // 一次性解析（script 掛在 </body> 前，樣式表已套用）
  const rootStyle =
    typeof getComputedStyle === "function" && document.documentElement
      ? getComputedStyle(document.documentElement)
      : null;

  function token(name, fallback) {
    const value = rootStyle ? (rootStyle.getPropertyValue(name) || "").trim() : "";
    return value || fallback;
  }

  const SLATE = token("--muted-light", "#94a3b8");
  const C = {
    below:   token("--chart-gap-below",   "#22c55e"),  // shorter than avg → green (healthy)
    above:   token("--chart-gap-above",   "#ef4444"),  // longer than avg  → red (warning)
    near:    SLATE,                                    // within ±10%      → slate
    current: token("--chart-gap-current", "#f97316"),  // current elapsed  → orange (in-progress)
    avgLine: SLATE,
    label:   SLATE,
  };

  function draw(canvas) {
    const gaps    = JSON.parse(canvas.dataset.gaps    || "[]");
    const avg     = parseInt(canvas.dataset.avg,     10) || 0;
    const current = parseInt(canvas.dataset.current, 10) || 0;
    if (gaps.length === 0) return;

    const dpr  = window.devicePixelRatio || 1;
    const W    = canvas.offsetWidth  || 260;
    const H    = canvas.offsetHeight || 72;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    const PL = 26, PR = 6, PT = 8, PB = 16;
    const chartW = W - PL - PR;
    const chartH = H - PT - PB;

    const showCurrent = current > 0;
    const totalBars   = gaps.length + (showCurrent ? 1 : 0);
    const GAP         = 3;
    const barW        = Math.max(7, (chartW - GAP * (totalBars - 1)) / totalBars);
    // Y 軸以歷史間隔為基準，最多放大到 avg*2.5，
    // 「今」超出的部分蓋頂顯示（避免被拉高後歷史柱縮到底部）
    const histMax  = Math.max(...gaps, avg > 0 ? avg : 1);
    const maxVal   = Math.max(histMax, avg > 0 ? avg * 1.2 : 1) * 1.15;
    const currentCapped = showCurrent && current > maxVal; // 超出上限時蓋頂

    function fy(v) { return PT + chartH - (v / maxVal) * chartH; }

    function barColor(g) {
      if (avg <= 0) return C.near;
      const r = g / avg;
      if (r > 1.10) return C.above;
      if (r < 0.90) return C.below;
      return C.near;
    }

    ctx.clearRect(0, 0, W, H);

    // Average reference line
    if (avg > 0) {
      const ay = fy(avg);
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = C.avgLine;
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.moveTo(PL, ay);
      ctx.lineTo(W - PR, ay);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle  = C.label;
      ctx.font       = "9px system-ui,sans-serif";
      ctx.textAlign  = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(avg, PL - 3, ay);
    }

    // Historical gap bars
    gaps.forEach((g, i) => {
      const x  = PL + i * (barW + GAP);
      const bh = (g / maxVal) * chartH;
      const y  = PT + chartH - bh;

      ctx.fillStyle = barColor(g);
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, barW, bh, BAR_RADIUS);
      else ctx.rect(x, y, barW, bh);
      ctx.fill();

      ctx.fillStyle    = C.label;
      ctx.font         = "9px system-ui,sans-serif";
      ctx.textAlign    = "center";
      ctx.textBaseline = "top";
      ctx.fillText(g, x + barW / 2, H - PB + 2);
    });

    // Current elapsed bar (dashed top, semi-transparent)
    if (showCurrent) {
      const i  = gaps.length;
      const x  = PL + i * (barW + GAP);
      const bh = Math.min((current / maxVal) * chartH, chartH);
      const y  = PT + chartH - bh;

      ctx.save();
      ctx.globalAlpha = 0.45;
      ctx.fillStyle   = C.current;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, barW, bh, BAR_RADIUS);
      else ctx.rect(x, y, barW, bh);
      ctx.fill();
      ctx.restore();

      ctx.save();
      ctx.setLineDash([2, 2]);
      ctx.strokeStyle = C.current;
      ctx.lineWidth   = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + barW, y);
      ctx.stroke();
      ctx.restore();

      // 蓋頂時在柱子頂端顯示「▲ 101」提示實際數值
      ctx.fillStyle    = C.label;
      ctx.font         = "9px system-ui,sans-serif";
      ctx.textAlign    = "center";
      ctx.textBaseline = "top";
      if (currentCapped) {
        ctx.fillStyle = C.current;
        ctx.font      = "bold 9px system-ui,sans-serif";
        ctx.fillText("▲" + current, x + barW / 2, PT - 1);
        ctx.fillStyle = C.label;
        ctx.font      = "9px system-ui,sans-serif";
      }
      ctx.fillText("今", x + barW / 2, H - PB + 2);
    }
  }

  function drawAll() {
    document.querySelectorAll(".gap-sparkline").forEach(draw);
  }

  drawAll();

  // Redraw when detail row is expanded (canvas was hidden, offsetWidth was 0)
  document.addEventListener("click", (e) => {
    const row = e.target.closest("[data-monitor-row]");
    if (!row) return;
    setTimeout(() => {
      const detail = row.nextElementSibling;
      if (detail?.hasAttribute("data-monitor-detail")) {
        detail.querySelectorAll(".gap-sparkline").forEach(draw);
      }
    }, 16);
  });
})();
