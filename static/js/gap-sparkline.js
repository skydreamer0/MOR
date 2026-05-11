(function () {
  const BAR_RADIUS = 2;
  const C = {
    below:   "#22c55e",  // shorter than avg → green (healthy)
    above:   "#ef4444",  // longer than avg  → red (warning)
    near:    "#94a3b8",  // within ±10%      → slate
    current: "#f97316",  // current elapsed  → orange (in-progress)
    avgLine: "#94a3b8",
    label:   "#94a3b8",
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
    const maxVal      = Math.max(...gaps, showCurrent ? current : 0, avg > 0 ? avg * 1.1 : 1) * 1.1;

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

      ctx.fillStyle    = C.label;
      ctx.font         = "9px system-ui,sans-serif";
      ctx.textAlign    = "center";
      ctx.textBaseline = "top";
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
