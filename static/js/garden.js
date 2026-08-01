// Sculpture-garden fly-through. Data comes from content/garden.json, injected
// into the page as <script type="application/json" id="garden-data">.
// Two modes: Tour (camera on a spline, scroll/drag scrubs) and Walk (WASD).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

const data = JSON.parse(document.getElementById('garden-data').textContent);
const container = document.getElementById('garden-canvas');
const loadingEl = document.getElementById('garden-loading');
const progressEl = document.getElementById('garden-progress');
const modeBtn = document.getElementById('garden-mode');

const isTouch = navigator.maxTouchPoints > 0 && matchMedia('(pointer: coarse)').matches;
const canWebGL = (() => {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch { return false; }
})();
if (!canWebGL) {
  loadingEl.innerHTML = '<p>This device cannot show the 3D garden. ' +
    'Visit the <a href="/#sonnets">sonnet pages</a> for images of every sculpture.</p>';
  throw new Error('no webgl');
}

// --- scene -----------------------------------------------------------------
const BG = 0x1e1e2e;
const scene = new THREE.Scene();
scene.background = new THREE.Color(BG);
scene.fog = new THREE.Fog(BG, 20, 90);

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
container.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer();
labelRenderer.domElement.style.cssText = 'position:absolute;top:0;pointer-events:none';
container.appendChild(labelRenderer.domElement);

function resize() {
  const { clientWidth: w, clientHeight: h } = container;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  labelRenderer.setSize(w, h);
}
addEventListener('resize', resize);
resize();

// gradient sky: big inverted sphere, horizon glow fading to bg
const sky = new THREE.Mesh(
  new THREE.SphereGeometry(120, 24, 16),
  new THREE.ShaderMaterial({
    side: THREE.BackSide,
    uniforms: { top: { value: new THREE.Color(BG) }, horizon: { value: new THREE.Color(0x89b4fa) } },
    vertexShader: 'varying float h; void main(){ h = normalize(position).y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform vec3 top; uniform vec3 horizon; varying float h;' +
      'void main(){ gl_FragColor = vec4(mix(horizon, top, clamp(abs(h) * 2.5, 0.0, 1.0)) , 1.0); }',
  })
);
scene.add(sky);

const ground = new THREE.Mesh(
  new THREE.CircleGeometry(100, 64),
  new THREE.MeshStandardMaterial({ color: 0x181825, roughness: 0.95 })
);
ground.rotation.x = -Math.PI / 2;
scene.add(ground);

scene.add(new THREE.HemisphereLight(0x89b4fa, 0x181825, 0.7));
const sun = new THREE.DirectionalLight(0xfab387, 1.4);
sun.position.set(12, 18, 8);
scene.add(sun);

// --- sculptures ------------------------------------------------------------
const draco = new DRACOLoader().setDecoderPath('/static/vendor/draco/');
const loader = new GLTFLoader().setDRACOLoader(draco);

const plinthGeo = new THREE.CylinderGeometry(1.4, 1.6, 0.5, 24);
const plinthMat = new THREE.MeshStandardMaterial({ color: 0x313244, roughness: 0.8 });
const anchors = [];
let loaded = 0;

function addSculpture(s) {
  const pos = new THREE.Vector3(...(s.position || [0, 0, 0]));
  const plinth = new THREE.Mesh(plinthGeo, plinthMat);
  plinth.position.copy(pos).setY(0.25);
  scene.add(plinth);

  const label = document.createElement('a');
  label.className = 'plinth-label';
  label.textContent = s.label || s.sonnet;
  label.href = `/sonnets/${s.sonnet}/`;
  label.style.pointerEvents = 'auto';
  const labelObj = new CSS2DObject(label);
  labelObj.position.copy(pos).setY(3.6);
  scene.add(labelObj);
  anchors.push(pos.clone().setY(1.6));

  return new Promise((resolve) => {
    loader.load(s.glb, (gltf) => {
      const model = gltf.scene;
      // normalize to ~2.5 units tall on the plinth
      const box = new THREE.Box3().setFromObject(model);
      const size = box.getSize(new THREE.Vector3());
      const scale = (s.scale || 1) * (2.5 / Math.max(size.x, size.y, size.z));
      model.scale.setScalar(scale);
      box.setFromObject(model);
      model.position.copy(pos).setY(0.5 - box.min.y);
      if (s.rotation) model.rotation.y = s.rotation;
      scene.add(model);
      resolve();
    }, undefined, () => resolve()); // a missing GLB shouldn't kill the garden
  }).then(() => {
    loaded += 1;
    progressEl.style.width = `${(loaded / data.sculptures.length) * 100}%`;
  });
}

// nearest-to-spawn first, first three gate the reveal, rest stream in
const origin = new THREE.Vector3(0, 0, 18);
const sorted = [...data.sculptures].sort((a, b) =>
  new THREE.Vector3(...(a.position || [0, 0, 0])).distanceTo(origin) -
  new THREE.Vector3(...(b.position || [0, 0, 0])).distanceTo(origin));
Promise.all(sorted.slice(0, 3).map(addSculpture)).then(() => {
  loadingEl.remove();
  sorted.slice(3).forEach(addSculpture);
});

// --- tour mode: camera on a loop through the plinths -----------------------
const focus = new URLSearchParams(location.search).get('focus');
const focusIdx = Math.max(0, data.sculptures.findIndex((s) => s.sonnet === focus));
const pathPoints = (data.sculptures.length >= 2 ? data.sculptures : [...data.sculptures, { position: [0, 0, 10] }])
  .map((s) => new THREE.Vector3(...(s.position || [0, 0, 0])).add(new THREE.Vector3(3.5, 2, 3.5)));
const curve = new THREE.CatmullRomCurve3(pathPoints, true, 'centripetal', 0.5);
let tourT = focusIdx / Math.max(1, data.sculptures.length);
let tourTarget = tourT;

addEventListener('wheel', (e) => { tourTarget += e.deltaY * 0.0003; }, { passive: true });
let dragY = null;
container.addEventListener('pointerdown', (e) => { if (mode === 'tour') dragY = e.clientY; });
addEventListener('pointermove', (e) => { if (dragY !== null) { tourTarget += (e.clientY - dragY) * 0.001; dragY = e.clientY; } });
addEventListener('pointerup', () => { dragY = null; });

// --- walk mode (desktop) ---------------------------------------------------
let mode = 'tour';
let walk = null;
const keys = {};
if (!isTouch) {
  modeBtn.hidden = false;
  walk = new PointerLockControls(camera, renderer.domElement);
  modeBtn.addEventListener('click', () => walk.lock());
  walk.addEventListener('lock', () => { mode = 'walk'; modeBtn.textContent = 'Walking (Esc to exit)'; });
  walk.addEventListener('unlock', () => { mode = 'tour'; modeBtn.textContent = 'Walk'; });
  addEventListener('keydown', (e) => { keys[e.code] = true; });
  addEventListener('keyup', (e) => { keys[e.code] = false; });
}

// --- render loop -----------------------------------------------------------
const clock = new THREE.Clock();
const lookAhead = new THREE.Vector3();
function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();
  if (mode === 'tour') {
    tourT += (tourTarget - tourT) * Math.min(1, dt * 3);
    const t = ((tourT % 1) + 1) % 1;
    curve.getPointAt(t, camera.position);
    curve.getPointAt((t + 0.03) % 1, lookAhead);
    const nearest = anchors.reduce((best, a) =>
      a.distanceTo(camera.position) < best.distanceTo(camera.position) ? a : best, lookAhead);
    camera.lookAt(nearest.distanceTo(camera.position) < 9 ? nearest : lookAhead);
  } else if (walk) {
    const speed = 8 * dt;
    if (keys.KeyW || keys.ArrowUp) walk.moveForward(speed);
    if (keys.KeyS || keys.ArrowDown) walk.moveForward(-speed);
    if (keys.KeyA || keys.ArrowLeft) walk.moveRight(-speed);
    if (keys.KeyD || keys.ArrowRight) walk.moveRight(speed);
    camera.position.y = 1.7;
  }
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}
animate();
