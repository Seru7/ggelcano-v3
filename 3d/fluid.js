/* Estela de agua del cursor — simulación de fluidos estable en GPU.
   Reconstruida desde el linaje libre (Pavel Dobryakov, WebGL-Fluid-Simulation,
   MIT) sobre Three.js con double-FBO ping-pong, afinada con las constantes que
   documenta nuestra investigación (informes 05 y 08 de webs-premium):
   - splat de SEGMENTO (cápsula entre posición anterior y actual): estela
     continua aunque cruces la pantalla de un latigazo
   - el gesto inyecta su VELOCIDAD en el campo (más rápido = más energía)
   - solo 2 iteraciones de presión + vorticity confinement (curl 10)
   - disipaciones 0.97 (tinta) / 0.99 (velocidad): el agua sigue viva al soltar
   - resolución por presupuesto de píxeles (2^18 ≈ 590×444 en 16:9)
   - del campo de tinta se derivan NORMALES (relieve líquido) y su delta
     (filo brillante): la estela se ilumina como agua, no como pintura
   Reemplaza a la estela 2D de burbujas (#waterC); si este módulo no puede
   correr (sin WebGL2, móvil, reduced-motion) la antigua sigue de fallback. */
import * as THREE from 'three';

const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const fino = matchMedia('(pointer: fine)').matches;
const ancho = innerWidth > 880;
const gl2 = (() => { try { return !!document.createElement('canvas').getContext('webgl2'); } catch { return false; } })();

if (!window.GG_FLUID || reduce || !fino || !ancho || !gl2) {
  window.__fluidOn = false;
} else {
  try { init(); window.__fluidOn = true; }
  catch (e) { console.error('GG fluido:', e); window.__fluidOn = false; }
}

function init() {
  /* ---------- constantes de la simulación ---------- */
  const PIXELES_SIM = 1 << 18;     // presupuesto desktop (la referencia usa 2^18)
  const DISIPA_TINTA = 0.97;
  const DISIPA_VEL = 0.99;
  const DECAE_PRESION = 0.99;
  const CURL = 10;
  const ITER_PRESION = 2;
  const RADIO_SPLAT = 0.0016;      // estela ancha como la referencia (~200px)
  const EPS_NORMAL = 0.005;
  const FUERZA_GESTO = 6000;       // la velocidad del gesto (uv/frame) → campo
  const IDLE_MS = 8000;            // sin ratón: la sim se duerme y libera CPU

  /* ---------- lienzo y renderer ---------- */
  const cv = document.createElement('canvas');
  cv.id = 'waterC';                // reutiliza el CSS del efecto antiguo
  cv.setAttribute('aria-hidden', 'true');
  /* la espuma se funde en aditivo con la página (negro = invisible),
     como la capa de agua de la referencia */
  cv.style.mixBlendMode = 'screen';
  document.body.appendChild(cv);
  const renderer = new THREE.WebGLRenderer({
    canvas: cv, alpha: true, antialias: false, depth: false, stencil: false,
    premultipliedAlpha: false, powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(1);       // la sim es de baja resolución: ampliar suaviza
  renderer.autoClear = false;

  const escena = new THREE.Scene();
  const camara = new THREE.Camera();
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
  escena.add(quad);

  /* ---------- shaders ---------- */
  const VERT = `
    precision highp float;
    attribute vec3 position; attribute vec2 uv;
    varying vec2 vUv, vL, vR, vT, vB;
    uniform vec2 uTexel;
    void main(){
      vUv = uv;
      vL = uv - vec2(uTexel.x, 0.0); vR = uv + vec2(uTexel.x, 0.0);
      vT = uv + vec2(0.0, uTexel.y); vB = uv - vec2(0.0, uTexel.y);
      gl_Position = vec4(position.xy, 0.0, 1.0);
    }`;

  function mat(frag, unis) {
    return new THREE.RawShaderMaterial({
      vertexShader: VERT, fragmentShader: frag,
      uniforms: Object.assign({ uTexel: { value: new THREE.Vector2() } }, unis),
      depthTest: false, depthWrite: false,
    });
  }

  const matSplat = mat(`
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D uBase;
    uniform float uAspecto, uRadio;
    uniform vec3 uColor;
    uniform vec2 uPunto, uPrevio;
    void main(){
      vec3 base = texture2D(uBase, vUv).xyz;
      vec2 p = uPunto;  p.x *= uAspecto;
      vec2 q = uPrevio; q.x *= uAspecto;
      vec2 uv = vUv;    uv.x *= uAspecto;
      vec2 seg = p - q;
      float L2 = dot(seg, seg);
      vec2 rel = uv - q;
      float t = (L2 > 1e-9) ? clamp(dot(rel, seg) / L2, 0.0, 1.0) : 0.0;
      vec2 perp = rel - seg * t;
      float fuerza = exp(-dot(perp, perp) / uRadio);
      gl_FragColor = vec4(base + fuerza * uColor, 1.0);
    }`, {
    uBase: { value: null }, uAspecto: { value: 1 }, uRadio: { value: RADIO_SPLAT },
    uColor: { value: new THREE.Vector3() },
    uPunto: { value: new THREE.Vector2() }, uPrevio: { value: new THREE.Vector2() },
  });

  const matAdvec = mat(`
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D uVelocidad, uFuente;
    uniform vec2 uTexelV;
    uniform float uDt, uDisipa;
    void main(){
      vec2 coord = vUv - uDt * texture2D(uVelocidad, vUv).xy * uTexelV;
      gl_FragColor = vec4(uDisipa * texture2D(uFuente, coord).rgb, 1.0);
    }`, {
    uVelocidad: { value: null }, uFuente: { value: null },
    uTexelV: { value: new THREE.Vector2() }, uDt: { value: 0 }, uDisipa: { value: 1 },
  });

  const matCurl = mat(`
    precision highp float;
    varying vec2 vUv, vL, vR, vT, vB;
    uniform sampler2D uVelocidad;
    void main(){
      float L = texture2D(uVelocidad, vL).y;
      float R = texture2D(uVelocidad, vR).y;
      float T = texture2D(uVelocidad, vT).x;
      float B = texture2D(uVelocidad, vB).x;
      gl_FragColor = vec4(0.5 * (R - L - T + B), 0.0, 0.0, 1.0);
    }`, { uVelocidad: { value: null } });

  const matVort = mat(`
    precision highp float;
    varying vec2 vUv, vL, vR, vT, vB;
    uniform sampler2D uVelocidad, uCurl;
    uniform float uFuerza, uDt;
    void main(){
      float L = texture2D(uCurl, vL).x;
      float R = texture2D(uCurl, vR).x;
      float T = texture2D(uCurl, vT).x;
      float B = texture2D(uCurl, vB).x;
      float C = texture2D(uCurl, vUv).x;
      vec2 f = 0.5 * vec2(abs(T) - abs(B), abs(R) - abs(L));
      f /= length(f) + 0.0001;
      f *= uFuerza * C;
      f.y *= -1.0;
      vec2 vel = texture2D(uVelocidad, vUv).xy;
      gl_FragColor = vec4(vel + f * uDt, 0.0, 1.0);
    }`, { uVelocidad: { value: null }, uCurl: { value: null }, uFuerza: { value: CURL }, uDt: { value: 0 } });

  const matDiv = mat(`
    precision highp float;
    varying vec2 vUv, vL, vR, vT, vB;
    uniform sampler2D uVelocidad;
    void main(){
      float L = texture2D(uVelocidad, vL).x;
      float R = texture2D(uVelocidad, vR).x;
      float T = texture2D(uVelocidad, vT).y;
      float B = texture2D(uVelocidad, vB).y;
      vec2 C = texture2D(uVelocidad, vUv).xy;
      if (vL.x < 0.0) { L = -C.x; }
      if (vR.x > 1.0) { R = -C.x; }
      if (vT.y > 1.0) { T = -C.y; }
      if (vB.y < 0.0) { B = -C.y; }
      gl_FragColor = vec4(0.5 * (R - L + T - B), 0.0, 0.0, 1.0);
    }`, { uVelocidad: { value: null } });

  const matClear = mat(`
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D uBase;
    uniform float uFactor;
    void main(){ gl_FragColor = uFactor * texture2D(uBase, vUv); }`,
    { uBase: { value: null }, uFactor: { value: DECAE_PRESION } });

  const matPres = mat(`
    precision highp float;
    varying vec2 vUv, vL, vR, vT, vB;
    uniform sampler2D uPresion, uDivergencia;
    void main(){
      float L = texture2D(uPresion, vL).x;
      float R = texture2D(uPresion, vR).x;
      float T = texture2D(uPresion, vT).x;
      float B = texture2D(uPresion, vB).x;
      float div = texture2D(uDivergencia, vUv).x;
      gl_FragColor = vec4((L + R + B + T - div) * 0.25, 0.0, 0.0, 1.0);
    }`, { uPresion: { value: null }, uDivergencia: { value: null } });

  const matGrad = mat(`
    precision highp float;
    varying vec2 vUv, vL, vR, vT, vB;
    uniform sampler2D uPresion, uVelocidad;
    void main(){
      float L = texture2D(uPresion, vL).x;
      float R = texture2D(uPresion, vR).x;
      float T = texture2D(uPresion, vT).x;
      float B = texture2D(uPresion, vB).x;
      vec2 vel = texture2D(uVelocidad, vUv).xy;
      vel -= vec2(R - L, T - B);
      gl_FragColor = vec4(vel, 0.0, 1.0);
    }`, { uPresion: { value: null }, uVelocidad: { value: null } });

  /* la tinta se convierte en relieve: normales por diferencias finitas */
  const matNormal = mat(`
    precision highp float;
    varying vec2 vUv, vR, vB;
    uniform sampler2D uTinta;
    uniform float uEps;
    void main(){
      float C = length(texture2D(uTinta, vUv).xy);
      float R = length(texture2D(uTinta, vR).xy);
      float B = length(texture2D(uTinta, vB).xy);
      vec2 dN = vec2(R - C, B - C);
      vec3 N = vec3(0.0, 1.0, 0.0);
      vec2 eps = vec2(uEps, 0.0);
      N = normalize(N + cross(dN.x * N + eps.xyy, dN.y * N + eps.yyx));
      gl_FragColor = vec4(N, 1.0);
    }`, { uTinta: { value: null }, uEps: { value: EPS_NORMAL } });

  const matDelta = mat(`
    precision highp float;
    varying vec2 vUv, vR, vB;
    uniform sampler2D uNormalT;
    void main(){
      vec3 C = texture2D(uNormalT, vUv).xyz;
      vec3 R = texture2D(uNormalT, vR).xyz;
      vec3 B = texture2D(uNormalT, vB).xyz;
      gl_FragColor = vec4(abs(R - C) + abs(B - C), 1.0);
    }`, { uNormalT: { value: null } });

  /* presentación: ESPUMA nacarada como la referencia — cuerpo vaporoso
     luminoso + filos rizados brillantes (delta de normales) + grano de
     espuma que viaja con el fluido + chispa especular. Sale sobre negro
     y el mix-blend-mode:screen del canvas la funde con la página. */
  const matAgua = mat(`
    precision highp float;
    varying vec2 vUv;
    uniform sampler2D uTinta, uNormalT, uDelta;
    uniform vec3 uTinte, uBrillo;
    uniform float uOpacidad, uModo;
    float hashGG(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    void main(){
      vec3 tinta = texture2D(uTinta, vUv).rgb;
      float pres = clamp(tinta.b * 0.12, 0.0, 1.0);
      /* transparente en ambos modos: en screen el negro transparente no suma */
      if (pres < 0.008) { gl_FragColor = vec4(0.0); return; }
      vec3 N = normalize(texture2D(uNormalT, vUv).xzy); // y-up → z hacia cámara
      vec3 L = normalize(vec3(-0.35, 0.55, 0.75));
      float dif = clamp(dot(N, L), 0.0, 1.0);
      float esp = pow(clamp(dot(reflect(-L, N), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 30.0);
      vec3 filoC = texture2D(uDelta, vUv).rgb;
      float filo = clamp((filoC.x + filoC.z) * 2.2, 0.0, 1.0);
      /* grano de espuma: ruido fino arrastrado por el propio campo */
      float gr = hashGG(vUv * 640.0 + tinta.rg * 2.5);
      float burbuja = smoothstep(0.55, 1.0, gr) * pres;
      if (uModo > 0.5) {
        /* secciones oscuras: espuma nacarada ADITIVA (canvas en screen) —
           el cuerpo es tenue; la estructura la dan filos y granos */
        vec3 col = uBrillo * pres * (0.12 + 0.10 * dif)   // cuerpo vaporoso
                 + uBrillo * filo * 0.95                   // filos rizados
                 + uBrillo * burbuja * 0.55                // granos de espuma
                 + uBrillo * esp * 0.35                    // chispa especular
                 + uTinte * pres * 0.15;                   // tinte de la sección
        gl_FragColor = vec4(col * uOpacidad, 1.0);
      } else {
        /* secciones claras: la misma espuma en tinta azul (alpha normal):
           sobre papel solo se ve lo más oscuro que el papel */
        vec3 col = uTinte * (0.62 + 0.20 * dif);
        col = mix(col, uTinte * 0.55, burbuja);            // granos más densos
        col = mix(col, uTinte * 0.78, filo * 0.7);         // filos marcados
        col += uBrillo * esp * 0.25;
        float a = smoothstep(0.0, 0.9, pres + filo * 0.25) * uOpacidad;
        gl_FragColor = vec4(col, a);
      }
    }`, {
    uTinta: { value: null }, uNormalT: { value: null }, uDelta: { value: null },
    uTinte: { value: new THREE.Color(0x223f83) },
    uBrillo: { value: new THREE.Color(0xf4efe2) },
    uOpacidad: { value: 0.55 },
    uModo: { value: 0 },
  });
  matAgua.transparent = true;

  /* ---------- render targets (ping-pong) ---------- */
  function rt(w, h) {
    return new THREE.WebGLRenderTarget(w, h, {
      type: THREE.HalfFloatType, format: THREE.RGBAFormat,
      minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
      wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping,
      depthBuffer: false,
    });
  }
  function doble(w, h) {
    return { read: rt(w, h), write: rt(w, h),
      swap() { const t = this.read; this.read = this.write; this.write = t; },
      texel: new THREE.Vector2(1 / w, 1 / h) };
  }

  let velocidad, tinta, presion, divergencia, curlRT, normalRT, deltaRT;
  function dimensiona() {
    const ratio = innerWidth / Math.max(1, innerHeight);
    const hs = Math.max(64, Math.round(Math.sqrt(PIXELES_SIM / ratio)));
    const ws = Math.max(64, Math.round(hs * ratio));
    const wd = ws * 2, hd = hs * 2;          // la tinta al doble de resolución
    for (const r of [velocidad, tinta, presion]) if (r) { r.read.dispose(); r.write.dispose(); }
    for (const r of [divergencia, curlRT, normalRT, deltaRT]) if (r) r.dispose();
    velocidad = doble(ws, hs);
    tinta = doble(wd, hd);
    presion = doble(ws, hs);
    divergencia = rt(ws, hs);
    curlRT = rt(ws, hs);
    normalRT = rt(wd, hd);
    deltaRT = rt(wd, hd);
    renderer.setSize(innerWidth, innerHeight, false);
  }
  dimensiona();
  addEventListener('resize', dimensiona);

  function pasa(material, destino) {
    quad.material = material;
    renderer.setRenderTarget(destino);
    renderer.render(escena, camara);
  }

  /* ---------- puntero ---------- */
  const punt = { x: 0.5, y: 0.5, px: 0.5, py: 0.5, dx: 0, dy: 0, movido: false };
  let ultimoMov = -1e9, dormido = true;
  addEventListener('pointermove', e => {
    const x = e.clientX / innerWidth, y = 1 - e.clientY / innerHeight;
    if (punt.movido) { punt.dx += x - punt.x; punt.dy += y - punt.y; }
    else { punt.px = x; punt.py = y; punt.dx = x - punt.px; punt.dy = y - punt.py; }
    punt.x = x; punt.y = y; punt.movido = true;
    ultimoMov = performance.now();
    if (dormido) { dormido = false; requestAnimationFrame(frame); }
  }, { passive: true });
  addEventListener('pointerdown', e => {
    if (document.body.classList.contains('nav-open')) return;
    /* chapuzón: mancha ancha sin dirección que el campo dispersa solo */
    salpica(e.clientX / innerWidth, 1 - e.clientY / innerHeight,
            e.clientX / innerWidth, 1 - e.clientY / innerHeight,
            new THREE.Vector3(0, 0, 1.6), RADIO_SPLAT * 9);
    ultimoMov = performance.now();
    if (dormido) { dormido = false; requestAnimationFrame(frame); }
  }, { passive: true });

  function salpica(x, y, px, py, color, radio) {
    matSplat.uniforms.uAspecto.value = innerWidth / innerHeight;
    matSplat.uniforms.uPunto.value.set(x, y);
    matSplat.uniforms.uPrevio.value.set(px, py);
    matSplat.uniforms.uRadio.value = radio;
    // al campo de velocidad
    matSplat.uniforms.uBase.value = velocidad.read.texture;
    matSplat.uniforms.uTexel.value.copy(velocidad.texel);
    matSplat.uniforms.uColor.value.set(color.x, color.y, 0);
    pasa(matSplat, velocidad.write); velocidad.swap();
    // a la tinta (misma energía + presencia)
    matSplat.uniforms.uBase.value = tinta.read.texture;
    matSplat.uniforms.uTexel.value.copy(tinta.texel);
    matSplat.uniforms.uColor.value.copy(color);
    pasa(matSplat, tinta.write); tinta.swap();
  }

  /* ---------- tinte según fondo (lo marca el cursor custom: #cc.cc-dark) ---------- */
  const tinteClaro = new THREE.Color(0x223f83), brilloClaro = new THREE.Color(0xeae3cf);
  const tinteOscuro = new THREE.Color(0xc9b07e), brilloOscuro = new THREE.Color(0xf4ead2);
  const cc = () => document.getElementById('cc');

  /* ---------- bucle ---------- */
  let tPrev = performance.now();
  function frame() {
    const ahora = performance.now();
    const dt = Math.min(0.033, (ahora - tPrev) / 1000);
    tPrev = ahora;

    /* siesta: sin ratón un rato, la estela ya se ha disipado — parar del todo */
    if (ahora - ultimoMov > IDLE_MS) {
      renderer.setRenderTarget(null);
      renderer.clear(true, false, false);
      dormido = true;
      return;
    }

    if (punt.movido && (Math.abs(punt.dx) > 1e-5 || Math.abs(punt.dy) > 1e-5)) {
      salpica(punt.x, punt.y, punt.x - punt.dx, punt.y - punt.dy,
        new THREE.Vector3(punt.dx * FUERZA_GESTO, punt.dy * FUERZA_GESTO, 0.22),
        RADIO_SPLAT);
      punt.dx = 0; punt.dy = 0;
    }

    // curl → vorticity → divergencia → presión (decae + 2 Jacobi) → proyección
    matCurl.uniforms.uVelocidad.value = velocidad.read.texture;
    matCurl.uniforms.uTexel.value.copy(velocidad.texel);
    pasa(matCurl, curlRT);

    matVort.uniforms.uVelocidad.value = velocidad.read.texture;
    matVort.uniforms.uCurl.value = curlRT.texture;
    matVort.uniforms.uDt.value = dt;
    matVort.uniforms.uTexel.value.copy(velocidad.texel);
    pasa(matVort, velocidad.write); velocidad.swap();

    matDiv.uniforms.uVelocidad.value = velocidad.read.texture;
    matDiv.uniforms.uTexel.value.copy(velocidad.texel);
    pasa(matDiv, divergencia);

    matClear.uniforms.uBase.value = presion.read.texture;
    matClear.uniforms.uTexel.value.copy(presion.texel);
    pasa(matClear, presion.write); presion.swap();

    matPres.uniforms.uDivergencia.value = divergencia.texture;
    matPres.uniforms.uTexel.value.copy(presion.texel);
    for (let i = 0; i < ITER_PRESION; i++) {
      matPres.uniforms.uPresion.value = presion.read.texture;
      pasa(matPres, presion.write); presion.swap();
    }

    matGrad.uniforms.uPresion.value = presion.read.texture;
    matGrad.uniforms.uVelocidad.value = velocidad.read.texture;
    matGrad.uniforms.uTexel.value.copy(velocidad.texel);
    pasa(matGrad, velocidad.write); velocidad.swap();

    // advección de la velocidad y de la tinta
    matAdvec.uniforms.uVelocidad.value = velocidad.read.texture;
    matAdvec.uniforms.uFuente.value = velocidad.read.texture;
    matAdvec.uniforms.uTexelV.value.copy(velocidad.texel);
    matAdvec.uniforms.uTexel.value.copy(velocidad.texel);
    matAdvec.uniforms.uDt.value = dt;
    matAdvec.uniforms.uDisipa.value = DISIPA_VEL;
    pasa(matAdvec, velocidad.write); velocidad.swap();

    matAdvec.uniforms.uVelocidad.value = velocidad.read.texture;
    matAdvec.uniforms.uFuente.value = tinta.read.texture;
    matAdvec.uniforms.uTexel.value.copy(tinta.texel);
    matAdvec.uniforms.uDisipa.value = DISIPA_TINTA;
    pasa(matAdvec, tinta.write); tinta.swap();

    // relieve líquido: normales + filo
    matNormal.uniforms.uTinta.value = tinta.read.texture;
    matNormal.uniforms.uTexel.value.copy(tinta.texel);
    pasa(matNormal, normalRT);

    matDelta.uniforms.uNormalT.value = normalRT.texture;
    matDelta.uniforms.uTexel.value.copy(tinta.texel);
    pasa(matDelta, deltaRT);

    // presentación (si el cursor custom está escondido, no pintamos)
    renderer.setRenderTarget(null);
    renderer.clear(true, false, false);
    const c = cc();
    if (!c || !c.classList.contains('cc-hidden')) {
      const oscuro = c && c.classList.contains('cc-dark');
      cv.style.mixBlendMode = oscuro ? 'screen' : 'normal';
      matAgua.uniforms.uModo.value = oscuro ? 1 : 0;
      matAgua.uniforms.uTinte.value.lerp(oscuro ? tinteOscuro : tinteClaro, 0.08);
      matAgua.uniforms.uBrillo.value.lerp(oscuro ? brilloOscuro : brilloClaro, 0.08);
      matAgua.uniforms.uOpacidad.value = oscuro ? 0.85 : 0.55;
      matAgua.uniforms.uTinta.value = tinta.read.texture;
      matAgua.uniforms.uNormalT.value = normalRT.texture;
      matAgua.uniforms.uDelta.value = deltaRT.texture;
      matAgua.uniforms.uTexel.value.copy(tinta.texel);
      quad.material = matAgua;
      renderer.render(escena, camara);
    }
    requestAnimationFrame(frame);
  }
  // primer arranque dormido: despierta con el primer pointermove
}
