/* Agua 3D vista desde arriba — sustituye a los separadores de ola 2D.
   Superficie de océano cenital por shader: oleaje fBm advectando en dos
   direcciones, normales por diferencias finitas (relieve real), sol con
   destellos dorados, espuma en las crestas y línea de agua ondulada que
   muerde la sección de arriba. Un canvas WebGL por separador; los canvas
   2D originales quedan ocultos de fallback (móvil/sin WebGL2 los conserva). */
import * as THREE from 'three';

if (window.GG_FLUID) {
  try { init(); } catch (e) { console.error('GG agua3d:', e); }
}

function init() {
  const DPR = Math.min((devicePixelRatio || 1) * 2, 3);
  const seps = [...document.querySelectorAll('canvas.wave-sep')];
  if (!seps.length) return;

  const FRAG = `
    precision highp float;
    varying vec2 vUv;
    uniform float uTime, uAspecto;
    uniform vec3 uAgua, uProf, uSig;
    float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float vnoise(vec2 p){
      vec2 i = floor(p), f = fract(p);
      vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
                 mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
    }
    float fbm(vec2 p){
      float v = 0.0, a = 0.5;
      for (int k = 0; k < 4; k++){ v += a * vnoise(p); p *= 2.07; a *= 0.5; }
      return v;
    }
    float altura(vec2 p){
      float h1 = fbm(p * 1.6 + vec2(uTime * 0.10, uTime * 0.045));
      float h2 = fbm(p * 3.2 - vec2(uTime * 0.07, uTime * 0.09) + 7.3);
      return h1 * 0.65 + h2 * 0.35;
    }
    void main(){
      // oleaje ancho: pocas olas grandes a lo largo de la franja
      vec2 p = vec2(vUv.x * uAspecto * 1.5, vUv.y * 1.1);
      float h = altura(p);
      // normales por diferencias finitas: el relieve del oleaje
      float e = 0.09;
      float hx = altura(p + vec2(e, 0.0));
      float hy = altura(p + vec2(0.0, e));
      vec3 N = normalize(vec3(-(hx - h) / e * 0.38, 1.0, -(hy - h) / e * 0.38));
      // sol bajo cálido + vista cenital
      vec3 L = normalize(vec3(-0.45, 0.75, 0.30));
      vec3 V = vec3(0.0, 1.0, 0.0);
      float dif = clamp(dot(N, L), 0.0, 1.0);
      vec3 col = mix(uProf, uAgua, smoothstep(0.2, 0.78, h));
      col *= 0.82 + 0.34 * dif;
      vec3 Hh = normalize(L + V);
      float nh = max(dot(N, Hh), 0.0);
      float glint = pow(nh, 90.0) * 0.5 + pow(nh, 320.0) * 0.9;
      col += vec3(1.0, 0.82, 0.5) * glint;
      // espuma solo en las crestas altas, con borde roto suave
      float foam = smoothstep(0.8, 0.93, h + 0.1 * vnoise(p * 5.0 + vec2(uTime * 0.3, 0.0)));
      col = mix(col, vec3(0.93, 0.9, 0.82), foam * 0.7);
      // línea de agua ondulada y nítida arriba (hacia la sección anterior)
      float ondula = (fbm(vec2(vUv.x * uAspecto * 0.9 + uTime * 0.04, 3.7)) - 0.5) * 0.2;
      float alfa = smoothstep(0.83 + ondula, 0.75 + ondula, vUv.y);
      // filo de espuma justo en la línea de agua
      float filoLinea = smoothstep(0.85 + ondula, 0.8 + ondula, vUv.y)
                      * smoothstep(0.73 + ondula, 0.8 + ondula, vUv.y);
      col = mix(col, vec3(0.95, 0.93, 0.86), filoLinea * 0.85);
      // por abajo se funde al color de la sección entrante
      col = mix(col, uSig, smoothstep(0.4, 0.02, vUv.y));
      gl_FragColor = vec4(col, alfa);
    }`;

  const VERT = `
    precision highp float;
    attribute vec3 position; attribute vec2 uv;
    varying vec2 vUv;
    void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

  for (const old of seps) {
    const cv = document.createElement('canvas');
    cv.className = 'agua3dC';
    cv.setAttribute('aria-hidden', 'true');
    old.parentElement.insertBefore(cv, old);
    old.style.display = 'none';

    const renderer = new THREE.WebGLRenderer({
      canvas: cv, alpha: true, antialias: false, depth: false, stencil: false,
      premultipliedAlpha: false, powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(DPR);
    const escena = new THREE.Scene();
    const camara = new THREE.Camera();
    const mat = new THREE.RawShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, transparent: true,
      depthTest: false, depthWrite: false,
      uniforms: {
        uTime: { value: Math.random() * 80 },     // cada separador, su fase
        uAspecto: { value: 8 },
        uAgua: { value: new THREE.Color(0x2c498f) },
        uProf: { value: new THREE.Color(0x14244f) },
        uSig: { value: new THREE.Color(old.dataset.fill || '#101c3c') },
      },
    });
    escena.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat));

    let activo = false, w = 0, h = 0;
    function rs() {
      w = cv.clientWidth || cv.parentElement.clientWidth;
      h = cv.clientHeight || 120;
      renderer.setSize(w, h, false);
      mat.uniforms.uAspecto.value = w / Math.max(1, h);
    }
    rs();
    addEventListener('resize', rs);
    new IntersectionObserver(es => es.forEach(en => { activo = en.isIntersecting; })).observe(cv);

    const reloj = new THREE.Clock();
    (function frame() {
      const dt = Math.min(0.05, reloj.getDelta());
      if (activo && w > 1) {
        mat.uniforms.uTime.value += dt;
        renderer.render(escena, camara);
      }
      requestAnimationFrame(frame);
    })();
  }
}
