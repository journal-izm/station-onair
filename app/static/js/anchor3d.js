// 3D AI 앵커 — 원본 캐릭터 (실존 인물·작품과 관계없음). 외부 라이브러리 없이 WebGL로 직접 그림.
// 구, 원기둥, 상자, 고리 같은 기본 도형을 조합해 얼굴과 몸을 만들고,
// TTS 소리 크기에 맞춰 입을 벌리고, 눈을 깜빡이고, 고개를 살짝 움직임.
// 사용법은 Anchor2D와 같음: Anchor3D.mount(el, {station, code}) → 클릭 뒤 attachAudio(audio) / setSpeaking(true|false)
// mount가 false를 돌려주면 (WebGL을 못 쓰는 PC) 2D 앵커로 바꿔 쓰면 됨.
const Anchor3D = (() => {
  // ── 방송국별 모습 ───────────────────────────────────────────────
  const THEMES = {
    M: { bg: ['#6E93D6', '#4466A6', '#2A3F72'], suit: '#26365A', shirt: '#EEF2F8', hair: '#3B2D5C', tie: '#00E5FF', pin: '#A6FF00',
         iris: '#3A2A6A', arc1: '#00E5FF', arc2: '#FF2BD6', rim: '#9FEFFF', longHair: true, glasses: false },
    K: { bg: ['#8A5BC4', '#55367F', '#2A1A45'], suit: '#52263D', shirt: '#F4EEF2', hair: '#1F1A1A', tie: '#FF2BD6', pin: '#00E5FF',
         iris: '#5A3A1A', arc1: '#FFB800', arc2: '#00FFA3', rim: '#FFC6F2', longHair: false, glasses: true },
  };
  const SKIN = '#F2C9A8', SKIN2 = '#E3B190', LIP = '#C8506A', MOUTH = '#4A1424', BLUSH = '#F5A3A3';

  // ── 행렬 계산 (4x4, 열 우선) ─────────────────────────────────────
  const I = () => { const m = new Float32Array(16); m[0] = m[5] = m[10] = m[15] = 1; return m; };
  const mul = (a, b) => { const o = new Float32Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += a[r + k * 4] * b[k + c * 4]; o[r + c * 4] = s; }
    return o; };
  const T = (x, y, z) => { const m = I(); m[12] = x; m[13] = y; m[14] = z; return m; };
  const S = (x, y, z) => { const m = I(); m[0] = x; m[5] = y; m[10] = z; return m; };
  const Rx = a => { const m = I(), c = Math.cos(a), s = Math.sin(a); m[5] = c; m[6] = s; m[9] = -s; m[10] = c; return m; };
  const Ry = a => { const m = I(), c = Math.cos(a), s = Math.sin(a); m[0] = c; m[2] = -s; m[8] = s; m[10] = c; return m; };
  const Rz = a => { const m = I(), c = Math.cos(a), s = Math.sin(a); m[0] = c; m[1] = s; m[4] = -s; m[5] = c; return m; };
  const chain = (...ms) => ms.reduce((a, b) => mul(a, b));
  function persp(fovy, asp, n, f) { const t = 1 / Math.tan(fovy / 2), m = new Float32Array(16);
    m[0] = t / asp; m[5] = t; m[10] = (f + n) / (n - f); m[11] = -1; m[14] = 2 * f * n / (n - f); return m; }
  function lookAt(e, c, u) {
    const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
    const nor = v => { const l = Math.hypot(...v); return v.map(x => x / l); };
    const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    const z = nor(sub(e, c)), x = nor(cr(u, z)), y = cr(z, x), m = I();
    m[0] = x[0]; m[4] = x[1]; m[8] = x[2]; m[1] = y[0]; m[5] = y[1]; m[9] = y[2]; m[2] = z[0]; m[6] = z[1]; m[10] = z[2];
    m[12] = -dot(x, e); m[13] = -dot(y, e); m[14] = -dot(z, e); return m;
  }
  function normalMat(m) {                     // 늘이고 줄인 도형의 빛 방향을 바로잡는 행렬 (역행렬의 전치)
    const A = (r, c) => m[c * 4 + r], o = new Float32Array(9);
    const cof = (r, c) => { const rr = [0, 1, 2].filter(i => i !== r), cc = [0, 1, 2].filter(i => i !== c);
      const d = A(rr[0], cc[0]) * A(rr[1], cc[1]) - A(rr[0], cc[1]) * A(rr[1], cc[0]); return ((r + c) % 2 ? -1 : 1) * d; };
    let det = 0; for (let c = 0; c < 3; c++) det += A(0, c) * cof(0, c);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) o[c * 3 + r] = cof(r, c) / det;
    return o;
  }
  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255);

  // ── 기본 도형 ────────────────────────────────────────────────────
  function sphere(nLat = 28, nLon = 36) { const p = [], n = [], idx = [];
    for (let i = 0; i <= nLat; i++) for (let j = 0; j <= nLon; j++) {
      const th = i / nLat * Math.PI, ph = j / nLon * 2 * Math.PI;
      const v = [Math.sin(th) * Math.cos(ph), Math.cos(th), Math.sin(th) * Math.sin(ph)]; p.push(...v); n.push(...v); }
    for (let i = 0; i < nLat; i++) for (let j = 0; j < nLon; j++) { const a = i * (nLon + 1) + j, b = a + nLon + 1; idx.push(a, b, a + 1, b, b + 1, a + 1); }
    return { p, n, idx }; }
  function cylinder(seg = 32) { const p = [], n = [], idx = [];
    for (let j = 0; j <= seg; j++) { const a = j / seg * 2 * Math.PI, x = Math.cos(a), z = Math.sin(a);
      p.push(x, -0.5, z, x, 0.5, z); n.push(x, 0, z, x, 0, z); }
    for (let j = 0; j < seg; j++) { const a = j * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    return { p, n, idx }; }
  function box() { const p = [], n = [], idx = [];
    const F = [[[1, 0, 0], [0, 1, 0], [0, 0, 1]], [[-1, 0, 0], [0, 1, 0], [0, 0, -1]], [[0, 1, 0], [0, 0, 1], [1, 0, 0]],
               [[0, -1, 0], [0, 0, -1], [1, 0, 0]], [[0, 0, 1], [1, 0, 0], [0, 1, 0]], [[0, 0, -1], [-1, 0, 0], [0, 1, 0]]];
    F.forEach(([nn, u, v], f) => { [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([a, b]) => {
        p.push(...[0, 1, 2].map(k => (nn[k] + u[k] * a + v[k] * b) * 0.5)); n.push(...nn); });
      const o = f * 4; idx.push(o, o + 1, o + 2, o, o + 2, o + 3); });
    return { p, n, idx }; }
  function torus(r = 0.12, nu = 40, nv = 14) { const p = [], n = [], idx = [];
    for (let i = 0; i <= nu; i++) for (let j = 0; j <= nv; j++) {
      const u = i / nu * 2 * Math.PI, v = j / nv * 2 * Math.PI;
      const nn = [Math.cos(v) * Math.cos(u), Math.cos(v) * Math.sin(u), Math.sin(v)];
      p.push(Math.cos(u) + r * nn[0], Math.sin(u) + r * nn[1], r * nn[2]); n.push(...nn); }
    for (let i = 0; i < nu; i++) for (let j = 0; j < nv; j++) { const a = i * (nv + 1) + j, b = a + nv + 1; idx.push(a, b, a + 1, b, b + 1, a + 1); }
    return { p, n, idx }; }

  // ── 배경 (별·네온 곡선)과 이름표는 HTML/SVG로 ─────────────────────
  const BG = T_ => `<svg viewBox="0 0 820 820" preserveAspectRatio="xMidYMid slice" style="position:absolute;inset:0;width:100%;height:100%">
    <defs><radialGradient id="a3bg" cx="50%" cy="38%" r="70%"><stop offset="0" stop-color="${T_.bg[0]}"/><stop offset=".55" stop-color="${T_.bg[1]}"/><stop offset="1" stop-color="${T_.bg[2]}"/></radialGradient>
    <filter id="a3g"><feGaussianBlur stdDeviation="6"/></filter></defs>
    <rect width="820" height="820" fill="url(#a3bg)"/>
    <g opacity=".55">${Array.from({ length: 40 }, (_, i) => `<circle cx="${(i * 383 + 57) % 820}" cy="${(i * i * 37 + i * 91) % 470}" r="${i % 3 ? 1.6 : 2.6}" fill="#E4ECFF"/>`).join('')}</g>
    <path d="M60 540 Q410 270 760 540" fill="none" stroke="${T_.arc1}" stroke-width="5" opacity=".5" filter="url(#a3g)"/>
    <path d="M100 580 Q410 350 720 580" fill="none" stroke="${T_.arc2}" stroke-width="4" opacity=".45" filter="url(#a3g)"/></svg>`;
  const PLATE = (st, T_) => `<div style="position:absolute;left:10%;right:10%;bottom:0;height:10%;border-radius:10px;background:#0E1527;border:3px solid ${T_.arc1 === '#00E5FF' ? '#00E5FF' : '#00E5FF'};
    box-shadow:0 0 18px #00E5FF88;display:flex;align-items:center;justify-content:center;color:#F2F5FA;font-weight:800;font-size:clamp(14px,3.2vmin,34px);font-family:'Noto Sans KR',sans-serif">${st} · AI 앵커</div>`;

  // ── 상태 ─────────────────────────────────────────────────────────
  let gl, prog, loc = {}, meshes = {}, canvas, theme;
  let ctx = null, analyser = null, buf = null, audioRef = null, analyserWorks = false, synthSpeaking = false, open = 0, nextBlink = 2500, blinkT = -9999;

  function compile(vs, fs) {
    const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o);
      if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; };
    const p = gl.createProgram(); gl.attachShader(p, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p)); return p;
  }
  function upload(g) {
    const b = k => { const o = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, o); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(g[k]), gl.STATIC_DRAW); return o; };
    const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(g.idx), gl.STATIC_DRAW);
    return { p: b('p'), n: b('n'), ib, count: g.idx.length };
  }

  const VS = `attribute vec3 aP; attribute vec3 aN; uniform mat4 uM, uVP; uniform mat3 uN; varying vec3 vN, vW;
    void main(){ vec4 w = uM * vec4(aP, 1.0); vW = w.xyz; vN = normalize(uN * aN); gl_Position = uVP * w; }`;
  const FS = `precision mediump float; varying vec3 vN, vW; uniform vec3 uC, uCam, uRim; uniform float uE;
    void main(){ vec3 n = normalize(vN); vec3 l = normalize(vec3(0.45, 0.6, 1.0));
      float d = dot(n, l) * 0.5 + 0.5; d = d * d;                         // 부드러운 그림자
      float fill = max(dot(n, normalize(vec3(-0.6, 0.2, 0.6))), 0.0) * 0.15;
      vec3 v = normalize(uCam - vW); float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0);   // 테두리 빛 (네온 느낌)
      vec3 col = uC * (0.38 + 0.72 * d + fill) + uRim * rim * 0.45;
      col = mix(col, uC * 1.5 + 0.15, uE);                                 // 빛나는 부품 (넥타이·이어피스)
      gl_FragColor = vec4(col, 1.0); }`;

  function mount(el, opt = {}) {
    theme = THEMES[opt.code] || THEMES.M;
    el.innerHTML = BG(theme) + '<canvas style="position:absolute;inset:0;width:100%;height:100%"></canvas>' + PLATE(opt.station || '방송국', theme);
    canvas = el.querySelector('canvas');
    gl = canvas.getContext('webgl', { antialias: true, alpha: true, premultipliedAlpha: false });
    if (!gl) { el.innerHTML = ''; return false; }
    try { prog = compile(VS, FS); } catch (e) { console.warn('3D 앵커 준비 실패', e); el.innerHTML = ''; return false; }
    gl.useProgram(prog);
    ['aP', 'aN'].forEach(k => loc[k] = gl.getAttribLocation(prog, k));
    ['uM', 'uVP', 'uN', 'uC', 'uCam', 'uRim', 'uE'].forEach(k => loc[k] = gl.getUniformLocation(prog, k));
    meshes = { sph: upload(sphere()), cyl: upload(cylinder()), box: upload(box()), tor: upload(torus()) };
    gl.enable(gl.DEPTH_TEST);
    requestAnimationFrame(tick);
    return true;
  }

  function draw(mesh, M, color, emit = 0) {
    const m = meshes[mesh];
    gl.bindBuffer(gl.ARRAY_BUFFER, m.p); gl.enableVertexAttribArray(loc.aP); gl.vertexAttribPointer(loc.aP, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, m.n); gl.enableVertexAttribArray(loc.aN); gl.vertexAttribPointer(loc.aN, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, m.ib);
    gl.uniformMatrix4fv(loc.uM, false, M); gl.uniformMatrix3fv(loc.uN, false, normalMat(M));
    gl.uniform3fv(loc.uC, hex(color)); gl.uniform1f(loc.uE, emit);
    gl.drawElements(gl.TRIANGLES, m.count, gl.UNSIGNED_SHORT, 0);
  }
  // 부품 하나 = 위치(x,y,z) · 크기(sx,sy,sz) · 회전(rx,ry,rz)
  const part = (G, mesh, [x, y, z], [sx, sy, sz], color, emit = 0, [rx, ry, rz] = [0, 0, 0]) =>
    draw(mesh, chain(G, T(x, y, z), Rz(rz), Ry(ry), Rx(rx), S(sx, sy, sz)), color, emit);

  // ── 소리 → 입 크기 (Anchor2D와 같은 방식) ─────────────────────────
  function attachAudio(audioEl) {
    audioRef = audioEl;                       // 소리 분석이 안 되는 환경(OBS 등)에서도 '재생 중'이면 입을 움직이기 위해 기억
    audioEl.addEventListener('play', () => { if (ctx && ctx.state === 'suspended') ctx.resume().catch(() => {}); });
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      const src = ctx.createMediaElementSource(audioEl);
      analyser = ctx.createAnalyser(); analyser.fftSize = 1024; buf = new Uint8Array(analyser.fftSize);
      src.connect(analyser); analyser.connect(ctx.destination);
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      console.info('[앵커] 소리 분석 연결됨, 상태:', ctx.state);
    } catch (e) { console.warn('입 모양 연결 실패 — 소리는 그대로 나감', e); }
  }
  function setSpeaking(v) { synthSpeaking = v; }
  function level() {
    if (analyser) { analyser.getByteTimeDomainData(buf);
      let s = 0; for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; s += v * v; }
      const rms = Math.sqrt(s / buf.length); if (rms > 0.012) { analyserWorks = true; return Math.min(1, Math.sqrt(rms) * 2.4); } }   // 작은 소리에도 입이 잘 벌어지게
    const playing = !analyserWorks && audioRef && !audioRef.paused && !audioRef.ended && audioRef.currentTime > 0;   // 소리 분석이 안 될 때(OBS 등)는 재생 중이면 흉내
    if (synthSpeaking || playing) { const t = performance.now() / 1000;
      return Math.max(0, 0.45 + 0.35 * Math.sin(t * 13) + 0.2 * Math.sin(t * 7.3) - (Math.random() < 0.08 ? 0.6 : 0)); }
    return 0;
  }

  // ── 매 프레임 그리기 ─────────────────────────────────────────────
  function tick(now) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2), w = canvas.clientWidth * dpr | 0, h = canvas.clientHeight * dpr | 0;
    if (w && h && (canvas.width !== w || canvas.height !== h)) { canvas.width = w; canvas.height = h; }
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    const target = level(); open += (target - open) * (target > open ? 0.6 : 0.25);
    const o = Math.max(0, Math.min(1, open)), t = now / 1000;
    if (now > nextBlink) { blinkT = now; nextBlink = now + 3000 + Math.random() * 3000; }
    const blink = now - blinkT < 150 ? 1 : 0;

    const cam = [0, 0.1, 9.6];
    gl.uniformMatrix4fv(loc.uVP, false, mul(persp(30 * Math.PI / 180, canvas.width / Math.max(1, canvas.height), 0.1, 50), lookAt(cam, [0, -0.6, 0], [0, 1, 0])));
    gl.uniform3fv(loc.uCam, cam); gl.uniform3fv(loc.uRim, hex(theme.rim));

    const breath = Math.sin(t * 1.6) * 0.03;
    const B = T(0, breath * 0.6, 0);                                     // 몸 (숨쉬기)
    const yaw = Math.sin(t * 0.7) * 0.12 + Math.sin(t * 1.9) * 0.03;
    const pitch = Math.sin(t * 1.1) * 0.03 + o * 0.05 * Math.sin(t * 6);
    const roll = Math.sin(t * 0.9) * 0.03;
    const H = chain(T(0, 0.3 + breath, 0), T(0, -0.9, 0), Ry(yaw), Rx(pitch), Rz(roll), T(0, 0.9, 0));   // 머리 (목을 축으로)
    const tm = theme;

    // 몸
    part(B, 'sph', [0, -2.65, 0], [2.0, 1.5, 1.0], tm.suit);
    part(B, 'sph', [0, -1.75, 0.8], [0.42, 0.7, 0.2], tm.shirt);                            // 셔츠
    for (const sx of [-1, 1]) part(B, 'box', [0.31 * sx, -1.95, 0.97], [0.32, 1.15, 0.05], tm.suit, 0, [0, 0.3 * sx, -0.35 * sx]);   // 옷깃
    part(B, 'cyl', [0, -0.85, 0], [0.36, 0.9, 0.36], SKIN2);
    if (tm.longHair) part(B, 'box', [0, -1.85, 1.0], [0.14, 0.55, 0.04], tm.tie, 0.55);
    else { part(B, 'tor', [0, -1.25, 0.05], [0.5, 0.42, 0.5], tm.tie, 0.5, [Math.PI / 2, 0, 0]);    // 스카프
           part(B, 'sph', [0, -1.45, 0.62], [0.2, 0.16, 0.12], tm.tie, 0.5); }
    part(B, 'sph', [0.78, -1.9, 0.8], [0.07, 0.07, 0.05], tm.pin, 0.9);

    // 머리
    part(H, 'sph', [0, 0, 0], [0.95, 1.15, 1.0], SKIN);
    part(H, 'sph', [0.93, 0, 0], [0.14, 0.25, 0.12], SKIN); part(H, 'sph', [-0.93, 0, 0], [0.14, 0.25, 0.12], SKIN);
    part(H, 'sph', [0.99, -0.06, 0.1], [0.07, 0.07, 0.07], tm.tie, 0.9);                    // 이어피스
    if (tm.longHair) {
      part(H, 'sph', [0, 0.12, -0.12], [1.05, 1.2, 1.05], tm.hair);
      part(H, 'sph', [0.2, 0.84, 0.45], [0.7, 0.24, 0.38], tm.hair, 0, [0, 0, -0.3]);         // 앞머리
      part(H, 'sph', [0.92, -0.4, -0.05], [0.28, 0.95, 0.45], tm.hair);                        // 옆머리
      part(H, 'sph', [-0.92, -0.4, -0.05], [0.28, 0.95, 0.45], tm.hair);
    } else {
      part(H, 'sph', [0, 0.25, -0.08], [1.0, 1.0, 1.03], tm.hair);
      part(H, 'sph', [-0.22, 0.9, 0.38], [0.7, 0.24, 0.42], tm.hair, 0, [0, 0, 0.2]);         // 옆 가르마
    }
    for (const sx of [-1, 1]) {
      const ex = 0.33 * sx;
      part(H, 'sph', [ex, 0.12, 0.9], [0.2, 0.14, 0.08], '#FFFFFF');                           // 흰자
      part(H, 'sph', [ex + yaw * 0.05, 0.11, 0.97], [0.09, 0.09, 0.05], tm.iris);               // 눈동자
      part(H, 'sph', [ex - 0.03, 0.15, 1.01], [0.03, 0.03, 0.02], '#FFFFFF', 1);               // 반짝임
      if (blink) part(H, 'sph', [ex, 0.12, 0.91], [0.22, 0.16, 0.13], SKIN);                    // 눈꺼풀
      part(H, 'box', [ex, 0.36 + o * 0.03, 0.93], [0.24, 0.045, 0.05], tm.hair, 0, [0, 0, -0.12 * sx]);   // 눈썹
      part(H, 'sph', [0.5 * sx, -0.18, 0.82], [0.14, 0.07, 0.03], BLUSH);                      // 볼
      if (tm.glasses) part(H, 'tor', [ex, 0.12, 1.03], [0.24, 0.19, 0.24], '#FFB800', 0.45);   // 안경테
    }
    if (tm.glasses) part(H, 'box', [0, 0.16, 1.04], [0.18, 0.03, 0.03], '#FFB800', 0.45);
    part(H, 'sph', [0, -0.12, 0.98], [0.08, 0.14, 0.1], SKIN2);                                 // 코
    part(H, 'sph', [0, -0.47, 0.87], [0.2 - o * 0.04, 0.04 + o * 0.15, 0.06], LIP);              // 입술
    if (o > 0.05) part(H, 'sph', [0, -0.47, 0.885], [0.15 - o * 0.02, 0.12 * o, 0.065], MOUTH);            // 입 안
    if (o > 0.35) part(H, 'box', [0, -0.47 + 0.085 * o, 0.94], [0.13, 0.025, 0.02], '#FFFFFF'); // 윗니

    requestAnimationFrame(tick);
  }
  return { mount, attachAudio, setSpeaking };
})();
