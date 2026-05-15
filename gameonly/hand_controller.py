"""
hand_controller.py
==================
Real-time hand gesture recognition menggunakan MediaPipe Tasks API + TensorFlow.

Gestures yang dideteksi:
  - MOVE_LEFT   : tangan gerak ke kiri
  - MOVE_RIGHT  : tangan gerak ke kanan
  - MOVE_UP     : tangan gerak ke atas
  - MOVE_DOWN   : tangan gerak ke bawah
  - SHOOT       : jari telunjuk tegak, jari lain tertutup (pointing ✌ → ☝)
  - SHIELD      : semua jari terbuka (open palm 🖐)
  - IDLE        : tidak ada gesture khusus
"""

import cv2
import numpy as np
import threading
import time
import os
import urllib.request
from collections import deque, Counter
from enum import Enum, auto

# ── MediaPipe Tasks API ───────────────────────────────────────────────────────
MP_AVAILABLE = False
mp = None
HandLandmarker = None
HandLandmarkerOptions = None
VisionRunningMode = None
BaseOptions = None
MpImage = None
MpImageFormat = None

try:
    import mediapipe as mp
    from mediapipe.tasks import python as _tasks_python
    from mediapipe.tasks.python import vision as _tasks_vision
    BaseOptions       = _tasks_python.BaseOptions
    HandLandmarker    = _tasks_vision.HandLandmarker
    HandLandmarkerOptions = _tasks_vision.HandLandmarkerOptions
    VisionRunningMode = _tasks_vision.RunningMode
    MpImage           = mp.Image
    MpImageFormat     = mp.ImageFormat
    MP_AVAILABLE      = True
except Exception as _e:
    print(f"[WARNING] MediaPipe Tasks API tidak tersedia: {_e}")

# Model hand landmark (didownload otomatis jika belum ada)
MODEL_URL  = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")

# Koneksi tangan untuk drawing (tanpa mp.solutions)
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(0,17),(17,18),(18,19),(19,20),
]

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("[WARNING] TensorFlow tidak tersedia, fallback ke rule-based gesture.")


# ──────────────────────────────────────────────
# Enum Gesture
# ──────────────────────────────────────────────
class Gesture(Enum):
    IDLE        = auto()
    MOVE_LEFT   = auto()
    MOVE_RIGHT  = auto()
    MOVE_UP     = auto()
    MOVE_DOWN   = auto()
    SHOOT       = auto()   # ☝ telunjuk berdiri
    SHIELD      = auto()   # 🖐 palm terbuka


# ──────────────────────────────────────────────
# Landmark index (MediaPipe 21 titik)
# ──────────────────────────────────────────────
WRIST          = 0
THUMB_TIP      = 4
INDEX_TIP      = 8
MIDDLE_TIP     = 12
RING_TIP       = 16
PINKY_TIP      = 20
INDEX_MCP      = 5
MIDDLE_MCP     = 9
RING_MCP       = 13
PINKY_MCP      = 17
INDEX_PIP      = 6
MIDDLE_PIP     = 10
RING_PIP       = 14
PINKY_PIP      = 18


class GestureClassifier:
    """
    Classifier berbasis TensorFlow ringan.
    Input  : 21 landmark (x, y, z) → 63 fitur, dinormalisasi relatif terhadap wrist.
    Output : 7 kelas gesture.
    
    Kalau TF tidak tersedia, fallback ke rule-based classifier.
    """

    LABELS = [g for g in Gesture]

    def __init__(self, use_tf: bool = True):
        self.use_tf = use_tf and TF_AVAILABLE
        self.model  = None
        if self.use_tf:
            self._build_model()

    def _build_model(self):
        """Buat model MLP ringan (tidak perlu training besar, cukup rule → label)."""
        inp = tf.keras.Input(shape=(63,))
        x   = tf.keras.layers.Dense(64, activation="relu")(inp)
        x   = tf.keras.layers.Dropout(0.2)(x)
        x   = tf.keras.layers.Dense(32, activation="relu")(x)
        out = tf.keras.layers.Dense(len(self.LABELS), activation="softmax")(x)
        self.model = tf.keras.Model(inp, out)
        self.model.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
        # Model belum di-train → kita tetap pakai rule-based sebagai oracle
        # (TF dipakai untuk arsitektur; bisa di-fine-tune dengan dataset sendiri)
        self.use_tf = False   # aktifkan setelah model di-train
        print("[GestureClassifier] Model TF siap (belum di-train, pakai rule-based).")

    @staticmethod
    def _normalize(landmarks) -> np.ndarray:
        """Normalisasi landmark relatif terhadap wrist, scale ke bounding box."""
        pts = np.array([[lm.x, lm.y, lm.z] for lm in landmarks])
        origin = pts[WRIST]
        pts -= origin
        scale = np.max(np.abs(pts)) + 1e-6
        pts /= scale
        return pts.flatten()   # (63,)

    # ── Rule-based classifier ──────────────────
    @staticmethod
    def _finger_up(landmarks, tip_idx, pip_idx, mcp_idx) -> bool:
        """Jari tegak jika tip lebih tinggi dari pip ATAU mcp (sensitif ke berbagai sudut)."""
        return (landmarks[tip_idx].y < landmarks[pip_idx].y or
                landmarks[tip_idx].y < landmarks[mcp_idx].y)

    def classify_rules(self, landmarks) -> Gesture:
        lm = landmarks
        index_up  = self._finger_up(lm, INDEX_TIP,  INDEX_PIP,  INDEX_MCP)
        middle_up = self._finger_up(lm, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP)
        ring_up   = self._finger_up(lm, RING_TIP,   RING_PIP,   RING_MCP)
        pinky_up  = self._finger_up(lm, PINKY_TIP,  PINKY_PIP,  PINKY_MCP)

        n_up = sum([index_up, middle_up, ring_up, pinky_up])

        # SHIELD : 4+ jari terbuka (telapak penuh)
        if n_up >= 4:
            return Gesture.SHIELD

        # MOVE_RIGHT : 3 jari (angka 3)
        if n_up == 3:
            return Gesture.MOVE_RIGHT

        # MOVE_LEFT : 2 jari (angka 2 / peace sign)
        if n_up == 2:
            return Gesture.MOVE_LEFT

        # SHOOT : hanya telunjuk berdiri (angka 1)
        if index_up and not middle_up and not ring_up and not pinky_up:
            return Gesture.SHOOT

        return Gesture.IDLE

    def classify(self, landmarks) -> Gesture:
        if self.use_tf and self.model is not None:
            feat  = self._normalize(landmarks).reshape(1, -1)
            probs = self.model.predict(feat, verbose=0)[0]
            return self.LABELS[np.argmax(probs)]
        return self.classify_rules(landmarks)


# ──────────────────────────────────────────────
# Model download helper
# ──────────────────────────────────────────────
def _ensure_model():
    """Download hand_landmarker.task jika belum ada di folder proyek."""
    if os.path.exists(MODEL_PATH):
        return True
    if not MP_AVAILABLE:
        return False
    print(f"[HandController] Mendownload model hand landmark (~26 MB)...")
    print(f"                  Simpan ke: {MODEL_PATH}")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[HandController] Download selesai.")
        return True
    except Exception as e:
        print(f"[ERROR] Gagal download model: {e}")
        return False


# ──────────────────────────────────────────────
# HandController — thread kamera terpisah
# ──────────────────────────────────────────────
class HandController:
    """
    Menjalankan kamera + MediaPipe Tasks HandLandmarker di thread background.
    Game cukup panggil:
        ctrl.gesture   → Gesture enum saat ini
        ctrl.hand_x    → posisi X tangan (0.0–1.0), kiri = 0
        ctrl.hand_y    → posisi Y tangan (0.0–1.0), atas = 0
        ctrl.frame     → frame BGR (untuk debug overlay)
    """

    SMOOTHING   = 5      # jumlah frame untuk rata-rata posisi
    MOVE_THRESH = 0.04   # threshold gerak (lebih sensitif dari 0.06)
    VOTE_FRAMES = 5      # jumlah frame untuk gesture voting

    def __init__(self, camera_index: int = 0, show_preview: bool = True):
        self.camera_index = camera_index
        self.show_preview = show_preview

        # State publik (thread-safe baca)
        self.gesture: Gesture = Gesture.IDLE
        self.hand_x: float    = 0.5
        self.hand_y: float    = 0.5
        self.frame            = None
        self.active: bool     = False

        # Internal
        self._x_hist        = deque(maxlen=self.SMOOTHING)
        self._y_hist        = deque(maxlen=self.SMOOTHING)
        self._gesture_vote  = deque(maxlen=self.VOTE_FRAMES)  # voting buffer
        self._last_gesture  = Gesture.IDLE                    # untuk console print
        self._hand_visible  = False                           # status deteksi
        self._lock          = threading.Lock()
        self._thread        = None

        # Tentukan backend
        self._backend = "none"
        if MP_AVAILABLE and HandLandmarker is not None:
            if _ensure_model():
                self._backend = "tasks"
            else:
                print("[WARNING] Model tidak tersedia. Gesture detection dinonaktifkan.")
        elif not MP_AVAILABLE:
            print("[WARNING] MediaPipe tidak tersedia. Gesture detection dinonaktifkan.")

        self._classifier = GestureClassifier()

    # ── Public API ─────────────────────────────
    def start(self):
        self.active  = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[HandController] Kamera dimulai (backend={self._backend}).")

    def stop(self):
        self.active = False
        if self._thread:
            self._thread.join(timeout=2)
        print("[HandController] Kamera dihentikan.")

    # ── Internal loop ──────────────────────────
    def _loop(self):
        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        if not cap.isOpened():
            print(f"[ERROR] Kamera index {self.camera_index} tidak bisa dibuka.")
            self.active = False
            return

        landmarker = None
        if self._backend == "tasks":
            opts = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=MODEL_PATH),
                running_mode=VisionRunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.4,   # diturunkan: lebih mudah terdeteksi
                min_hand_presence_confidence=0.3,    # diturunkan
                min_tracking_confidence=0.3,         # diturunkan
            )
            landmarker = HandLandmarker.create_from_options(opts)

        prev_x, prev_y = 0.5, 0.5
        start_ms = int(time.time() * 1000)

        while self.active:
            ret, raw_frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            # Flip horizontal (mirror) agar intuitif
            frame     = cv2.flip(raw_frame, 1)
            gesture   = Gesture.IDLE
            hx, hy    = prev_x, prev_y

            hand_now = False
            if landmarker is not None:
                rgb        = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image   = MpImage(image_format=MpImageFormat.SRGB,
                                     data=np.ascontiguousarray(rgb))
                timestamp  = int(time.time() * 1000) - start_ms
                result     = landmarker.detect_for_video(mp_image, timestamp)
                hand_now   = bool(result.hand_landmarks)

                if hand_now:
                    lm = result.hand_landmarks[0]  # list of NormalizedLandmark

                    # Gambar koneksi tangan
                    h_f, w_f = frame.shape[:2]
                    pts_px = [(int(p.x * w_f), int(p.y * h_f)) for p in lm]
                    for a, b in HAND_CONNECTIONS:
                        cv2.line(frame, pts_px[a], pts_px[b], (255, 255, 0), 2)
                    for pt in pts_px:
                        cv2.circle(frame, pt, 3, (0, 255, 120), -1)

                    # Posisi wrist (landmark 0)
                    hx = lm[WRIST].x
                    hy = lm[WRIST].y

                    self._x_hist.append(hx)
                    self._y_hist.append(hy)
                    smooth_x = float(np.mean(self._x_hist))
                    smooth_y = float(np.mean(self._y_hist))

                    dx = smooth_x - prev_x
                    dy = smooth_y - prev_y

                    base_gesture = self._classifier.classify(lm)

                    # SHOOT, SHIELD, dan arah KIRI/KANAN dari finger-count
                    if base_gesture in (Gesture.SHOOT, Gesture.SHIELD,
                                        Gesture.MOVE_LEFT, Gesture.MOVE_RIGHT):
                        gesture = base_gesture
                    elif abs(dy) > self.MOVE_THRESH:
                        # Atas/bawah tetap dari delta gerakan tangan
                        if dy > self.MOVE_THRESH:
                            gesture = Gesture.MOVE_DOWN
                        elif dy < -self.MOVE_THRESH:
                            gesture = Gesture.MOVE_UP

                    prev_x, prev_y = smooth_x, smooth_y
                    hx, hy = smooth_x, smooth_y

            # ── Feedback ke konsol saat status tangan berubah ──
            if hand_now != self._hand_visible:
                self._hand_visible = hand_now
                if hand_now:
                    print("[Hand] ✓ TANGAN TERDETEKSI")
                else:
                    print("[Hand] Tangan hilang dari frame")

            # ── Gesture voting (stabilisasi output) ────────────
            self._gesture_vote.append(gesture)
            voted = Counter(self._gesture_vote).most_common(1)[0][0]
            if voted != self._last_gesture:
                if voted != Gesture.IDLE:
                    print(f"[Gesture] >> {voted.name}")
                self._last_gesture = voted
            gesture = voted

            # Overlay info
            self._draw_overlay(frame, gesture, hx, hy, hand_now)
            if landmarker is None:
                cv2.putText(frame, "Gesture detection unavailable",
                            (10, frame.shape[0] - 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 80, 255), 2)

            if self.show_preview:
                cv2.imshow("Hand Controller", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.active = False
                    break

            with self._lock:
                self.gesture = gesture
                self.hand_x  = hx
                self.hand_y  = hy
                self.frame   = frame.copy()

        if landmarker is not None:
            landmarker.close()
        cap.release()
        if self.show_preview:
            cv2.destroyAllWindows()

    @staticmethod
    def _draw_overlay(frame, gesture: Gesture, hx: float, hy: float,
                      hand_visible: bool = False):
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (0, 0), (340, 75), (0, 0, 0), -1)

        # Status deteksi tangan
        if hand_visible:
            status_txt = "TANGAN: TERDETEKSI"
            status_col = (0, 255, 80)
        else:
            status_txt = "TANGAN: tidak terlihat"
            status_col = (80, 80, 255)
        cv2.putText(frame, status_txt, (10, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_col, 2)

        cv2.putText(frame, f"Gesture: {gesture.name}", (10, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 120), 2)
        cv2.putText(frame, f"X:{hx:.2f}  Y:{hy:.2f}", (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1)

        if hand_visible:
            cx = int(hx * w)
            cy = int(hy * h)
            cv2.drawMarker(frame, (cx, cy), (0, 200, 255),
                           cv2.MARKER_CROSS, 20, 2)
