// ==========================================
// 1. SETUP DUNIA 3D & KANVAS TERSEMBUNYI
// ==========================================
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050505);

const camera = new THREE.PerspectiveCamera(
  75,
  window.innerWidth / window.innerHeight,
  0.1,
  1000,
);
camera.position.set(0, 0, 10);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const canvas2d = document.createElement("canvas");
canvas2d.width = 1024;
canvas2d.height = 512;
const ctx = canvas2d.getContext("2d", { willReadFrequently: true });

// ==========================================
// 2. SISTEM PARTIKEL MORPHING
// ==========================================
const jumlahPartikel = 4000;
const particleGeo = new THREE.BufferGeometry();
const posisiAwal = new Float32Array(jumlahPartikel * 3);
const posisiTarget = new Float32Array(jumlahPartikel * 3);

for (let i = 0; i < jumlahPartikel * 3; i++) {
  posisiAwal[i] = (Math.random() - 0.5) * 30;
  posisiTarget[i] = posisiAwal[i];
}

particleGeo.setAttribute("position", new THREE.BufferAttribute(posisiAwal, 3));

const particleMat = new THREE.PointsMaterial({
  color: 0x00ffff,
  size: 0.15,
  transparent: true,
  opacity: 0.9,
});

const hologramParticles = new THREE.Points(particleGeo, particleMat);
scene.add(hologramParticles);

// Fungsi Hack Teks (Font dirampingkan biar ga kegencet)
function setTargetTeks(teks, ukuranFont = 85, yOffset = 0) {
  ctx.clearRect(0, 0, 1024, 512);
  ctx.fillStyle = "white";
  // Pake Arial biar ramping, ukuran font udah disesuaikan
  ctx.font = `bold ${ukuranFont}px Arial`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(teks, 512, 256);

  const imgData = ctx.getImageData(0, 0, 1024, 512).data;
  const titikValid = [];

  // Sampling rapat
  for (let y = 0; y < 512; y += 2) {
    for (let x = 0; x < 1024; x += 2) {
      if (imgData[(y * 1024 + x) * 4 + 3] > 128) {
        titikValid.push({
          x: (x - 512) / 40,
          y: -(y - 256) / 40 + yOffset,
          z: (Math.random() - 0.5) * 0.2,
        });
      }
    }
  }

  for (let i = 0; i < jumlahPartikel; i++) {
    if (titikValid.length > 0) {
      const target = titikValid[i % titikValid.length];
      posisiTarget[i * 3] = target.x;
      posisiTarget[i * 3 + 1] = target.y;
      posisiTarget[i * 3 + 2] = target.z;
    }
  }
}

// Fungsi Bikin Bentuk Love
function setTargetLove() {
  for (let i = 0; i < jumlahPartikel; i++) {
    const t = Math.PI * 2 * (i / jumlahPartikel);
    const x = 16 * Math.pow(Math.sin(t), 3);
    const y =
      13 * Math.cos(t) -
      5 * Math.cos(2 * t) -
      2 * Math.cos(3 * t) -
      Math.cos(4 * t);

    posisiTarget[i * 3] = x * 0.25;
    posisiTarget[i * 3 + 1] = y * 0.25 + 2;
    posisiTarget[i * 3 + 2] = (Math.random() - 0.5) * 0.5;
  }
}

// Fungsi Ngumpulin Partikel di Kursor
function setTargetKursor(xKursor, yKursor) {
  for (let i = 0; i < jumlahPartikel; i++) {
    posisiTarget[i * 3] = xKursor + (Math.random() - 0.5) * 3;
    posisiTarget[i * 3 + 1] = yKursor + (Math.random() - 0.5) * 3;
    posisiTarget[i * 3 + 2] = (Math.random() - 0.5) * 3;
  }
}

// Animasi
function animate() {
  requestAnimationFrame(animate);

  const posisiSkrg = hologramParticles.geometry.attributes.position.array;
  for (let i = 0; i < jumlahPartikel * 3; i++) {
    posisiSkrg[i] += (posisiTarget[i] - posisiSkrg[i]) * 0.1;
  }
  hologramParticles.geometry.attributes.position.needsUpdate = true;
  renderer.render(scene, camera);
}
animate();

// ==========================================
// 3. MATA AI & DETEKSI GESTUR SANGAT AKURAT
// ==========================================
const videoElement = document.getElementById("videoWebcam");

const hands = new Hands({
  locateFile: (file) => {
    return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
  },
});

hands.setOptions({
  maxNumHands: 1,
  modelComplexity: 1,
  minDetectionConfidence: 0.7,
  minTrackingConfidence: 0.7,
});

function hitungJarak(titik1, titik2) {
  return Math.sqrt(
    Math.pow(titik1.x - titik2.x, 2) + Math.pow(titik1.y - titik2.y, 2),
  );
}

let gesturTerakhir = "";

hands.onResults((hasil) => {
  if (hasil.multiHandLandmarks && hasil.multiHandLandmarks.length > 0) {
    const tangan = hasil.multiHandLandmarks[0];
    const pergelangan = tangan[0];

    let x_3D = -(tangan[8].x - 0.5) * 20;
    let y_3D = -(tangan[8].y - 0.5) * 15;

    // --- RUMUS BARU: ANTI GALAU ---
    // Kita ukur ujung jari (8,12,16,20) ke sendi tengahnya (6,10,14,18).
    // Jauh lebih akurat buat deteksi jari ditekuk atau dilurusin!
    const jempolBuka =
      hitungJarak(tangan[4], tangan[17]) > hitungJarak(tangan[3], tangan[17]);
    const telunjukBuka =
      hitungJarak(tangan[8], pergelangan) > hitungJarak(tangan[6], pergelangan);
    const tengahBuka =
      hitungJarak(tangan[12], pergelangan) >
      hitungJarak(tangan[10], pergelangan);
    const manisBuka =
      hitungJarak(tangan[16], pergelangan) >
      hitungJarak(tangan[14], pergelangan);
    const kelingkingBuka =
      hitungJarak(tangan[20], pergelangan) >
      hitungJarak(tangan[18], pergelangan);

    let gesturSkrg = "KURSOR";
    let colorTarget = 0x444444;

    // 1. HALLO (Semua Buka)
    if (
      jempolBuka &&
      telunjukBuka &&
      tengahBuka &&
      manisBuka &&
      kelingkingBuka
    ) {
      gesturSkrg = "HALLO";
    }
    // 2. LOVE / METAL (Jempol, Telunjuk, Kelingking Buka)
    else if (
      jempolBuka &&
      telunjukBuka &&
      !tengahBuka &&
      !manisBuka &&
      kelingkingBuka
    ) {
      gesturSkrg = "LOVE";
    }
    // 3. SAYA (Telunjuk Buka)
    else if (telunjukBuka && !tengahBuka && !manisBuka && !kelingkingBuka) {
      gesturSkrg = "SAYA";
    }
    // 4. M. ABDUL FARID (Telunjuk & Tengah Buka)
    else if (telunjukBuka && tengahBuka && !manisBuka && !kelingkingBuka) {
      gesturSkrg = "NAMA";
    }
    // 5. MOHON MAAF (JEMPOL DOANG)
    else if (jempolBuka && !telunjukBuka && !tengahBuka) {
      gesturSkrg = "MAAF";
    }
    // 6. TERIMAKASIH (JARI TENGAH DOANG) -> SEKARANG PASTI KEBACA!
    else if (!telunjukBuka && tengahBuka && !manisBuka) {
      gesturSkrg = "TERIMAKASIH";
    }

    // --- GANTI TARGET PARTIKEL ---
    if (gesturSkrg !== gesturTerakhir) {
      if (gesturSkrg === "HALLO") {
        setTargetTeks("HALLO", 100, 0);
        colorTarget = 0x00ffff;
      } else if (gesturSkrg === "TERIMAKASIH") {
        // Teks "TERIMA KASIH" gw kasih spasi & font 85 biar rapi gak gepeng
        setTargetTeks("TERIMA KASIH", 85, 0);
        colorTarget = 0xffffff;
      } else if (gesturSkrg === "SAYA") {
        setTargetTeks("SAYA", 100, 0);
        colorTarget = 0xffff00;
      } else if (gesturSkrg === "NAMA") {
        setTargetTeks("M. ABDUL FARID", 75, 0);
        colorTarget = 0xff00ff;
      } else if (gesturSkrg === "MAAF") {
        setTargetTeks("MOHON MAAF LAHIR BATIN", 65, 0);
        colorTarget = 0x00ff00;
      } else if (gesturSkrg === "LOVE") {
        setTargetLove();
        colorTarget = 0xff0000;
      } else {
        setTargetKursor(x_3D, y_3D);
        colorTarget = 0x444444;
      }
      hologramParticles.material.color.setHex(colorTarget);
      gesturTerakhir = gesturSkrg;

      // Log ini gw tambahin biar lu bisa pantau di console murni gestur yg ini aja
      console.log("Gestur Terdeteksi:", gesturSkrg);
    }

    if (gesturSkrg === "KURSOR") {
      setTargetKursor(x_3D, y_3D);
    }
  }
});

const cameraAI = new Camera(videoElement, {
  onFrame: async () => {
    await hands.send({ image: videoElement });
  },
  width: 640,
  height: 480,
});
cameraAI.start();
