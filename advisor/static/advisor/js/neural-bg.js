(function () {
  const canvas = document.getElementById("neural-bg");
  if (!canvas) return;

  const ctx = canvas.getContext("2d", { alpha: true });
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pointer = { x: -9999, y: -9999, active: false };
  let width = 0;
  let height = 0;
  let dpr = 1;
  let nodes = [];
  let time = 0;
  let rafId = 0;

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const count = Math.min(38, Math.max(20, Math.floor(width / 55)));
    nodes = Array.from({ length: count }, (_, index) => ({
      x: rand(width * 0.12, width * 0.88),
      y: rand(height * 0.12, height * 0.84),
      phase: rand(0, Math.PI * 2),
      speed: rand(0.002, 0.004),
      r: index % 5 === 0 ? rand(7, 12) : rand(3, 7)
    }));
  }

  function drawServerRack(x, flip) {
    const rackWidth = Math.max(90, width * 0.11);
    const grd = ctx.createLinearGradient(x, 0, x + (flip ? -rackWidth : rackWidth), 0);
    grd.addColorStop(0, "rgba(31, 195, 219, 0.16)");
    grd.addColorStop(1, "rgba(15, 23, 42, 0)");

    ctx.fillStyle = grd;
    ctx.fillRect(flip ? x - rackWidth : x, 0, rackWidth, height);

    ctx.strokeStyle = "rgba(148, 163, 184, 0.08)";
    ctx.lineWidth = 1;
    for (let y = 28; y < height; y += 18) {
      ctx.beginPath();
      ctx.moveTo(flip ? x - rackWidth + 18 : x + 18, y);
      ctx.lineTo(flip ? x - 14 : x + rackWidth - 14, y);
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(31, 195, 219, 0.22)";
    for (let y = 40; y < height; y += 36) {
      for (let i = 0; i < 7; i += 1) {
        const px = flip ? x - 24 - i * 10 : x + 24 + i * 10;
        ctx.fillRect(px, y, 3, 3);
      }
    }
  }

  function drawCloud(cx, cy, scale) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(scale, scale);

    const cloudFill = ctx.createLinearGradient(0, -95, 0, 90);
    cloudFill.addColorStop(0, "rgba(186, 240, 255, 0.18)");
    cloudFill.addColorStop(0.5, "rgba(89, 203, 224, 0.12)");
    cloudFill.addColorStop(1, "rgba(15, 23, 42, 0.04)");

    ctx.fillStyle = cloudFill;
    ctx.strokeStyle = "rgba(186, 240, 255, 0.36)";
    ctx.lineWidth = 2;
    ctx.shadowColor = "rgba(31, 195, 219, 0.26)";
    ctx.shadowBlur = 24;

    ctx.beginPath();
    ctx.moveTo(-150, 45);
    ctx.bezierCurveTo(-190, 42, -205, 8, -170, -12);
    ctx.bezierCurveTo(-154, -58, -102, -75, -62, -49);
    ctx.bezierCurveTo(-38, -103, 44, -105, 73, -48);
    ctx.bezierCurveTo(123, -60, 166, -26, 169, 23);
    ctx.bezierCurveTo(195, 30, 184, 62, 145, 64);
    ctx.lineTo(-146, 64);
    ctx.bezierCurveTo(-168, 64, -174, 50, -150, 45);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.shadowBlur = 0;
    ctx.strokeStyle = "rgba(226, 246, 255, 0.18)";
    ctx.lineWidth = 1;
    for (let i = -120; i <= 120; i += 40) {
      ctx.beginPath();
      ctx.moveTo(i, -20 + Math.sin(i) * 4);
      ctx.lineTo(i * 0.45, 52);
      ctx.stroke();
    }

    ctx.restore();
  }

  function nodePosition(node) {
    const drift = reduceMotion ? 0 : Math.sin(time * node.speed + node.phase) * 14;
    let x = node.x + drift;
    let y = node.y + Math.cos(time * node.speed + node.phase) * 10;

    if (pointer.active) {
      const dx = pointer.x - x;
      const dy = pointer.y - y;
      const distance = Math.hypot(dx, dy);
      if (distance < 220 && distance > 0.01) {
        x += (dx / distance) * (1 - distance / 220) * 18;
        y += (dy / distance) * (1 - distance / 220) * 18;
      }
    }

    return { x, y };
  }

  function drawNode(point, radius, active) {
    const ring = active ? radius + 18 : radius + 10;
    ctx.strokeStyle = active ? "rgba(34, 197, 94, 0.34)" : "rgba(186, 240, 255, 0.18)";
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(point.x, point.y, ring, 0, Math.PI * 2);
    ctx.stroke();

    ctx.strokeStyle = active ? "rgba(34, 197, 94, 0.45)" : "rgba(31, 195, 219, 0.22)";
    ctx.beginPath();
    ctx.arc(point.x, point.y, ring + 5, 0.2 + time * 0.01, Math.PI * 1.4 + time * 0.01);
    ctx.stroke();

    const glow = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, ring + 14);
    glow.addColorStop(0, active ? "rgba(34, 197, 94, 0.42)" : "rgba(125, 226, 245, 0.34)");
    glow.addColorStop(1, "rgba(31, 195, 219, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(point.x, point.y, ring + 14, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = active ? "rgba(187, 247, 208, 0.78)" : "rgba(186, 240, 255, 0.72)";
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  function draw() {
    time += 1;
    ctx.clearRect(0, 0, width, height);

    drawServerRack(0, false);
    drawServerRack(width, true);

    const cx = width * 0.52;
    const cy = height * 0.43;
    const scale = Math.min(width / 1300, 1) * 0.9 + 0.28;
    const points = nodes.map(nodePosition);

    ctx.lineWidth = 1;
    points.forEach((a, i) => {
      for (let j = i + 1; j < points.length; j += 1) {
        const b = points[j];
        const distance = Math.hypot(a.x - b.x, a.y - b.y);
        if (distance < 230) {
          ctx.strokeStyle = `rgba(186, 240, 255, ${(1 - distance / 230) * 0.12})`;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      const toCloud = Math.hypot(a.x - cx, a.y - cy);
      if (toCloud < 420) {
        ctx.strokeStyle = `rgba(31, 195, 219, ${(1 - toCloud / 420) * 0.11})`;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(cx + Math.sin(i) * 120 * scale, cy + Math.cos(i) * 44 * scale);
        ctx.stroke();
      }
    });

    drawCloud(cx, cy, scale);

    points.forEach((point, i) => {
      const active = pointer.active && Math.hypot(point.x - pointer.x, point.y - pointer.y) < 180;
      drawNode(point, nodes[i].r, active);
    });

    rafId = window.requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize, { passive: true });
  window.addEventListener("mousemove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.active = true;
  }, { passive: true });
  window.addEventListener("mouseleave", () => {
    pointer.active = false;
  }, { passive: true });

  resize();
  draw();

  window.addEventListener("pagehide", () => {
    if (rafId) window.cancelAnimationFrame(rafId);
  });
})();
