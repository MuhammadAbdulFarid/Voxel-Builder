"""
main.py
=======
Entry point untuk Hand Gesture Space Shooter.

Cara jalankan:
    pip install -r requirements.txt
    python main.py

Opsi:
    python main.py --camera 0       # index kamera (default 0)
    python main.py --no-preview     # sembunyikan jendela OpenCV
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Hand Gesture Space Shooter")
    parser.add_argument("--camera",     type=int, default=0,
                        help="Index kamera (default: 0)")
    parser.add_argument("--no-preview", action="store_true",
                        help="Sembunyikan jendela kamera OpenCV")
    args = parser.parse_args()

    print("=" * 55)
    print("  ✋  Hand Gesture Space Shooter")
    print("=" * 55)
    print(f"  Kamera index : {args.camera}")
    print(f"  Preview OpenCV: {'OFF' if args.no_preview else 'ON'}")
    print()
    print("  Kontrol Gesture:")
    print("    1 jari  (telunjuk)   → TEMBAK")
    print("    2 jari  (peace sign) → GESER KIRI")
    print("    3 jari               → GESER KANAN")
    print("    5 jari  (telapak)    → PERISAI (2 dtk, CD 5 dtk)")
    print("    Gerak atas/bawah     → Naik / Turun")
    print()
    print("  Keyboard:")
    print("    ENTER  → Mulai / Restart")
    print("    ESC    → Pause / Resume")
    print("    Q (di jendela OpenCV) → Keluar")
    print("=" * 55)

    from hand_controller import HandController
    from game import SpaceGame

    controller = HandController(
        camera_index=args.camera,
        show_preview=not args.no_preview,
    )

    game = SpaceGame(controller)
    game.run()


if __name__ == "__main__":
    main()
