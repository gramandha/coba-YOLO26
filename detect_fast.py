import argparse
import time

import cv2
import torch
from ultralytics import YOLO


def parse_source(source: str) -> int | str:
    return int(source) if source.isdecimal() else source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deteksi kamera YOLO26 dengan pengaturan untuk inference lebih cepat."
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Indeks kamera laptop (default: 0).",
    )
    parser.add_argument(
        "--model",
        default="yolo26n.pt",
        help="Bobot model (default: yolo26n.pt).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=416,
        help="Ukuran inference; lebih kecil biasanya lebih cepat (default: 416).",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Ambang confidence 0-1 (default: 0.25).",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Jalankan inference tanpa membuka jendela tampilan.",
    )
    args = parser.parse_args()

    if args.imgsz < 32:
        parser.error("--imgsz harus minimal 32.")
    if not 0 <= args.conf <= 1:
        parser.error("--conf harus bernilai antara 0 dan 1.")

    use_half = torch.cuda.is_available()
    if use_half:
        torch.backends.cudnn.benchmark = True
        print(f"GPU: {torch.cuda.get_device_name(0)} (FP16 aktif)")
    else:
        print("GPU CUDA tidak tersedia; menggunakan CPU.")

    model = YOLO(args.model)
    print(f"Model: {args.model} | inference: {args.imgsz}px | tekan Q atau Esc untuk keluar.")

    results = model.predict(
        source=parse_source(args.source),
        imgsz=args.imgsz,
        conf=args.conf,
        quantize=16 if use_half else None,
        stream=True,
        stream_buffer=False,
        show=False,
        save=False,
        verbose=False,
    )

    previous_time = None
    smoothed_fps = 0.0
    try:
        for result in results:
            current_time = time.perf_counter()
            if previous_time is not None:
                frame_interval = current_time - previous_time
                current_fps = 1.0 / max(frame_interval, 1e-9)
                smoothed_fps = (
                    current_fps
                    if smoothed_fps == 0
                    else 0.85 * smoothed_fps + 0.15 * current_fps
                )
            previous_time = current_time

            frame = result.plot()
            cv2.putText(
                frame,
                f"FPS: {smoothed_fps:.1f}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                frame,
                f"Inference: {result.speed['inference']:.1f} ms",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            if not args.no_show:
                cv2.imshow("YOLO26 Fast - Kamera Laptop", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
    finally:
        results.close()
        if not args.no_show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
