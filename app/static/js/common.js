// 방송국 화면 공통 도우미
async function api(method, url, body) {
  const r = await fetch(url, { method, credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  let d = null; try { d = await r.json(); } catch (e) {}
  if (r.status === 401 && !url.includes('/auth/login')) { location.href = '/login'; throw new Error('로그인 필요'); }
  if (!r.ok) throw new Error((d && (typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail))) || ('오류 ' + r.status));
  return d;
}
const n = v => (v || 0).toLocaleString('ko-KR');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function toast(msg, ms = 2500) {
  let t = document.querySelector('.toast'); if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.style.display = 'block'; clearTimeout(t._h); t._h = setTimeout(() => t.style.display = 'none', ms);
}
// SSE — 끊기면 브라우저가 스스로 다시 연결 (서버가 retry: 3000 보냄)
// 실시간 알림(SSE) 연결.
// 브라우저는 같은 주소(localhost:8101)에 동시에 6개까지만 연결함 → 탭을 여러 개 열면 7번째부터 줄 서서 기다리며 "확 느려짐".
// 그래서 안 보이는 탭(다른 탭으로 넘어간 탭)은 연결을 잠시 끊고, 다시 보이면 새로 연결 + 화면을 새로 고침.
// 송출 화면처럼 늘 연결돼 있어야 하는 곳은 listen(url, handlers, { keep: true }).
function listen(url, handlers, opt = {}) {
  let es = null;
  const open = () => {
    if (es) return;
    es = new EventSource(url, { withCredentials: true });
    for (const [ev, fn] of Object.entries(handlers)) es.addEventListener(ev, e => fn(JSON.parse(e.data || '{}')));
  };
  const close = () => { if (es) { es.close(); es = null; } };
  open();
  if (!opt.keep) document.addEventListener('visibilitychange', () => {
    if (document.hidden) close();
    else { open(); if (opt.onResume) opt.onResume(); }
  });
  window.addEventListener('pagehide', close);      // 다른 페이지로 넘어갈 때 연결을 바로 반납
  return { close };
}
// 몇 초마다 다시 불러오기 — 안 보이는 탭에서는 쉼, 다시 보이면 바로 한 번 불러옴
function every(fn, ms) {
  setInterval(() => { if (!document.hidden) fn(); }, ms);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) fn(); });
}
async function logout() { await api('POST', '/api/auth/logout'); location.href = '/login'; }
const TYPE_KO = { RATE_MILESTONE: '개표율', LEAD_CHANGE: '1위 변동', WIN_LIKELY: '당선 유력', WIN_SURE: '당선 확실', ELECTED: '당선 확정' };
const FLAG_KO = { LIKELY: '당선 유력', SURE: '당선 확실', ELECTED: '당선 확정' };
// 5개 구 지도 (가상 도시 모양)
const MAP = {
  DEEP:   'M6,25 L108,8 L126,108 L26,126 Z', NEBULA: 'M108,8 L225,17 L218,98 L126,108 Z',
  STAR:   'M225,17 L284,46 L274,166 L234,185 L218,98 Z', ORBIT: 'M26,126 L126,108 L135,217 L36,225 Z',
  DUNE:   'M126,108 L218,98 L234,185 L135,217 Z' };
const MAP_LABEL = { DEEP: [64, 70], NEBULA: [168, 60], STAR: [250, 110], ORBIT: [80, 172], DUNE: [178, 156] };
function drawMap(el, regions, onClick) {
  el.innerHTML = '<svg class="map" viewBox="0 0 290 232">' + regions.map(r =>
    `<path data-code="${r.code}" d="${MAP[r.code] || ''}" fill="${r.leader_color || '#2A3655'}"><title>${esc(r.name)} ${r.counted_rate}%</title></path>`
  ).join('') + regions.map(r => { const p = MAP_LABEL[r.code] || [0, 0];
    return `<text x="${p[0]}" y="${p[1]}" text-anchor="middle" style="fill:${r.leader_color ? '#0B1120' : '#9AA6BC'}">${esc(r.name)}</text>`; }).join('') + '</svg>';
  el.querySelectorAll('path').forEach(p => p.addEventListener('click', () => onClick && onClick(p.dataset.code)));
}
