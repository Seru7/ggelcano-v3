/* Estela fluida del cursor — la MISMA receta que la demo
   bttestudio-arquitectura-valencia-v2-premium (webgl-fluid-enhanced, MIT,
   técnica Noomo del informe 05), adaptada a la paleta G&G Elcano:
   azul tinta + azul suave + latón en lugar de los azules acero.
   Canvas con pointer-events:none → hover off + splat() manual desde window
   con impulso proporcional a la velocidad del ratón. Si el CDN falla, la
   estela 2D antigua de burbujas sigue de fallback (gating GG_FLUID). */

const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

if (window.GG_FLUID && !reduce) {
  import('https://cdn.jsdelivr.net/npm/webgl-fluid-enhanced@0.8.0/+esm').then((mod) => {
    const WebGLFluidEnhanced = mod.default;
    const cont = document.createElement('div');
    cont.id = 'fluid';
    cont.setAttribute('aria-hidden', 'true');
    document.body.appendChild(cont);
    const sim = new WebGLFluidEnhanced(cont);
    /* la lib pisa el position del contenedor: lo re-fijamos a viewport */
    Object.assign(cont.style, {
      position: 'fixed', inset: '0', width: '100%', height: '100%',
      zIndex: '499', pointerEvents: 'none',
    });
    dispatchEvent(new Event('resize'));            /* que el canvas adopte el viewport */
    sim.setConfig({
      simResolution: 128,
      dyeResolution: 1024,
      densityDissipation: 2.2,         /* la tinta vive más sin hacerse "sopa" */
      velocityDissipation: 1.4,
      pressureIterations: 10,
      curl: 28,                        /* remolinos bien visibles */
      splatRadius: 0.1,
      splatForce: 5000,
      hover: false,                    /* listener propio: el canvas no recibe eventos */
      colorful: false,                 /* nada de arcoíris */
      colorPalette: ['#223f83', '#3a5aa8', '#b08d57'],  /* tinta, azul suave, latón */
      transparent: true,
      bloom: false,                    /* el bloom de v0.8 rompe la transparencia */
      sunrays: false,
    });
    sim.start();
    window.__fluidOn = true;

    /* splat manual con impulso proporcional a la velocidad del gesto */
    let lastX = null, lastY = null;
    addEventListener('pointermove', (e) => {
      if (lastX !== null) {
        const dx = (e.clientX - lastX) * 2.5;
        const dy = (e.clientY - lastY) * 2.5;
        if (Math.abs(dx) + Math.abs(dy) > 4)
          sim.splatAtLocation(e.clientX, e.clientY, dx, dy);
      }
      lastX = e.clientX; lastY = e.clientY;
    }, { passive: true });

    /* ráfaga de bienvenida: una ola de tinta cruza la pantalla tras la intro */
    setTimeout(() => {
      const W = innerWidth, H = innerHeight;
      for (let i = 0; i <= 5; i++) {
        const t = i / 5;
        setTimeout(() => {
          sim.splatAtLocation(W * (0.15 + t * 0.7), H * (0.6 - Math.sin(t * Math.PI) * 0.22),
                              180 * (1 - t * 0.4), -70 * Math.cos(t * Math.PI));
        }, i * 70);
      }
    }, 1900);

    /* GPU en pausa con la pestaña oculta */
    document.addEventListener('visibilitychange', () => {
      sim.pause();                     /* toggle: oculta=pausa, visible=reanuda */
    });
  }).catch(() => { window.__fluidOn = false; });
} else {
  window.__fluidOn = false;
}
