import argparse

import torch
from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ekspor model deteksi Ultralytics ke ONNX INT8."
    )
    parser.add_argument(
        "--model",
        default="yolo26n.pt",
        help="Bobot model sumber (default: yolo26n.pt).",
    )
    parser.add_argument(
        "--data",
        default="coco8.yaml",
        help="File YAML dataset untuk kalibrasi INT8 (default: coco8.yaml).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=416,
        help="Ukuran input export (default: 416).",
    )
    parser.add_argument(
        "--fraction",
        type=float,
        default=1.0,
        help="Proporsi dataset kalibrasi yang dipakai, antara 0 dan 1.",
    )
    args = parser.parse_args()

    if args.imgsz < 32:
        parser.error("--imgsz harus minimal 32.")
    if not 0 < args.fraction <= 1:
        parser.error("--fraction harus lebih dari 0 dan maksimal 1.")

    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"Model sumber: {args.model}")
    print(f"Dataset kalibrasi: {args.data} (fraction={args.fraction})")
    print(f"Device kalibrasi: {'CUDA GPU' if device == 0 else 'CPU'}")
    print(
        "Catatan: coco8.yaml hanya berisi sedikit gambar untuk uji coba. "
        "Untuk akurasi INT8 yang lebih baik, gunakan dataset representatif "
        "dengan setidaknya 300 gambar."
    )

    model = YOLO(args.model)
    output = model.export(
        format="onnx",
        quantize=8,
        data=args.data,
        imgsz=args.imgsz,
        fraction=args.fraction,
        device=device,
    )
    print(f"\nModel ONNX INT8 berhasil dibuat: {output}")


if __name__ == "__main__":
    main()
