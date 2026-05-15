# ✋ Hand Gesture Space Shooter

Game Space Shooter yang dikendalikan penuh lewat gestur tangan menggunakan **MediaPipe** + **TensorFlow** + **Pygame**.

---

## 🗂 Struktur File

```
hand_game/
├── main.py              ← Entry point
├── hand_controller.py   ← Deteksi gestur (MediaPipe + TF)
├── game.py              ← Game engine (Pygame)
└── requirements.txt
```

---

## 🚀 Instalasi

```bash
# Buat virtual environment (direkomendasikan)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependensi
pip install -r requirements.txt
```

> **Catatan:** TensorFlow opsional. Jika tidak terinstall, sistem otomatis pakai rule-based classifier yang sama akuratnya untuk gesture dasar.

---

## ▶️ Menjalankan Game

```bash
python main.py
```

**Opsi tambahan:**
```bash
python main.py --camera 1        # Gunakan kamera index 1
python main.py --no-preview      # Sembunyikan jendela OpenCV
```

---

## 🎮 Kontrol Gesture

| Gesture | Aksi |
|---------|------|
| ☝ Telunjuk berdiri (jari lain tutup) | **TEMBAK** |
| 🖐 Semua jari terbuka (open palm) | **PERISAI** (2 dtk, cooldown 5 dtk) |
| ↔ Geser tangan kiri/kanan | **Gerak pesawat horizontal** |
| ↕ Geser tangan atas/bawah | **Gerak pesawat vertikal** |

**Keyboard:**
- `ENTER` → Mulai / Restart
- `ESC` → Pause / Resume
- `Q` (di jendela OpenCV) → Keluar

---

## 🏗 Arsitektur

### `hand_controller.py`

```
Kamera (thread background)
    ↓
MediaPipe Hands (21 landmark)
    ↓
GestureClassifier
    ├── TensorFlow MLP (jika tersedia + sudah di-train)
    └── Rule-based fallback (default)
    ↓
HandController (gesture, hand_x, hand_y)
    ↓ (dibaca tiap frame oleh game)
```

### Pipeline Gesture Detection

1. **Landmark extraction** — MediaPipe menghasilkan 21 titik (x, y, z) per tangan
2. **Normalisasi** — Relatif terhadap wrist, diskalakan ke bounding box
3. **Klasifikasi** — Rule-based: hitung jari yang berdiri (tip.y < pip.y)
4. **Motion detection** — Delta posisi wrist dibandingkan frame sebelumnya (smoothed 5 frame)
5. **Output** — Enum `Gesture` dikirim ke game loop

### `game.py` — Sistem Game

- **State machine**: MENU → PLAYING → PAUSED / DEAD / WIN
- **Wave system**: 3 wave per level, 5 level total
- **3 tipe musuh**: Diamond (HP=1), Hexagon (HP=2), Boss (HP=6+)
- **Spread shot**: Aktif di level ≥ 3 (3 peluru sekaligus)
- **Particle system**: Efek ledakan menggunakan partikel fisika sederhana
- **Parallax stars**: Bintang bergerak dengan kecepatan berbeda

---

## 🔧 Fine-tuning Model TensorFlow

Untuk training model gesture kustom:

```python
from hand_controller import GestureClassifier, Gesture
import numpy as np

clf = GestureClassifier(use_tf=True)

# Kumpulkan data training
# X: array (N, 63) — normalized landmarks
# y: array (N,)   — index Gesture enum

X_train = np.load("gesture_features.npy")
y_train = np.load("gesture_labels.npy")

clf.model.fit(X_train, y_train, epochs=50, batch_size=32)
clf.model.save("gesture_model.h5")
clf.use_tf = True   # aktifkan setelah training
```

---

## 🐛 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Kamera tidak terbuka | Coba `--camera 1` atau `--camera 2` |
| FPS rendah | Tutup aplikasi lain, kurangi resolusi kamera |
| Gesture tidak terdeteksi | Pastikan pencahayaan cukup, tangan di depan kamera |
| `ModuleNotFoundError: mediapipe` | `pip install mediapipe` |
| TF tidak mau install | Gunakan Python 3.8–3.11, atau lewati (rule-based tetap jalan) |

---

## 📄 Lisensi

MIT — bebas dimodifikasi dan didistribusikan.
