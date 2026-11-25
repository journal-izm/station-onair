// 2D AI 앵커 — 원본 캐릭터 (실존 인물·작품과 관계없음). TTS 소리 크기에 맞춰 입이 움직이고, 눈을 깜빡이고, 숨 쉬듯 움직임.
// 사용: Anchor2D.mount(element, {station:'M 방송국'}) → Anchor2D.attachAudio(audioEl) (클릭 뒤) → 말하는 동안 자동으로 입 움직임
//       브라우저 음성(speechSynthesis)일 때는 Anchor2D.setSpeaking(true/false)로 흉내.
const Anchor2D = (() => {
  let root, mouthOuter, mouthInner, teeth, lidsL, lidsR, browL, browR, headG, bodyG;
  let ctx = null, analyser = null, buf = null, synthSpeaking = false, open = 0, nextBlink = 2500, blinkT = -9999;
  // 방송국별 앵커 (둘 다 원본 캐릭터). M: 남색 배경·긴 머리·시안 넥타이 / K: 보라 배경·짧은 머리·안경·마젠타 스카프
  const THEMES = {
    M: { bg: ['#6E93D6', '#4466A6', '#2A3F72'], suit: ['#22324F', '#121C30'], hair: ['#3B2D5C', '#1E1733'], tie: '#00E5FF', pin: '#A6FF00',
         arc1: '#00E5FF', arc2: '#FF2BD6', iris: '#3A2A6A', longHair: true, glasses: false },
    K: { bg: ['#8A5BC4', '#55367F', '#2A1A45'], suit: ['#4A2338', '#2A1220'], hair: ['#1F1A1A', '#0D0A0A'], tie: '#FF2BD6', pin: '#00E5FF',
         arc1: '#FFB800', arc2: '#00FFA3', iris: '#5A3A1A', longHair: false, glasses: true },
  };
  const SVG = (station, T) => `
<svg viewBox="0 0 820 820" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;display:block">
  <defs>
    <radialGradient id="a2bg" cx="50%" cy="38%" r="70%"><stop offset="0" stop-color="${T.bg[0]}"/><stop offset=".55" stop-color="${T.bg[1]}"/><stop offset="1" stop-color="${T.bg[2]}"/></radialGradient>
    <linearGradient id="a2suit" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${T.suit[0]}"/><stop offset="1" stop-color="${T.suit[1]}"/></linearGradient>
    <linearGradient id="a2hair" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${T.hair[0]}"/><stop offset="1" stop-color="${T.hair[1]}"/></linearGradient>
    <filter id="a2glow"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <rect width="820" height="820" fill="url(#a2bg)"/>
  <g opacity=".55">${Array.from({length: 40}, (_, i) => `<circle cx="${(i * 383 + 57) % 820}" cy="${(i * i * 37 + i * 91) % 470}" r="${i % 3 ? 1.6 : 2.6}" fill="#C9D6FF"/>`).join('')}</g>
  <path d="M60 520 Q410 250 760 520" fill="none" stroke="${T.arc1}" stroke-width="4" opacity=".35" filter="url(#a2glow)"/>
  <path d="M100 560 Q410 330 720 560" fill="none" stroke="${T.arc2}" stroke-width="3" opacity=".3" filter="url(#a2glow)"/>
  <g id="a2body">
    <path d="M150 820 Q160 600 300 565 L520 565 Q660 600 670 820 Z" fill="url(#a2suit)"/>
    <path d="M345 565 L410 690 L475 565 Z" fill="#EEF2F8"/>
    ${T.longHair ? `<path d="M398 600 L422 600 L432 700 L410 730 L388 700 Z" fill="${T.tie}" filter="url(#a2glow)"/>`
      : `<path d="M352 575 Q410 640 468 575 L455 610 Q410 665 365 610 Z" fill="${T.tie}" filter="url(#a2glow)"/><circle cx="410" cy="628" r="10" fill="${T.tie}"/>`}
    <path d="M300 565 L410 720 L330 820 L230 640 Z" fill="${T.suit[1]}"/><path d="M520 565 L410 720 L490 820 L590 640 Z" fill="${T.suit[1]}"/>
    <circle cx="545" cy="660" r="9" fill="${T.pin}" filter="url(#a2glow)"/>
    <rect x="370" y="500" width="80" height="80" rx="20" fill="#E7B896"/>
  </g>
  <g id="a2head">
    ${T.longHair ? '<ellipse cx="410" cy="330" rx="150" ry="170" fill="url(#a2hair)"/>' : '<ellipse cx="410" cy="290" rx="138" ry="140" fill="url(#a2hair)"/>'}
    <ellipse cx="282" cy="345" rx="20" ry="30" fill="#E7B896"/><ellipse cx="538" cy="345" rx="20" ry="30" fill="#E7B896"/>
    <circle cx="540" cy="352" r="7" fill="${T.tie}" filter="url(#a2glow)"/>
    <ellipse cx="410" cy="345" rx="125" ry="150" fill="#F2C9A8"/>
    ${T.longHair
      ? `<path d="M285 300 Q300 175 410 168 Q530 172 540 300 Q500 230 430 222 Q350 220 285 300 Z" fill="url(#a2hair)"/>
    <path d="M268 300 Q262 430 300 470 L292 330 Z" fill="url(#a2hair)"/><path d="M552 300 Q558 430 520 470 L528 330 Z" fill="url(#a2hair)"/>`
      : `<path d="M282 320 Q280 170 420 165 Q545 175 540 320 Q530 255 470 240 Q440 200 380 236 Q320 250 282 320 Z" fill="url(#a2hair)"/>`}
    <path id="a2browL" d="M330 290 Q360 276 390 288" stroke="#2A1F3D" stroke-width="9" fill="none" stroke-linecap="round"/>
    <path id="a2browR" d="M430 288 Q460 276 490 290" stroke="#2A1F3D" stroke-width="9" fill="none" stroke-linecap="round"/>
    <g><ellipse cx="360" cy="330" rx="26" ry="18" fill="#fff"/><circle cx="362" cy="331" r="12" fill="${T.iris}"/><circle cx="366" cy="326" r="4" fill="#fff"/>
       <rect id="a2lidL" x="330" y="308" width="60" height="0" fill="#F2C9A8"/></g>
    <g><ellipse cx="460" cy="330" rx="26" ry="18" fill="#fff"/><circle cx="462" cy="331" r="12" fill="${T.iris}"/><circle cx="466" cy="326" r="4" fill="#fff"/>
       <rect id="a2lidR" x="430" y="308" width="60" height="0" fill="#F2C9A8"/></g>
    ${T.glasses ? `<g fill="none" stroke="#FFB800" stroke-width="5" opacity=".95"><rect x="322" y="304" width="78" height="54" rx="20"/><rect x="422" y="304" width="78" height="54" rx="20"/><path d="M400 326 Q411 318 422 326"/><path d="M322 320 L290 312"/><path d="M500 320 L532 312"/></g>` : ''}
    <path d="M410 345 Q400 385 412 392" stroke="#D49C7E" stroke-width="5" fill="none" stroke-linecap="round"/>
    <ellipse cx="330" cy="395" rx="22" ry="12" fill="#F5A3A3" opacity=".35"/><ellipse cx="490" cy="395" rx="22" ry="12" fill="#F5A3A3" opacity=".35"/>
    <ellipse id="a2mouthO" cx="410" cy="430" rx="30" ry="4" fill="#C8506A"/>
    <ellipse id="a2mouthI" cx="410" cy="432" rx="22" ry="0" fill="#4A1424"/>
    <rect id="a2teeth" x="394" y="424" width="32" height="0" rx="3" fill="#FFF"/>
  </g>
  <rect x="80" y="740" width="660" height="80" rx="10" fill="#0E1527" stroke="#00E5FF" stroke-width="3" filter="url(#a2glow)"/>
  <text x="410" y="792" text-anchor="middle" font-size="34" font-weight="800" fill="#F2F5FA" font-family="Noto Sans KR, sans-serif">${station} · AI 앵커</text>
</svg>`;

  function mount(el, opt = {}) {
    el.innerHTML = SVG(opt.station || '방송국', THEMES[opt.code] || THEMES.M);
    root = el;
    const q = id => el.querySelector('#' + id);
    mouthOuter = q('a2mouthO'); mouthInner = q('a2mouthI'); teeth = q('a2teeth');
    lidsL = q('a2lidL'); lidsR = q('a2lidR'); browL = q('a2browL'); browR = q('a2browR');
    headG = q('a2head'); bodyG = q('a2body');
    requestAnimationFrame(tick);
  }
  function attachAudio(audioEl) {           // 화면을 한 번 클릭한 뒤 불러야 함 (브라우저 소리 정책)
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      const src = ctx.createMediaElementSource(audioEl);
      analyser = ctx.createAnalyser(); analyser.fftSize = 1024;
      buf = new Uint8Array(analyser.fftSize);
      src.connect(analyser); analyser.connect(ctx.destination);
      if (ctx.state === 'suspended') ctx.resume();
    } catch (e) { console.warn('입 모양 연결 실패 — 소리는 그대로 나감', e); }
  }
  function setSpeaking(v) { synthSpeaking = v; }
  function level() {
    if (analyser) {
      analyser.getByteTimeDomainData(buf);
      let sum = 0; for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
      const rms = Math.sqrt(sum / buf.length);
      if (rms > 0.01) return Math.min(1, rms * 5);
    }
    if (synthSpeaking) {                    // 브라우저 음성은 소리를 읽을 수 없어 흉내
      const t = performance.now() / 1000;
      return Math.max(0, 0.45 + 0.35 * Math.sin(t * 13) + 0.2 * Math.sin(t * 7.3) - (Math.random() < 0.08 ? 0.6 : 0));
    }
    return 0;
  }
  function tick(now) {
    const target = level();
    open += (target - open) * (target > open ? 0.6 : 0.25);
    const o = Math.max(0, Math.min(1, open));
    mouthOuter.setAttribute('ry', 4 + o * 22); mouthOuter.setAttribute('rx', 30 - o * 4);
    mouthInner.setAttribute('ry', Math.max(0, o * 18 - 1)); mouthInner.setAttribute('cy', 432 + o * 2);
    teeth.setAttribute('height', o > 0.35 ? 6 : 0); teeth.setAttribute('y', 424 - o * 10);
    const brow = o > 0.6 ? -4 : 0;
    browL.setAttribute('transform', `translate(0 ${brow})`); browR.setAttribute('transform', `translate(0 ${brow})`);
    // 눈 깜빡임 (3~6초마다)
    if (now > nextBlink) { blinkT = now; nextBlink = now + 3000 + Math.random() * 3000; }
    const b = now - blinkT < 140 ? 36 : 0;
    lidsL.setAttribute('height', b); lidsR.setAttribute('height', b);
    // 숨쉬기·말할 때 고개 살짝
    const t = now / 1000;
    headG.setAttribute('transform', `translate(0 ${Math.sin(t * 1.6) * 3}) rotate(${Math.sin(t * 2.1) * (0.6 + o * 2)} 410 360)`);
    bodyG.setAttribute('transform', `translate(0 ${Math.sin(t * 1.6) * 2})`);
    requestAnimationFrame(tick);
  }
  return { mount, attachAudio, setSpeaking };
})();
