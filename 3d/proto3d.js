/* Prototipo 3D ggelcano.com — capa aditiva sobre la web real.
   Escena 1 (hero): nao Victoria toon + contorno, mar Gerstner con sol, espuma
   de cresta, estela del casco y flotación acoplada a la ola real; velas con
   viento, fanal de popa que se enciende al final y gaviotas lejanas.
   Escena 2 (interludio): globo con continentes en matriz de puntos dorados,
   la ruta real de la 1ª circunnavegación dibujándose, atmósfera, estrellas
   y etiquetas de hitos proyectadas.
   Si el dispositivo no cumple (móvil, reduced-motion, sin WebGL2), no se activa
   nada y la web original queda intacta. */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import LAND from './land-dots.js';

window.__p3dErrors = [];
window.addEventListener('error', e => window.__p3dErrors.push(String(e.message)));
window.addEventListener('unhandledrejection', e => window.__p3dErrors.push(String(e.reason)));

if (new URLSearchParams(location.search).has('dbg')) {
  setTimeout(() => {
    const ilu = document.querySelector('#interludio');
    let trap = '';
    for (let el = ilu; el && el !== document.documentElement; el = el.parentElement) {
      const cs = getComputedStyle(el);
      for (const prop of ['transform', 'filter', 'backdropFilter', 'perspective', 'contain', 'willChange', 'containerType']) {
        const v = cs[prop];
        if (v && v !== 'none' && v !== 'normal' && v !== 'auto') trap += `${el.tagName}#${el.id || el.className}:${prop}=${v} `;
      }
    }
    document.title = `TRAP[${trap.slice(0, 400)}] P3D skip:${!!window.__p3dSkip} ready:${!!window.__p3dReady}`
      + ` gsap:${!!window.gsap} scrollY:${Math.round(scrollY)}`
      + ` iluTop:${Math.round(ilu ? ilu.getBoundingClientRect().top + scrollY : -1)}`
      + ` docH:${document.documentElement.scrollHeight}`
      + ` errs:[${window.__p3dErrors.join(' | ').slice(0, 300)}]`;
  }, 2500);
}

const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const movil = matchMedia('(max-width: 900px), (pointer: coarse)').matches;
const gl2 = (() => { try { return !!document.createElement('canvas').getContext('webgl2'); } catch { return false; } })();

// Paleta de marca (de las variables CSS de la web)
const C = {
  paper: 0xf4efe2, ink: 0x1b2238, noche: 0x101c3c, abismo: 0x070d20,
  azul: 0x223f83, azulSoft: 0x3a5aa8, gold: 0xb08d57, goldLight: 0xc9b07e, cream: 0xfaf7ee,
};

const DPR = Math.min((devicePixelRatio || 1) * 3, 4.5);
const loader = new GLTFLoader();
loader.setMeshoptDecoder(MeshoptDecoder);

/* ============================================================
   OLAS GERSTNER — una sola definición para shader (GLSL) y JS
   (la flotación de la nao muestrea la MISMA agua que se pinta)
   ============================================================ */
const Q_OLA = 0.72; // pellizco global de cresta (Σ st·Q < 1 o la ola se pliega)
// las olas viajan hacia -X: la nao (proa +X) navega CONTRA el mar
const OLAS = [
  { d: [-0.94, -0.34], wl: 16.0, st: 0.18 },
  { d: [-0.48, 0.88], wl: 9.5, st: 0.16 },
  { d: [-0.89, 0.45], wl: 5.8, st: 0.14 },
  { d: [-0.22, 0.97], wl: 3.2, st: 0.10 },
];
const olasCalc = OLAS.map(o => {
  const L = Math.hypot(o.d[0], o.d[1]);
  const k = 2 * Math.PI / o.wl;
  return {
    dx: o.d[0] / L, dy: o.d[1] / L, k,
    A: o.st / k,
    w: Math.sqrt(9.8 * k) * 0.7,
  };
});
function alturaOla(x, y, t) {
  let h = 0;
  for (const o of olasCalc) h += o.A * Math.sin(o.k * (o.dx * x + o.dy * y) - o.w * t);
  return h;
}
// GLSL desenrollado, mismos números que olasCalc
const OLAS_GLSL = olasCalc.map(o => {
  const f5 = n => n.toFixed(5);
  return `{
    float f = ${f5(o.k)} * (${f5(o.dx)} * p0.x + ${f5(o.dy)} * p0.y) - ${f5(o.w)} * uTime;
    float c = cos(f), s = sin(f);
    acc.x += ${f5(Q_OLA * o.A)} * ${f5(o.dx)} * c;
    acc.y += ${f5(Q_OLA * o.A)} * ${f5(o.dy)} * c;
    acc.z += ${f5(o.A)} * s;
    nrm.x -= ${f5(o.dx)} * ${f5(o.k * o.A)} * c;
    nrm.y -= ${f5(o.dy)} * ${f5(o.k * o.A)} * c;
    nrm.z -= ${f5(Q_OLA * o.k * o.A)} * s;
    jac   += ${f5(Q_OLA * o.k * o.A)} * s;
  }`;
}).join('\n');

function rendererEn(canvas) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  r.setPixelRatio(DPR);
  return r;
}

/* texturas de canvas: punto redondo, halo y gaviota de tinta */
function texturaPunto() {
  const cv = document.createElement('canvas'); cv.width = cv.height = 32;
  const g = cv.getContext('2d');
  const grad = g.createRadialGradient(16, 16, 0, 16, 16, 15);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.7, 'rgba(255,255,255,.9)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 32, 32);
  const t = new THREE.CanvasTexture(cv); return t;
}
function texturaHalo() {
  const cv = document.createElement('canvas'); cv.width = cv.height = 128;
  const g = cv.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 2, 64, 64, 62);
  grad.addColorStop(0, 'rgba(255,222,150,.95)');
  grad.addColorStop(0.35, 'rgba(255,206,120,.4)');
  grad.addColorStop(1, 'rgba(255,206,120,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(cv);
}
function texturaGaviota() {
  const cv = document.createElement('canvas'); cv.width = 64; cv.height = 32;
  const g = cv.getContext('2d');
  g.strokeStyle = 'rgba(27,34,56,.9)'; g.lineWidth = 2.6; g.lineCap = 'round';
  g.beginPath(); g.moveTo(6, 22); g.quadraticCurveTo(20, 8, 32, 18);
  g.quadraticCurveTo(44, 8, 58, 22); g.stroke();
  return new THREE.CanvasTexture(cv);
}

/* Cámara Blender: carga el GLB-timeline y devuelve {camera, setProgress} (patrón de la skill) */
function montaCamara(gltf, escena) {
  escena.add(gltf.scene);
  const camera = gltf.cameras[0];
  const mixer = new THREE.AnimationMixer(gltf.scene);
  const dur = Math.max(...gltf.animations.map(c => c.duration));
  const acciones = gltf.animations.map(c => {
    const a = mixer.clipAction(c); a.play(); a.paused = true; return a;
  });
  return {
    camera,
    setProgress(p) {
      const t = Math.min(p * dur, dur - 1e-4);
      acciones.forEach(a => { a.time = t; });
      mixer.update(0);
    },
  };
}

async function init() {
  document.documentElement.classList.add('p3d');
  gsap.registerPlugin(ScrollTrigger);

  const [shipG, camHeroG, camGlobeG] = await Promise.all([
    loader.loadAsync('3d/ship.glb'),
    loader.loadAsync('3d/cam-hero.glb'),
    loader.loadAsync('3d/cam-globe.glb'),
  ]);

  const uT = { value: 0 }; // reloj compartido (velas, banderas)

  /* ============ ESCENA 1: HERO ============ */
  const heroSec = document.querySelector('#inicio');
  const heroCv = document.createElement('canvas');
  heroCv.id = 'hero3d';
  heroSec.appendChild(heroCv);
  const heroR = rendererEn(heroCv);
  const heroSc = new THREE.Scene();
  heroSc.fog = new THREE.FogExp2(C.paper, 0.085); // arranca denso: la nao está "en la niebla"

  // sol cálido + relleno de cielo (el especular del agua usa la misma dirección)
  const luzSol = new THREE.DirectionalLight(0xfff4dd, 1.35);
  luzSol.position.set(6, 9, 5);
  heroSc.add(luzSol, new THREE.HemisphereLight(0xfdf6e3, 0x223f83, 0.75));
  const sunDir = luzSol.position.clone().normalize();

  /* ---- mar Gerstner: crestas pellizcadas, sol, fresnel, espuma y estela ---- */
  const seaUniforms = {
    uTime: { value: 0 },
    uDeep: { value: new THREE.Color(C.azul) },
    uSoft: { value: new THREE.Color(C.azulSoft) },
    uPaper: { value: new THREE.Color(C.paper) },
    uCrest: { value: new THREE.Color(0xf0ead8) },
    uFogDensity: { value: 0.085 },
    uSunDir: { value: sunDir },
    uShip: { value: new THREE.Vector2(0, 0) },
    /* el cursor sobre el mar: (x, y local, fuerza 0..1) + 10 ondas viajeras
       (x, y, edad, amplitud) que deja la estela del puntero */
    uPunt: { value: new THREE.Vector3(0, 0, 0) },
    uRip: { value: Array.from({ length: 10 }, () => new THREE.Vector4(0, 0, 99, 0)) },
  };
  const sea = new THREE.Mesh(
    new THREE.PlaneGeometry(170, 170, 200, 200),
    new THREE.ShaderMaterial({
      uniforms: seaUniforms,
      transparent: true,
      vertexShader: `
        uniform float uTime;
        uniform vec3 uPunt;
        uniform vec4 uRip[10];
        varying vec3 vNW; varying vec3 vWPos; varying vec2 vLocal;
        varying float vH; varying float vJac; varying float vDist; varying float vStir;
        void main(){
          vec2 p0 = position.xy;
          vec3 acc = vec3(0.0);
          vec3 nrm = vec3(0.0, 0.0, 1.0);
          float jac = 0.0;
          ${OLAS_GLSL}
          /* el cursor aparta el agua: depresión con inercia + ondas que viajan */
          vec2 dpu = p0 - uPunt.xy;
          float distur = -uPunt.z * 0.26 * exp(-dot(dpu, dpu) / 1.3);
          for (int i = 0; i < 10; i++){
            float rr = length(p0 - uRip[i].xy);
            float env = uRip[i].w * exp(-uRip[i].z * 1.35) * exp(-rr * 0.5);
            distur += 0.18 * env * sin(rr * 3.4 - uRip[i].z * 4.2);
          }
          acc.z += distur;
          vStir = distur;
          vec3 pos = position + acc;
          vH = acc.z;
          vJac = jac;
          vLocal = p0;
          // el plano está rotado -90° en X: normal local (x,y,z) → mundo (x,z,-y)
          vNW = vec3(nrm.x, nrm.z, -nrm.y);
          vWPos = (modelMatrix * vec4(pos, 1.0)).xyz;
          vec4 mv = modelViewMatrix * vec4(pos, 1.0);
          vDist = -mv.z;
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 uDeep, uSoft, uPaper, uCrest, uSunDir;
        uniform float uFogDensity, uTime;
        uniform vec2 uShip;
        varying vec3 vNW; varying vec3 vWPos; varying vec2 vLocal;
        varying float vH; varying float vJac; varying float vDist; varying float vStir;
        float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float vnoise(vec2 p){
          vec2 i = floor(p), f = fract(p);
          vec2 u = f * f * (3.0 - 2.0 * f);
          return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
                     mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
        }
        float fbm(vec2 p){
          float v = 0.0, a = 0.5;
          for (int k = 0; k < 3; k++){ v += a * vnoise(p); p *= 2.13; a *= 0.5; }
          return v;
        }
        void main(){
          vec3 N = normalize(vNW);
          // detalle fino de superficie: el ruido perturba la normal cerca de cámara
          float d1 = vnoise(vLocal * 2.2 + vec2(uTime * 0.20, 0.0));
          float d2 = vnoise(vLocal * 2.2 + vec2(37.7, uTime * 0.16));
          N = normalize(N + vec3((d1 - 0.5) * 0.22, 0.0, (d2 - 0.5) * 0.22));
          vec3 V = normalize(cameraPosition - vWPos);
          float lam = clamp(dot(N, uSunDir), 0.0, 1.0);
          // tinta del mar: profundidad por altura + cara iluminada algo más clara
          vec3 col = mix(uDeep, uSoft, clamp(smoothstep(-0.6, 0.9, vH) * 0.6 + lam * 0.35, 0.0, 1.0));
          // relleno de cielo en las caras que miran arriba (que el mar cercano no sea un bloque)
          col = mix(col, uSoft, clamp(N.y, 0.0, 1.0) * 0.22);
          // sol: brillo ancho + chispa fina
          vec3 Hv = normalize(uSunDir + V);
          float nh = max(dot(N, Hv), 0.0);
          float spec = pow(nh, 90.0) + 0.5 * pow(nh, 240.0);
          col += vec3(1.0, 0.85, 0.6) * spec * 0.8;
          // fresnel: el agua refleja el cielo-papel al mirarla rasante
          float fres = pow(1.0 - max(dot(N, V), 0.0), 3.0);
          col = mix(col, uPaper, fres * 0.42);
          // espuma de cresta: pellizco del jacobiano roto con ruido
          float pin = smoothstep(0.55, 1.0, vJac);
          float nz = fbm(vLocal * 0.9 + vec2(uTime * 0.22, -uTime * 0.17));
          float foam = pin * smoothstep(0.32, 0.72, nz);
          // estela en V tras el casco (la nao vive en el origen mirando +x)
          vec2 rel = vLocal - uShip;
          float behind = -rel.x;
          float semiancho = 0.7 + behind * 0.42;
          float enV = smoothstep(semiancho, semiancho * 0.45, abs(rel.y))
                    * smoothstep(-1.0, 2.0, behind) * exp(-max(behind, 0.0) * 0.13);
          float wn = fbm(vec2(rel.x * 0.55 + uTime * 1.05, rel.y * 1.9));
          float estela = enV * smoothstep(0.3, 0.7, wn) * 1.2;
          // anillo de espuma pegado a la línea de flotación + rompiente de proa
          float e = length(vec2(rel.x / 5.5, rel.y / 1.8));
          float casco = smoothstep(1.32, 1.0, e) * smoothstep(0.86, 1.02, e);
          casco *= 0.5 + 0.5 * fbm(vLocal * 2.3 + vec2(uTime * 0.6, 0.0));
          vec2 proa = rel - vec2(4.9, 0.0);
          float rompiente = exp(-dot(proa * vec2(0.55, 0.75), proa * vec2(0.55, 0.75)))
                          * (0.55 + 0.45 * fbm(vLocal * 3.1 + vec2(-uTime * 0.9, 0.0)));
          /* el agua removida por el cursor levanta espuma */
          float removido = smoothstep(0.015, 0.08, abs(vStir)) * 0.7;
          foam = clamp(foam + estela + casco * 1.6 + rompiente * 1.3 + removido, 0.0, 1.0);
          col = mix(col, uCrest, foam * 0.85);
          // niebla exponencial + horizonte fundido a papel (suave, sin banda dura)
          float fog = 1.0 - exp(-uFogDensity * uFogDensity * vDist * vDist);
          float horizonte = smoothstep(40.0, 82.0, vDist + (nz - 0.5) * 6.0);
          col = mix(col, uPaper, max(fog, horizonte));
          gl_FragColor = vec4(col, 0.97);
        }`,
    })
  );
  sea.rotation.x = -Math.PI / 2;
  heroSc.add(sea);

  /* ---- la nao: toon + contorno estable, menos niebla, velas con viento ---- */
  const escalones = new THREE.DataTexture(
    new Uint8Array([110, 110, 110, 255, 185, 185, 185, 255, 255, 255, 255, 255]),
    3, 1, THREE.RGBAFormat
  );
  escalones.needsUpdate = true;
  // la tela sombrea más claro que la madera: sin escalón oscuro las velas no
  // parecen de cristal contra el cielo-papel
  const escalonesTela = new THREE.DataTexture(
    new Uint8Array([178, 178, 178, 255, 218, 218, 218, 255, 255, 255, 255, 255]),
    3, 1, THREE.RGBAFormat
  );
  escalonesTela.needsUpdate = true;

  const tinta = new THREE.Color(0x2a2017);
  const outlineMat = new THREE.ShaderMaterial({
    uniforms: { uColor: { value: tinta }, uGrosor: { value: 0.04 } },
    vertexShader: `
      uniform float uGrosor;
      void main(){
        vec3 n = normalize(normalMatrix * normal);
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        // grosor proporcional a la distancia: línea de tinta constante en pantalla
        mv.xyz += n * uGrosor * clamp(-mv.z / 14.0, 0.45, 1.8);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `uniform vec3 uColor; void main(){ gl_FragColor = vec4(uColor, 1.0); }`,
    side: THREE.BackSide,
  });

  /* parche común de material: menos niebla que el mar (la nao conserva su color
     a media distancia) y, según el tipo, viento de vela o flameo de bandera */
  function parcheMaterial(m, viento, baseX) {
    m.onBeforeCompile = sh => {
      sh.uniforms.uTime = uT;
      let vs = 'uniform float uTime;\n' + sh.vertexShader;
      if (viento === 'vela') {
        vs = vs.replace('#include <begin_vertex>', `#include <begin_vertex>
          transformed.x += 0.030 * sin(uTime * 1.6 + position.y * 1.7 + position.z * 0.8)
                         + 0.020 * sin(uTime * 2.4 + position.z * 2.6);`);
      } else if (viento === 'bandera') {
        vs = vs.replace('#include <begin_vertex>', `#include <begin_vertex>
          float mGG = clamp((${baseX.toFixed(2)} - position.x) / 2.2, 0.0, 1.0);
          transformed.y += 0.20 * mGG * sin(uTime * 5.2 + position.x * 3.1);
          transformed.z += 0.09 * mGG * sin(uTime * 3.4 + position.x * 2.2 + 1.7);`);
      }
      vs = vs.replace('#include <fog_vertex>', '#include <fog_vertex>\n vFogDepth *= 0.45;');
      sh.vertexShader = vs;
    };
    return m;
  }

  const nao = shipG.scene;
  const SIN_CONTORNO = /Obenque|Estay|Braza|Flechaste|Bal\d|Aro|Pasamanos|Bobstay|Cruz|Ventana|Vigota|CabestranteBarra|Grimpola|Bandera|Espolon|AnclaCepo/;
  const ES_VELA = /^(VelaMayor|GaviaMayor|VelaTrinquete|VelaMesana|Cebadera|Cruz)/;
  const ES_BANDERA = /^(Grimpola|Bandera)/;
  const BASE_BANDERA = { GrimpolaMayor: 0.0, BanderaTrinquete: 3.1, BanderaMesana: -3.85 };
  const mallas = [];
  nao.traverse(o => { if (o.isMesh) mallas.push(o); }); // recoger ANTES de mutar el árbol
  for (const o of mallas) {
    const base = o.material?.color ? o.material.color.clone() : new THREE.Color(0x8a6242);
    const viento = ES_VELA.test(o.name) ? 'vela' : ES_BANDERA.test(o.name) ? 'bandera' : null;
    const m = new THREE.MeshToonMaterial({
      color: base, gradientMap: viento ? escalonesTela : escalones,
      side: THREE.DoubleSide, fog: true,
    });
    parcheMaterial(m, viento, BASE_BANDERA[o.name] || 0);
    o.material = m;
    if (!SIN_CONTORNO.test(o.name)) o.add(new THREE.Mesh(o.geometry, outlineMat));
  }
  const naoGrupo = new THREE.Group();
  naoGrupo.add(nao);
  heroSc.add(naoGrupo);

  // fanal de popa: se enciende al caer la niebla del final del recorrido
  const fanalMesh = nao.getObjectByName('Fanal');
  const fanalColorBase = new THREE.Color(0xe8c97a);
  const fanalColorVivo = new THREE.Color(0xffe9b0);
  const luzFanal = new THREE.PointLight(0xffd28a, 0, 8, 1.8);
  const glowFanal = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texturaHalo(), transparent: true, opacity: 0, depthWrite: false, fog: false,
  }));
  glowFanal.scale.setScalar(1.5);
  if (fanalMesh) {
    fanalMesh.getWorldPosition(luzFanal.position);
    glowFanal.position.copy(luzFanal.position);
    naoGrupo.add(luzFanal, glowFanal);
  }

  // gaviotas de tinta, lejanas, dando vueltas a popa
  const texGav = texturaGaviota();
  const gaviotas = [0, 1, 2].map(i => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({
      map: texGav, transparent: true, opacity: 0.5, depthWrite: false, fog: true,
    }));
    s.scale.set(1.5, 0.75, 1);
    heroSc.add(s);
    return { s, cx: -10 - i * 5, cy: 6.2 + i * 0.9, cz: -4 + i * 6, r: 2.6 + i, w: 0.22 + i * 0.05, f: i * 2.1 };
  });

  const heroCam = montaCamara(camHeroG, heroSc);
  heroCam.camera.near = 0.1; heroCam.camera.far = 400;

  /* el ratón toca el mar: raycast del puntero al plano del agua (y=0) */
  const rayo = new THREE.Raycaster();
  const planoMar = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const puntObjetivo = new THREE.Vector2(0, 0);
  let puntDentro = false, ripIdx = 0;
  const ultimaRip = { x: 0, y: 0, t: 0 };
  const _ndc = new THREE.Vector2(), _hit = new THREE.Vector3();
  addEventListener('pointermove', e => {
    if (!heroEstado.activo) { puntDentro = false; return; }
    const r = heroCv.getBoundingClientRect();
    if (r.width < 2 || e.clientY < r.top - 60 || e.clientY > r.bottom) { puntDentro = false; return; }
    _ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    rayo.setFromCamera(_ndc, heroCam.camera);
    if (!rayo.ray.intersectPlane(planoMar, _hit)) { puntDentro = false; return; }
    const lx = _hit.x, ly = -_hit.z;     // mundo → coords locales del plano
    if (Math.hypot(lx, ly) > 70) { puntDentro = false; return; }
    puntObjetivo.set(lx, ly);
    puntDentro = true;
    /* al desplazarse lo bastante deja una onda viajera detrás */
    const ahora = performance.now();
    if (Math.hypot(lx - ultimaRip.x, ly - ultimaRip.y) > 1.4 && ahora - ultimaRip.t > 90) {
      seaUniforms.uRip.value[ripIdx++ % 10].set(lx, ly, 0, 1);
      ultimaRip.x = lx; ultimaRip.y = ly; ultimaRip.t = ahora;
    }
  }, { passive: true });

  const heroEstado = { fog: 0.085, activo: true, progreso: 0, farol: 0 };
  ScrollTrigger.create({
    /* tramo más corto (140% vs 220%): la secuencia termina antes; el scrub
       más alto deja la cámara flotando en vez de corriendo tras el scroll */
    trigger: '#inicio', start: 'top top', end: '+=140%',
    pin: true, scrub: 1.4, anticipatePin: 1,
    onUpdate(self) {
      heroEstado.progreso = self.progress;
      heroCam.setProgress(self.progress);
      // la niebla se levanta según avanza el plano
      heroEstado.fog = 0.085 - 0.063 * self.progress;
      heroEstado.farol = THREE.MathUtils.smoothstep(self.progress, 0.62, 0.9);
    },
    onToggle(self) { heroEstado.activo = self.isActive; },
  });

  /* ============ ESCENA 2: GLOBO (interludio) ============ */
  const iluSec = document.querySelector('#interludio');
  const globeCv = document.createElement('canvas');
  globeCv.id = 'globe3d';
  iluSec.insertBefore(globeCv, iluSec.querySelector('.ilu-veil'));
  const yearEl = document.createElement('p');
  yearEl.className = 'globe3d-year';
  yearEl.textContent = 'AÑO 1519 · ZARPA LA ARMADA';
  iluSec.querySelector('.ilu-inner')?.appendChild(yearEl);

  const globeR = rendererEn(globeCv);
  const globeSc = new THREE.Scene();

  function latLon(lat, lon, r) {
    const phi = (90 - lat) * Math.PI / 180, theta = (lon + 180) * Math.PI / 180;
    return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
  }

  // Esfera base oscura (oculta puntos y líneas de la cara trasera)
  const R = 1;
  globeSc.add(new THREE.Mesh(
    new THREE.SphereGeometry(R * 0.995, 48, 32),
    new THREE.MeshBasicMaterial({ color: C.abismo })
  ));

  // Continentes: matriz de puntos dorados (rima con la sección de partículas)
  const texPunto = texturaPunto();
  {
    const n = LAND.length / 2;
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const v = latLon(LAND[i * 2], LAND[i * 2 + 1], R * 1.004);
      pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    globeSc.add(new THREE.Points(g, new THREE.PointsMaterial({
      color: C.goldLight, size: 0.016, map: texPunto, alphaTest: 0.35,
      transparent: true, opacity: 0.85, sizeAttenuation: true, depthWrite: false,
    })));
  }

  // Retícula de carta náutica (paralelos y meridianos cada 15°)
  const grat = new THREE.Group();
  const matGrat = new THREE.LineBasicMaterial({ color: C.gold, transparent: true, opacity: 0.14 });
  for (let lat = -75; lat <= 75; lat += 15) {
    const r = R * Math.cos(lat * Math.PI / 180), y = R * Math.sin(lat * Math.PI / 180);
    const pts = [];
    for (let i = 0; i <= 96; i++) {
      const a = i / 96 * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r));
    }
    grat.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), matGrat));
  }
  for (let lon = 0; lon < 360; lon += 15) {
    const pts = [];
    for (let i = 0; i <= 96; i++) {
      const a = -Math.PI / 2 + i / 96 * Math.PI;
      pts.push(latLon(Math.sin(a) * 90, lon, R));
    }
    grat.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), matGrat));
  }
  globeSc.add(grat);

  // Atmósfera: rim dorado fino por fresnel en la cara trasera de una esfera mayor
  globeSc.add(new THREE.Mesh(
    new THREE.SphereGeometry(R * 1.035, 48, 32),
    new THREE.ShaderMaterial({
      side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `
        varying vec3 vN; varying vec3 vP;
        void main(){
          vN = normalize(normalMatrix * normal);
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vP = mv.xyz;
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        varying vec3 vN; varying vec3 vP;
        void main(){
          float f = pow(clamp(0.6 + dot(normalize(vN), normalize(vP)), 0.0, 1.0), 5.0);
          gl_FragColor = vec4(vec3(0.72, 0.62, 0.40) * f, f * 0.38);
        }`,
    })
  ));

  // Estrellas tenues de fondo
  {
    const n = 480;
    const pos = new Float32Array(n * 3);
    let seed = 7;
    const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < n; i++) {
      const u = rnd() * 2 - 1, a = rnd() * Math.PI * 2;
      const s = Math.sqrt(1 - u * u), r = 15 + rnd() * 6;
      pos[i * 3] = s * Math.cos(a) * r; pos[i * 3 + 1] = u * r; pos[i * 3 + 2] = s * Math.sin(a) * r;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    globeSc.add(new THREE.Points(g, new THREE.PointsMaterial({
      color: C.cream, size: 0.16, map: texPunto, alphaTest: 0.3,
      transparent: true, opacity: 0.5, sizeAttenuation: true, depthWrite: false,
    })));
  }

  // Ruta real de la expedición (1519-1522), hacia el oeste, densificada para
  // que la curva abrace la esfera (sin cuerdas que corten el Pacífico)
  const ETAPAS = [
    [37, -6, 'Sanlúcar'], [28, -16, 'Canarias'], [15, -23, 'Cabo Verde'],
    [5, -28, ''], [-5, -34, ''], [-14, -38, ''], [-23, -43, 'Río'],
    [-30, -50, ''], [-35, -57, ''], [-42, -63, ''], [-49, -68, 'San Julián'],
    [-53, -70, 'El Estrecho'], [-52, -78, ''], [-46, -84, ''], [-40, -90, ''],
    [-33, -100, ''], [-26, -110, ''], [-20, -120, ''], [-14, -132, ''],
    [-8, -145, ''], [-2, -158, ''], [3, -170, ''], [7, 178, ''], [10, 165, ''],
    [12, 155, ''], [13, 145, 'Guam'], [11, 133, ''], [10, 124, 'Mactán'],
    [5, 125, ''], [0, 127, 'Molucas'], [-5, 126, ''], [-9, 125, 'Timor'],
    [-13, 115, ''], [-18, 105, ''], [-23, 97, ''], [-28, 90, ''], [-31, 75, ''],
    [-33, 60, ''], [-34, 45, ''], [-35, 30, ''], [-34, 18, 'Buena Esperanza'],
    [-25, 8, ''], [-15, -5, ''], [-5, -15, ''], [3, -20, ''], [10, -22, ''],
    [20, -20, ''], [28, -15, ''], [33, -10, ''], [37, -6, 'Sanlúcar'],
  ];
  const curva = new THREE.CatmullRomCurve3(ETAPAS.map(e => latLon(e[0], e[1], R * 1.012)), false, 'centripetal');
  const tubo = new THREE.Mesh(
    new THREE.TubeGeometry(curva, 900, 0.0045, 6),
    new THREE.MeshBasicMaterial({ color: C.goldLight })
  );
  tubo.geometry.setDrawRange(0, 0);
  const totalIdx = tubo.geometry.index.count;
  globeSc.add(tubo);

  // Punta luminosa que "navega" + hitos que se encienden al pasar
  const punta = new THREE.Mesh(new THREE.SphereGeometry(0.018, 12, 8),
    new THREE.MeshBasicMaterial({ color: C.cream }));
  globeSc.add(punta);
  const glowPunta = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texturaHalo(), transparent: true, opacity: 0.85, depthWrite: false,
  }));
  glowPunta.scale.setScalar(0.16);
  globeSc.add(glowPunta);
  function uDeEtapa(e) { // posición aproximada del hito a lo largo de la curva
    const i = ETAPAS.indexOf(e);
    return i / (ETAPAS.length - 1);
  }
  const hitos = ETAPAS.filter(e => e[2]).map(e => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.012, 10, 6),
      new THREE.MeshBasicMaterial({ color: C.gold, transparent: true, opacity: 0.35 }));
    m.position.copy(latLon(e[0], e[1], R * 1.012));
    m.userData.u = uDeEtapa(e);
    globeSc.add(m);
    return m;
  });

  // Etiquetas de hito: divs proyectados (se encienden al pasar la punta)
  const tags = ETAPAS.filter(e => e[2]).map((e, i) => {
    // el segundo Sanlúcar (la vuelta) no repite etiqueta
    if (e[2] === 'Sanlúcar' && i > 0 && ETAPAS.indexOf(e) > 10) return null;
    const div = document.createElement('div');
    div.className = 'globe3d-tag';
    div.textContent = e[2];
    iluSec.appendChild(div);
    return { div, pos: latLon(e[0], e[1], R * 1.06), u: uDeEtapa(e) };
  }).filter(Boolean);

  const globeCam = montaCamara(camGlobeG, globeSc);
  globeCam.camera.near = 0.05; globeCam.camera.far = 50;

  const _vCam = new THREE.Vector3(), _vTag = new THREE.Vector3();
  function pintaTags() {
    const cam = globeCam.camera;
    cam.getWorldPosition(_vCam);
    const W = globeCv.clientWidth, H = globeCv.clientHeight;
    const camN = _vCam.clone().normalize();
    for (const tg of tags) {
      const pasado = globeEstado.progreso >= tg.u - 0.004;
      const deCara = tg.pos.clone().normalize().dot(camN) > 0.2;
      if (!pasado || !deCara) { tg.div.style.opacity = '0'; continue; }
      _vTag.copy(tg.pos).project(cam);
      tg.div.style.opacity = '1';
      tg.div.style.left = ((_vTag.x * 0.5 + 0.5) * W).toFixed(1) + 'px';
      tg.div.style.top = ((-_vTag.y * 0.5 + 0.5) * H).toFixed(1) + 'px';
    }
  }

  const globeEstado = { activo: false, progreso: 0 };
  ScrollTrigger.create({
    trigger: '#interludio', start: 'top top', end: '+=280%',
    pin: true, scrub: 1, anticipatePin: 1,
    onUpdate(self) {
      const p = self.progress;
      globeEstado.progreso = p;
      globeCam.setProgress(p);
      tubo.geometry.setDrawRange(0, Math.floor(totalIdx * p));
      punta.position.copy(curva.getPointAt(Math.max(p, 1e-4)));
      glowPunta.position.copy(punta.position);
      hitos.forEach(h => {
        const pasado = p >= h.userData.u;
        h.material.opacity = pasado ? 1 : 0.35;
        h.scale.setScalar(pasado ? 1.6 : 1);
      });
      const year = 1519 + Math.min(3, Math.floor(p * 3.34));
      const fases = ['ZARPA LA ARMADA', 'EL ESTRECHO', 'EL PACÍFICO SIN FIN', 'PRIMUS CIRCUMDEDISTI ME'];
      yearEl.textContent = `AÑO ${year} · ${fases[Math.min(3, Math.floor(p * 4))]}`;
      pintaTags();
    },
    onToggle(self) { globeEstado.activo = self.isActive; },
  });

  /* ============ tamaño, bucle y primer frame ============ */
  function resize() {
    for (const [r, cv, cam] of [[heroR, heroCv, heroCam.camera], [globeR, globeCv, globeCam.camera]]) {
      const w = cv.clientWidth || cv.parentElement.clientWidth;
      const h = cv.clientHeight || cv.parentElement.clientHeight;
      r.setSize(w, h, false);
      cam.aspect = w / h;
      cam.updateProjectionMatrix();
    }
  }
  addEventListener('resize', resize);

  const reloj = new THREE.Clock();
  let tAnt = 0;
  function frame() {
    /* reloj a mitad de velocidad: olas, cabeceo, velas y gaviotas van al 50%
       (todo cuelga de este t, así el shader y la flotación JS siguen en fase) */
    const tRaw = reloj.getElapsedTime();
    const dtR = Math.min(0.05, tRaw - tAnt); tAnt = tRaw;
    const t = tRaw * 0.5;
    uT.value = t;
    if (heroEstado.activo) {
      seaUniforms.uTime.value = t;
      /* el cursor sobre el agua: inercia hacia el objetivo + envejecer ondas */
      const pu = seaUniforms.uPunt.value;
      pu.x += (puntObjetivo.x - pu.x) * 0.12;
      pu.y += (puntObjetivo.y - pu.y) * 0.12;
      pu.z += ((puntDentro ? 1 : 0) - pu.z) * 0.06;
      for (const rip of seaUniforms.uRip.value) rip.z += dtR;
      seaUniforms.uFogDensity.value = heroEstado.fog;
      heroSc.fog.density = heroEstado.fog;
      /* flotación real: la nao muestrea la MISMA ola que pinta el shader.
         Proa/popa en x=±4.6 (mundo = local del plano), bandas en z=±1.5 → y_local=∓1.5 */
      const hC = alturaOla(0, 0, t);
      const hPr = alturaOla(4.6, 0, t), hPp = alturaOla(-4.6, 0, t);
      const hB = alturaOla(0, 1.5, t), hE = alturaOla(0, -1.5, t);
      naoGrupo.position.y = hC * 0.52 + Math.sin(t * 0.8) * 0.03;
      naoGrupo.rotation.z = Math.atan2((hPr - hPp) * 0.52, 9.2);
      naoGrupo.rotation.x = Math.atan2((hB - hE) * 0.40, 3.0);
      // farol de popa
      luzFanal.intensity = heroEstado.farol * 2.6;
      glowFanal.material.opacity = heroEstado.farol * 0.85;
      if (fanalMesh) fanalMesh.material.color.lerpColors(fanalColorBase, fanalColorVivo, heroEstado.farol);
      // gaviotas trazando círculos lentos a popa
      for (const g of gaviotas) {
        g.s.position.set(
          g.cx + Math.cos(t * g.w + g.f) * g.r,
          g.cy + Math.sin(t * 0.6 + g.f) * 0.5,
          g.cz + Math.sin(t * g.w + g.f) * g.r
        );
        g.s.scale.y = 0.75 * (0.7 + 0.3 * Math.sin(t * 6 + g.f * 3)); // aleteo
      }
      heroR.render(heroSc, heroCam.camera);
    }
    if (globeEstado.activo) {
      grat.rotation.y = t * 0.012; // deriva sutil de la retícula
      globeR.render(globeSc, globeCam.camera);
    }
    requestAnimationFrame(frame);
  }

  resize();
  heroCam.setProgress(0);
  globeCam.setProgress(0);
  heroR.render(heroSc, heroCam.camera);
  globeR.render(globeSc, globeCam.camera);
  frame();
  ScrollTrigger.refresh();
  window.__p3dReady = true;

  // utilidades de test headless: ?s=0.4 scrollea a esa fracción del documento;
  // ?p=0.6 fija el progreso de ambas escenas y re-renderiza (el rAF headless no avanza)
  const dbg = new URLSearchParams(location.search);
  const s = dbg.get('s');
  if (s !== null) setTimeout(() => {
    window.scrollTo({
      top: parseFloat(s) * (document.documentElement.scrollHeight - innerHeight),
      behavior: 'instant',
    });
  }, 600);
  const go = dbg.get('go');
  if (go) setTimeout(() => {
    const el = document.querySelector('#' + go);
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY;
    const f = parseFloat(dbg.get('f') || '0');
    window.scrollTo({ top: top + f * innerHeight * 2.8, behavior: 'instant' });
    // headless: el rAF está parado, así que bombeamos el ticker de GSAP a mano
    setTimeout(() => {
      ScrollTrigger.update();
      for (let i = 0; i < 240; i++) gsap.ticker.tick();
      ScrollTrigger.update();
    }, 150);
  }, 700);
  const p = dbg.get('p');
  if (p !== null) setTimeout(() => {
    const v = parseFloat(p);
    const tDbg = 4.2;
    uT.value = tDbg;
    heroCam.setProgress(v);
    heroEstado.fog = 0.085 - 0.063 * v; // que el bucle rAF no lo pise
    heroEstado.farol = THREE.MathUtils.smoothstep(v, 0.62, 0.9);
    heroSc.fog.density = seaUniforms.uFogDensity.value = heroEstado.fog;
    seaUniforms.uTime.value = tDbg;
    naoGrupo.position.y = alturaOla(0, 0, tDbg) * 0.52;
    luzFanal.intensity = heroEstado.farol * 2.6;
    glowFanal.material.opacity = heroEstado.farol * 0.85;
    heroR.render(heroSc, heroCam.camera);
    globeCam.setProgress(v);
    globeEstado.progreso = v;
    tubo.geometry.setDrawRange(0, Math.floor(totalIdx * v));
    punta.position.copy(curva.getPointAt(Math.max(v, 1e-4)));
    glowPunta.position.copy(punta.position);
    hitos.forEach(h => {
      h.material.opacity = v >= h.userData.u ? 1 : 0.35;
      h.scale.setScalar(v >= h.userData.u ? 1.6 : 1);
    });
    pintaTags();
    globeR.render(globeSc, globeCam.camera);
    // ?solo=globe|hero: canvas a pantalla completa por encima de todo (validación visual)
    const solo = dbg.get('solo');
    if (solo) {
      const cv = solo === 'globe' ? globeCv : heroCv;
      document.body.appendChild(cv); // fuera de la sección: su transform atrapa el fixed
      heroEstado.activo = solo === 'hero';
      globeEstado.activo = solo === 'globe'; // el bucle rAF presenta el frame al compositor
      cv.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;z-index:9999;'
        + (solo === 'globe' ? 'background:#101c3c;' : 'background:#f4efe2;');
      cv.style.maskImage = 'none';
      cv.style.webkitMaskImage = 'none';
      resize();
      heroR.render(heroSc, heroCam.camera);
      globeR.render(globeSc, globeCam.camera);
      const wp = (solo === 'globe' ? globeCam : heroCam).camera.getWorldPosition(new THREE.Vector3());
      const inf = (solo === 'globe' ? globeR : heroR).info.render;
      document.title = `SOLO cam:[${wp.toArray().map(v2 => v2.toFixed(2)).join(',')}]`
        + ` tris:${inf.triangles} lines:${inf.lines} cv:${cv.width}x${cv.height}`;
    }
    window.__p3dDebugDone = true;
    if (!solo) document.title = `P3D ready:${!!window.__p3dReady} errs:[${window.__p3dErrors.join(' | ').slice(0, 300)}]`;
  }, 900);
}

// Arranque (al final del módulo: todas las const ya están inicializadas)
if (reduce || movil || !gl2 || !window.gsap) {
  window.__p3dSkip = true;
} else {
  init().catch(e => { window.__p3dErrors.push('init: ' + (e?.message || e)); });
}
