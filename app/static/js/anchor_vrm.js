// VRoid(VRM) AI 앵커 — 송출 화면 주소에 ?anchor=vrm 을 붙이면 씀.
// 필요한 파일 (Git에 올리지 않음, 드라이브로 공유):
//   app/static/models/anchor_m.vrm · anchor_k.vrm      ← VRoid Studio에서 VRM 1.0으로 내보낸 원본 캐릭터
//   app/static/models/motions/idle.fbx · talk.fbx       ← Mixamo, Without Skin, 30fps (없어도 됨: 계산식 동작으로 대신)
//   (선택) walk.fbx · point.fbx · clap.fbx · bow.fbx · swipe.fbx
// three.js·three-vrm은 인터넷(CDN)에서 불러옴 — 송출 화면 <script type="importmap"> 참고.
// 무엇이든 실패하면 mount()가 false를 돌려주고, 송출 화면이 지금 3D 앵커로 바꿔 씀.
//
// 사용법은 Anchor2D·Anchor3D와 같음: mount(el,{station,code}) → attachAudio(audio) / setSpeaking(bool)
// 더 있는 것: act('swipe'|'point'|'clap'|'bow') 손짓 · setVisible(bool) · fps()
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

const THEMES = {
  M: { bg: 'radial-gradient(circle at 50% 38%, #6E93D6, #4466A6 55%, #2A3F72)', line: '#00E5FF' },
  K: { bg: 'radial-gradient(circle at 50% 38%, #8A5BC4, #55367F 55%, #2A1A45)', line: '#FFB800' },
};
const qs = new URLSearchParams(location.search);
const FRAME = qs.get('vrmframe') === 'full' ? 'full' : 'upper';   // ?vrmframe=full 이면 전신
const SHOW_FPS = qs.get('fps') === '1';
const MAX_FPS = 30;                                                 // OBS가 1초 30장 녹화 → 그 이상 그리지 않음

// Mixamo 뼈 이름 → VRM 뼈 이름 (three-vrm 공식 예제와 같은 표)
const RIG = {
  mixamorigHips: 'hips', mixamorigSpine: 'spine', mixamorigSpine1: 'chest', mixamorigSpine2: 'upperChest',
  mixamorigNeck: 'neck', mixamorigHead: 'head',
  mixamorigLeftShoulder: 'leftShoulder', mixamorigLeftArm: 'leftUpperArm', mixamorigLeftForeArm: 'leftLowerArm', mixamorigLeftHand: 'leftHand',
  mixamorigRightShoulder: 'rightShoulder', mixamorigRightArm: 'rightUpperArm', mixamorigRightForeArm: 'rightLowerArm', mixamorigRightHand: 'rightHand',
  mixamorigLeftUpLeg: 'leftUpperLeg', mixamorigLeftLeg: 'leftLowerLeg', mixamorigLeftFoot: 'leftFoot', mixamorigLeftToeBase: 'leftToes',
  mixamorigRightUpLeg: 'rightUpperLeg', mixamorigRightLeg: 'rightLowerLeg', mixamorigRightFoot: 'rightFoot', mixamorigRightToeBase: 'rightToes',
  mixamorigLeftHandThumb1: 'leftThumbMetacarpal', mixamorigLeftHandThumb2: 'leftThumbProximal', mixamorigLeftHandThumb3: 'leftThumbDistal',
  mixamorigLeftHandIndex1: 'leftIndexProximal', mixamorigLeftHandIndex2: 'leftIndexIntermediate', mixamorigLeftHandIndex3: 'leftIndexDistal',
  mixamorigLeftHandMiddle1: 'leftMiddleProximal', mixamorigLeftHandMiddle2: 'leftMiddleIntermediate', mixamorigLeftHandMiddle3: 'leftMiddleDistal',
  mixamorigLeftHandRing1: 'leftRingProximal', mixamorigLeftHandRing2: 'leftRingIntermediate', mixamorigLeftHandRing3: 'leftRingDistal',
  mixamorigLeftHandPinky1: 'leftLittleProximal', mixamorigLeftHandPinky2: 'leftLittleIntermediate', mixamorigLeftHandPinky3: 'leftLittleDistal',
  mixamorigRightHandThumb1: 'rightThumbMetacarpal', mixamorigRightHandThumb2: 'rightThumbProximal', mixamorigRightHandThumb3: 'rightThumbDistal',
  mixamorigRightHandIndex1: 'rightIndexProximal', mixamorigRightHandIndex2: 'rightIndexIntermediate', mixamorigRightHandIndex3: 'rightIndexDistal',
  mixamorigRightHandMiddle1: 'rightMiddleProximal', mixamorigRightHandMiddle2: 'rightMiddleIntermediate', mixamorigRightHandMiddle3: 'rightMiddleDistal',
  mixamorigRightHandRing1: 'rightRingProximal', mixamorigRightHandRing2: 'rightRingIntermediate', mixamorigRightHandRing3: 'rightRingDistal',
  mixamorigRightHandPinky1: 'rightLittleProximal', mixamorigRightHandPinky2: 'rightLittleIntermediate', mixamorigRightHandPinky3: 'rightLittleDistal',
};

// Mixamo FBX 동작을 이 VRM 캐릭터에 맞게 바꿈 (three-vrm 공식 예제 loadMixamoAnimation과 같은 계산)
async function loadMixamo(url, vrm) {
  const asset = await new FBXLoader().loadAsync(url);
  const clip = THREE.AnimationClip.findByName(asset.animations, 'mixamo.com') || asset.animations[0];
  if (!clip) throw new Error('동작이 없는 파일: ' + url);
  const tracks = [], restInv = new THREE.Quaternion(), parentRest = new THREE.Quaternion(), q = new THREE.Quaternion(), v = new THREE.Vector3();
  const motionHips = asset.getObjectByName('mixamorigHips');
  const motionHipsHeight = motionHips ? motionHips.position.y : 1;
  const vrmHipsY = vrm.humanoid.getNormalizedBoneNode('hips').getWorldPosition(v).y;
  const vrmRootY = vrm.scene.getWorldPosition(v).y;
  const scale = Math.abs(vrmHipsY - vrmRootY) / motionHipsHeight;
  const isV0 = vrm.meta?.metaVersion === '0';
  for (const track of clip.tracks) {
    const [rigName, prop] = track.name.split('.');
    const boneName = RIG[rigName];
    const node = boneName && vrm.humanoid.getNormalizedBoneNode(boneName);
    const rigNode = asset.getObjectByName(rigName);
    if (!node || !rigNode) continue;
    rigNode.getWorldQuaternion(restInv).invert();
    rigNode.parent.getWorldQuaternion(parentRest);
    if (track instanceof THREE.QuaternionKeyframeTrack) {
      const vals = track.values.slice();
      for (let i = 0; i < vals.length; i += 4) {
        q.fromArray(vals, i).premultiply(parentRest).multiply(restInv).toArray(vals, i);
      }
      tracks.push(new THREE.QuaternionKeyframeTrack(`${node.name}.${prop}`, track.times,
        vals.map((x, i) => (isV0 && i % 2 === 0 ? -x : x))));
    } else if (track instanceof THREE.VectorKeyframeTrack && boneName === 'hips') {
      // 엉덩이 위치: 앞뒤·좌우로 걸어 나가는 움직임은 빼고 위아래만 (제자리에서 자연스럽게)
      const vals = track.values.map((x, i) => (i % 3 === 1 ? x * scale : 0));
      tracks.push(new THREE.VectorKeyframeTrack(`${node.name}.${prop}`, track.times, vals));
    }
  }
  return new THREE.AnimationClip(url.split('/').pop(), clip.duration, tracks);
}

let renderer, scene, camera, clock, vrm, mixer, el, canvas, fpsBox;
const actions = {};
let current = null, visible = true, lastDraw = 0, frames = 0, fpsT = 0, fpsNow = 0, slowSecs = 0, dpr = 1;
let ctx = null, analyser = null, buf = null, audioRef = null, analyserWorks = false, synthSpeaking = false, open = 0;
let nextBlink = 2500, blinkT = -9999, gesture = null;          // gesture = {name, t0, dur}
// 지도 무대(?stage=map): 캐릭터가 지도 앞을 걸어 다님
let STAGE = 'box', baseRot = 0, rotY = 0;
const walk = { x: 0, target: null, facing: 0, resolve: null, walking: false };
const WALK_SPEED = 0.9;                                             // 1초에 0.9m

function level() {
  if (analyser) {
    analyser.getByteTimeDomainData(buf);
    let s = 0; for (let i = 0; i < buf.length; i++) { const x = (buf[i] - 128) / 128; s += x * x; }
    const rms = Math.sqrt(s / buf.length);
    if (rms > 0.012) { analyserWorks = true; return Math.min(1, Math.sqrt(rms) * 2.4); }
  }
  const playing = !analyserWorks && audioRef && !audioRef.paused && !audioRef.ended && audioRef.currentTime > 0;
  if (synthSpeaking || playing) {
    const t = performance.now() / 1000;
    return Math.max(0, 0.45 + 0.35 * Math.sin(t * 13) + 0.2 * Math.sin(t * 7.3) - (Math.random() < 0.08 ? 0.6 : 0));
  }
  return 0;
}

function play(name, fade = 0.4) {
  const a = actions[name] || actions.idle;
  if (!a || a === current) return;
  a.reset().fadeIn(fade).play();
  if (current) current.fadeOut(fade);
  current = a;
}

// 동작 파일이 없을 때 쓰는 계산식 자세·손짓 (정규화된 뼈 기준: 팔을 옆으로 편 T자세가 0)
const tmpQ = new THREE.Quaternion(), tmpE = new THREE.Euler();
function bone(n) { return vrm.humanoid.getNormalizedBoneNode(n); }
function blendBone(n, x, y, z, w) {
  const b = bone(n); if (!b) return;
  tmpQ.setFromEuler(tmpE.set(x, y, z)); b.quaternion.slerp(tmpQ, w);
}
function proceduralPose(t, o) {
  const hasIdle = !!actions.idle;
  if (walk.walking && !actions.walk) {                              // 걷기 동작 파일이 없을 때 계산식 걸음
    const ph = t * 7, sw = Math.sin(ph);
    blendBone('leftUpperLeg', sw * 0.45, 0, 0, 1); blendBone('rightUpperLeg', -sw * 0.45, 0, 0, 1);
    blendBone('leftLowerLeg', Math.max(0, -sw) * 0.7, 0, 0, 1); blendBone('rightLowerLeg', Math.max(0, sw) * 0.7, 0, 0, 1);
    blendBone('leftUpperArm', -sw * 0.35, 0, -1.2, 1); blendBone('rightUpperArm', sw * 0.35, 0, 1.2, 1);
    blendBone('hips', 0, 0, 0, 1);
    return;
  }
  if (!hasIdle) {                                                   // 팔 내리기 + 숨쉬기 + 말할 때 손 조금
    blendBone('leftUpperArm', 0, 0, -1.2 + o * 0.15, 1);
    blendBone('rightUpperArm', 0, 0, 1.2 - o * 0.15, 1);
    blendBone('leftLowerArm', 0, -0.25 - o * 0.3, 0, 1);
    blendBone('rightLowerArm', 0, 0.25 + o * 0.3, 0, 1);
    blendBone('spine', Math.sin(t * 1.6) * 0.015, Math.sin(t * 0.7) * 0.03, 0, 1);
    blendBone('neck', Math.sin(t * 1.1) * 0.03 + o * 0.04 * Math.sin(t * 6), Math.sin(t * 0.7) * 0.08, Math.sin(t * 0.9) * 0.03, 1);
  }
  if (!gesture) return;
  const p = (t - gesture.t0) / gesture.dur;
  if (p >= 1) { gesture = null; return; }
  const w = Math.sin(Math.PI * Math.min(1, p)) ;                    // 0 → 1 → 0
  if (gesture.name === 'swipe') {                                   // 왼팔(화면 오른쪽)을 들어 차트 쪽으로 휘이
    const sweep = -0.9 + 1.4 * p;
    blendBone('leftUpperArm', 0, sweep, -0.15, w);
    blendBone('leftLowerArm', 0, -0.35, 0, w);
    blendBone('leftHand', 0, 0, 0.3, w);
  } else if (gesture.name === 'point') {                            // 차트·지도 쪽 가리키기 (지도 무대: 팔을 비스듬히 위로)
    if (STAGE === 'map') blendBone('leftUpperArm', 0, -0.15, 0.45, w);
    else blendBone('leftUpperArm', 0, -0.35, -0.05, w);
    blendBone('leftLowerArm', 0, -0.05, 0, w);
  } else if (gesture.name === 'bow') {
    blendBone('spine', 0.35 * w, 0, 0, 1); blendBone('neck', 0.25 * w, 0, 0, 1);
  } else if (gesture.name === 'clap') {
    const c = Math.abs(Math.sin(p * Math.PI * 6)) * 0.25;
    blendBone('leftUpperArm', 0, -1.0, -0.9, w); blendBone('rightUpperArm', 0, 1.0, 0.9, w);
    blendBone('leftLowerArm', 0, -1.2 + c, 0, w); blendBone('rightLowerArm', 0, 1.2 - c, 0, w);
  }
}

function frameCamera() {
  const v = new THREE.Vector3();
  const head = bone('head').getWorldPosition(v.clone());
  const hips = bone('hips').getWorldPosition(v.clone());
  if (STAGE === 'map') {                                           // 지도 무대: 넓은 화면에 전신, 발이 아래쪽
    camera.position.set(0, 1.0, 4.85); camera.lookAt(0, 1.0, 0); return;
  }
  if (FRAME === 'full') {
    const h = head.y + 0.15;
    camera.position.set(0, h * 0.55, h * 2.1); camera.lookAt(0, h * 0.5, 0);
  } else {
    camera.position.set(0, head.y - 0.05, 1.55); camera.lookAt(0, head.y - 0.22, 0);
  }
  void hips;
}

function tick(now) {
  requestAnimationFrame(tick);
  if (!vrm || !visible || document.hidden) { clock.getDelta(); return; }
  if (now - lastDraw < 1000 / MAX_FPS - 1) return;                 // 30번 고정
  lastDraw = now;
  const dt = Math.min(clock.getDelta(), 0.1), t = now / 1000;
  const target = level(); open += (target - open) * (target > open ? 0.6 : 0.25);
  const o = Math.max(0, Math.min(1, open));
  if (walk.target != null) {                                       // 목표 지점까지 걷기
    const dx = walk.target - walk.x;
    walk.walking = true; walk.facing = dx > 0 ? Math.PI / 2 : -Math.PI / 2;
    walk.x += Math.sign(dx) * Math.min(Math.abs(dx), WALK_SPEED * dt);
    if (Math.abs(walk.target - walk.x) < 0.01) {
      walk.target = null; walk.walking = false; walk.facing = 0;
      const r = walk.resolve; walk.resolve = null; if (r) setTimeout(r, 350);   // 카메라 쪽으로 돌아선 뒤
    }
  }
  rotY += (walk.facing - rotY) * Math.min(1, dt * 8);
  vrm.scene.position.x = walk.x; vrm.scene.rotation.y = baseRot + rotY;
  if (walk.walking && actions.walk) play('walk', 0.3);
  else if (actions.talk) play(o > 0.15 || synthSpeaking ? 'talk' : 'idle', 0.5);
  else if (actions.idle && current === actions.walk) play('idle', 0.3);
  if (mixer) mixer.update(dt);
  proceduralPose(t, o);
  const em = vrm.expressionManager;
  if (em) {
    em.setValue('aa', o);
    if (now > nextBlink) { blinkT = now; nextBlink = now + 3000 + Math.random() * 3000; }
    em.setValue('blink', now - blinkT < 150 ? 1 : 0);
  }
  vrm.update(dt);
  renderer.render(scene, camera);
  // 초당 그리는 횟수 재기 + 너무 느리면 그림을 덜 세밀하게
  frames++;
  if (now - fpsT > 1000) {
    fpsNow = frames * 1000 / (now - fpsT); frames = 0; fpsT = now;
    if (fpsBox) fpsBox.textContent = `${fpsNow.toFixed(0)} fps · ${dpr}x`;
    slowSecs = fpsNow < 20 ? slowSecs + 1 : 0;
    if (slowSecs >= 5 && dpr > 0.5) { dpr = dpr > 0.75 ? 0.75 : 0.5; renderer.setPixelRatio(dpr); resize(); slowSecs = 0; }
  }
}

function resize() {
  const w = el.clientWidth, h = el.clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}

async function mount(element, opt = {}) {
  el = element;
  const code = opt.code === 'K' ? 'K' : 'M', theme = THEMES[code];
  STAGE = opt.stage === 'map' ? 'map' : 'box';
  try {
    el.innerHTML = `${STAGE === 'map' ? '' : `<div style="position:absolute;inset:0;background:${theme.bg}"></div>`}
      <canvas style="position:absolute;inset:0;width:100%;height:100%"></canvas>
      <div style="display:${STAGE === 'map' ? 'none' : 'flex'};position:absolute;left:10%;right:10%;bottom:0;height:10%;border-radius:10px;background:#0E1527;border:3px solid ${theme.line};
        align-items:center;justify-content:center;color:#F2F5FA;font-weight:800;font-size:34px">${opt.station || '방송국'} · AI 앵커</div>
      <div class="vrmload" style="position:absolute;left:0;right:0;top:45%;text-align:center;color:#DDE4F2;font-size:28px">앵커 불러오는 중…</div>
      ${SHOW_FPS ? '<div class="fps" style="position:absolute;right:12px;top:12px;background:#000a;color:#0f0;font:20px monospace;padding:4px 8px;border-radius:6px">-</div>' : ''}`;
    canvas = el.querySelector('canvas'); fpsBox = el.querySelector('.fps');
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    dpr = Math.min(window.devicePixelRatio || 1, 1); renderer.setPixelRatio(dpr);
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(30, 1, 0.1, 30);
    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(0.6, 1.4, 2); scene.add(key);
    const rim = new THREE.DirectionalLight(code === 'K' ? 0xffc6f2 : 0x9fefff, 0.8); rim.position.set(-1.5, 1.2, -1.5); scene.add(rim);
    clock = new THREE.Clock(); resize(); window.addEventListener('resize', resize);

    const loader = new GLTFLoader(); loader.register(p => new VRMLoaderPlugin(p));
    const gltf = await loader.loadAsync(`/static/models/anchor_${code.toLowerCase()}.vrm`);
    vrm = gltf.userData.vrm;
    if (!vrm) throw new Error('VRM 파일이 아님');
    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.combineSkeletons?.(gltf.scene);
    VRMUtils.rotateVRM0(vrm);                                       // 옛 VRM 0.x도 앞을 보게
    baseRot = vrm.scene.rotation.y;
    vrm.scene.traverse(o => { o.frustumCulled = false; });
    scene.add(vrm.scene);
    vrm.scene.updateMatrixWorld(true);
    frameCamera();

    mixer = new THREE.AnimationMixer(vrm.scene);
    for (const name of ['idle', 'talk', 'walk', 'point', 'clap', 'bow', 'swipe']) {
      try {
        const clip = await loadMixamo(`/static/models/motions/${name}.fbx`, vrm);
        const a = mixer.clipAction(clip);
        if (['point', 'clap', 'bow', 'swipe'].includes(name)) { a.setLoop(THREE.LoopOnce); a.clampWhenFinished = false; }
        actions[name] = a;
      } catch (e) { /* 파일이 없으면 계산식 동작으로 */ }
    }
    console.info('[VRM 앵커] 불러온 동작:', Object.keys(actions).join(', ') || '없음 (계산식 동작 사용)');
    if (actions.idle) play('idle', 0);
    el.querySelector('.vrmload')?.remove();
    requestAnimationFrame(tick);
    return true;
  } catch (e) {
    console.warn('[VRM 앵커] 준비 실패 → 3D 앵커로 바꿈:', e);
    el.innerHTML = '';
    return false;
  }
}

function attachAudio(audioEl) {
  audioRef = audioEl;
  audioEl.addEventListener('play', () => { if (ctx && ctx.state === 'suspended') ctx.resume().catch(() => {}); });
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaElementSource(audioEl);
    analyser = ctx.createAnalyser(); analyser.fftSize = 1024; buf = new Uint8Array(analyser.fftSize);
    src.connect(analyser); analyser.connect(ctx.destination);
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});
  } catch (e) { console.warn('입 모양 연결 실패 — 소리는 그대로 나감', e); }
}
function setSpeaking(v) { synthSpeaking = v; }
function setVisible(v) { visible = v; }
function fps() { return fpsNow; }

// 손짓: 동작 파일이 있으면 그것을, 없으면 계산식으로. 손짓의 한가운데(화면을 바꿀 때)까지 기다림
function act(name) {
  if (!vrm) return Promise.resolve();
  const dur = { swipe: 1.1, point: 2.2, clap: 1.8, bow: 1.6 }[name] || 1.2;
  if (actions[name]) {
    const a = actions[name]; a.reset().fadeIn(0.25).play(); if (current) current.fadeOut(0.25);
    const back = current; current = a;
    setTimeout(() => { a.fadeOut(0.4); current = null; if (back) play(back === actions.talk ? 'talk' : 'idle', 0.4); }, a.getClip().duration * 1000 - 300);
    return new Promise(r => setTimeout(r, Math.min(900, a.getClip().duration * 450)));
  }
  gesture = { name, t0: performance.now() / 1000, dur };
  return new Promise(r => setTimeout(r, dur * 500));
}

// 지도 무대: 화면 가로 위치(0=왼쪽 끝, 1=오른쪽 끝)로 걸어감. side=true 면 그 지점의 왼쪽에 서서 가리킬 준비
function walkTo(fx, side = false) {
  if (!vrm || STAGE !== 'map') return Promise.resolve();
  const halfW = camera.position.z * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect;
  let x = (fx - 0.5) * 2 * halfW - (side ? 0.45 : 0);
  x = Math.max(-halfW + 0.4, Math.min(halfW - 0.4, x));
  if (Math.abs(x - walk.x) < 0.05) return Promise.resolve();
  if (walk.resolve) walk.resolve();
  return new Promise(r => { walk.target = x; walk.resolve = r; setTimeout(r, 12000); });   // 12초 넘으면 그냥 다음으로
}

window.AnchorVRM = { mount, attachAudio, setSpeaking, setVisible, fps, act, walkTo };
export default window.AnchorVRM;
