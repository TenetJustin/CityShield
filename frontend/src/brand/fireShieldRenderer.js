// Canvas materials preserve the approved copper/silver preview without a WebGL dependency.
export function createFireShield(button, rotor) {
  const resolution = Math.max(
    120,
    Math.min(
      600,
      Math.ceil(button.clientWidth * Math.min(window.devicePixelRatio || 1, 3)),
    ),
  );
  const shield = new Path2D(
    "M150 16 C117 42 72 59 27 70 L27 171 C27 246 72 301 150 342 C228 301 273 246 273 171 L273 70 C228 59 183 42 150 16 Z",
  );
  const flameLeft = new Path2D(
    "M150 342 C105 320 61 286 62 246 C62 204 98 169 126 132 C151 100 152 81 138 57 C176 87 186 121 180 151 C175 184 152 211 132 236 C108 267 115 310 150 342 Z",
  );
  const flameRight = new Path2D(
    "M150 342 C130 318 121 297 133 269 C146 238 183 224 190 193 C195 177 190 157 186 142 C185 163 204 180 217 200 C238 231 236 265 216 291 C202 309 176 328 150 342 Z",
  );
  const flameMetal = new Path2D();
  flameMetal.addPath(flameLeft);
  flameMetal.addPath(flameRight);
  const settings = { thickness: 11, glint: true };
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const brushedCopper = document.createElement("canvas");
  brushedCopper.width = 600;
  brushedCopper.height = 720;
  const brush = brushedCopper.getContext("2d");
  let grainSeed = 42;
  const grainRandom = () => {
    grainSeed = (grainSeed * 1664525 + 1013904223) >>> 0;
    return grainSeed / 4294967296;
  };
  for (let i = 0; i < 1700; i++) {
    const x = grainRandom() * 600,
      y = grainRandom() * 720,
      length = 18 + grainRandom() * 190;
    brush.strokeStyle =
      i % 2 ? "rgba(255,230,186,.065)" : "rgba(56,24,10,.055)";
    brush.lineWidth = 0.45 + grainRandom() * 0.5;
    brush.beginPath();
    brush.moveTo(x, y);
    brush.lineTo(x + length, y - 0.8);
    brush.stroke();
  }

  function canvasFor(rotor, className, transform) {
    const canvas = document.createElement("canvas");
    canvas.width = resolution;
    canvas.height = Math.round(resolution * 1.2);
    canvas.className = className;
    canvas.style.transform = transform;
    rotor.appendChild(canvas);
    return canvas;
  }
  function paint(canvas, edge, shine = 0.2) {
    const c = canvas.getContext("2d");
    c.setTransform(resolution / 300, 0, 0, resolution / 300, 0, 0);
    c.clearRect(0, 0, 300, 360);
    if (edge !== null) {
      const g = c.createLinearGradient(0, 0, 280, 320);
      g.addColorStop(0, edge % 3 === 0 ? "#ffe1a8" : "#b9834b");
      g.addColorStop(0.32, "#6d361a");
      g.addColorStop(0.53, edge % 3 === 0 ? "#edb773" : "#c7894c");
      g.addColorStop(0.7, "#78401e");
      g.addColorStop(0.86, "#dba56a");
      g.addColorStop(1, "#4d2816");
      c.fillStyle = g;
      c.fill(shield);
      return;
    }
    const border = c.createLinearGradient(40, 10, 260, 340);
    border.addColorStop(0, "#fff0c8");
    border.addColorStop(0.18, "#e9b773");
    border.addColorStop(0.34, "#7a411e");
    border.addColorStop(0.48, "#ffdda0");
    border.addColorStop(0.57, "#b77b42");
    border.addColorStop(0.74, "#f6c88a");
    border.addColorStop(1, "#61351b");
    c.fillStyle = border;
    c.fill(shield);
    c.save();
    c.translate(150, 179);
    c.scale(0.964, 0.977);
    c.translate(-150, -179);
    const shift = (shine - 0.2) * 42;
    const copper = c.createLinearGradient(-25 + shift, 35, 290 + shift, 230);
    copper.addColorStop(0, "#b5753b");
    copper.addColorStop(0.28, "#c88b4c");
    copper.addColorStop(0.5, "#cd9355");
    copper.addColorStop(0.75, "#c28747");
    copper.addColorStop(1, "#b97b3e");
    c.fillStyle = copper;
    c.fill(shield);
    c.save();
    c.clip(shield);
    c.drawImage(brushedCopper, 0, 0, 300, 360);
    const bloom = c.createRadialGradient(
      93 + shift,
      83,
      0,
      93 + shift,
      83,
      205,
    );
    bloom.addColorStop(0, "#fff3c512");
    bloom.addColorStop(0.5, "#fff3c508");
    bloom.addColorStop(1, "#3e190a0a");
    c.fillStyle = bloom;
    c.fillRect(0, 0, 300, 360);
    c.restore();
    if (settings.glint) {
      c.save();
      c.clip(shield);
      const x = -240 + shine * 700;
      const gleam = c.createLinearGradient(x, 0, x + 240, 100);
      gleam.addColorStop(0, "#ffffff00");
      gleam.addColorStop(0.25, "#fff2ce0a");
      gleam.addColorStop(0.5, "#fff5d82b");
      gleam.addColorStop(0.75, "#fff5d80c");
      gleam.addColorStop(1, "#ffffff00");
      c.fillStyle = gleam;
      c.fillRect(0, 0, 300, 360);
      c.restore();
    }
    const ivory = c.createLinearGradient(
      40 + shift * 0.65,
      45,
      245 + shift * 0.65,
      320,
    );
    ivory.addColorStop(0, "#e4e3d8");
    ivory.addColorStop(0.3, "#f3f2e7");
    ivory.addColorStop(0.52, "#f9f8ee");
    ivory.addColorStop(0.76, "#e8e7dc");
    ivory.addColorStop(1, "#ddded4");
    c.save();
    c.clip(shield);
    c.fillStyle = ivory;
    c.shadowColor = "#64310c55";
    c.shadowBlur = 1.5;
    c.shadowOffsetY = 1.2;
    c.fill(flameLeft);
    c.fill(flameRight);
    c.restore();
    c.save();
    c.clip(shield);
    c.clip(flameMetal);
    c.globalAlpha = 0.25;
    c.drawImage(brushedCopper, 0, 0, 300, 360);
    c.globalAlpha = 1;
    const silverEdge = c.createLinearGradient(70, 70, 200, 330);
    silverEdge.addColorStop(0, "#ffffffa0");
    silverEdge.addColorStop(0.5, "#ffffff55");
    silverEdge.addColorStop(1, "#84867e35");
    c.strokeStyle = silverEdge;
    c.lineWidth = 1.2;
    c.stroke(flameMetal);
    if (settings.glint) {
      const silverX = -180 + shine * 550;
      const silverLight = c.createLinearGradient(silverX, 0, silverX + 220, 95);
      silverLight.addColorStop(0, "#ffffff00");
      silverLight.addColorStop(0.25, "#ffffff0a");
      silverLight.addColorStop(0.5, "#ffffff48");
      silverLight.addColorStop(0.75, "#ffffff10");
      silverLight.addColorStop(1, "#ffffff00");
      c.fillStyle = silverLight;
      c.fillRect(0, 0, 300, 360);
    }
    c.restore();
    c.restore();
  }

  let frame = 0;
  let disposed = false;
  let busy = false;
  try {
    const depth = (settings.thickness * button.clientWidth) / 224;
    for (let i = 0; i < 25; i++) {
      const edge = canvasFor(
        rotor,
        "fireShieldMark__edge",
        `translateZ(${-depth / 2 + (i * depth) / 24}px)`,
      );
      paint(edge, i);
    }
    const back = canvasFor(
      rotor,
      "",
      `rotateY(180deg) translateZ(${depth / 2 + 0.15}px)`,
    );
    const front = canvasFor(rotor, "", `translateZ(${depth / 2 + 0.15}px)`);
    const reset = () => {
      cancelAnimationFrame(frame);
      busy = false;
      button.dataset.animating = "false";
      rotor.style.transform = "rotateY(0deg)";
      paint(front, null, 0.2);
      paint(back, null, 0.2);
    };
    reset();
    button.dataset.ready = "true";

    const play = () => {
      if (disposed || busy || reduce.matches || document.hidden) return;
      busy = true;
      button.dataset.animating = "true";
      const start = performance.now();
      // Approved timing: 750 ms winding, 150 ms hold, then a gently damped return.
      const duration = 750,
        holdDuration = 150,
        returnDuration = 2465;
      const damping = 0.68,
        frequency = 7.4;
      const dampedFrequency = frequency * Math.sqrt(1 - damping * damping);
      const total = duration + holdDuration + returnDuration;
      const tick = (now) => {
        if (disposed) return;
        const elapsed = Math.max(0, now - start);
        if (elapsed >= total) {
          reset();
          return;
        }
        let rotation, tilt, compression;
        if (elapsed < duration) {
          const winding = Math.sin(((elapsed / duration) * Math.PI) / 2);
          rotation = 360 * winding;
          tilt = -4 * winding;
          compression = 1 - 0.018 * winding;
        } else if (elapsed < duration + holdDuration) {
          rotation = 360;
          tilt = -4;
          compression = 0.982;
        } else {
          const seconds = (elapsed - duration - holdDuration) / 1000;
          const decay = Math.exp(-damping * frequency * seconds);
          const spring =
            decay *
            (Math.cos(dampedFrequency * seconds) +
              ((damping * frequency) / dampedFrequency) *
                Math.sin(dampedFrequency * seconds));
          rotation = 360 * spring;
          tilt = -4 * spring;
          compression = 1 - 0.018 * spring;
        }
        rotor.style.transform = `rotateX(${tilt}deg) rotateY(${rotation}deg) scale(${compression})`;
        const reflection =
          0.2 + 0.65 * Math.abs(Math.sin((rotation * Math.PI) / 180));
        paint(front, null, reflection);
        paint(back, null, reflection);
        frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };
    const stopIfReduced = () => {
      if (reduce.matches) reset();
    };
    const stopIfHidden = () => {
      if (document.hidden) reset();
    };
    reduce.addEventListener("change", stopIfReduced);
    document.addEventListener("visibilitychange", stopIfHidden);
    return {
      play,
      dispose() {
        disposed = true;
        cancelAnimationFrame(frame);
        reduce.removeEventListener("change", stopIfReduced);
        document.removeEventListener("visibilitychange", stopIfHidden);
        rotor.replaceChildren();
        rotor.style.transform = "";
        delete button.dataset.ready;
        delete button.dataset.animating;
      },
    };
  } catch (error) {
    rotor.replaceChildren();
    delete button.dataset.ready;
    throw error;
  }
}
