import argparse

from ultralytics import YOLO


def parse_source(source: str) -> int | str:
    return int(source) if source.isdecimal() else source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Uji deteksi objek dengan model pretrained Ultralytics YOLO26."
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Indeks webcam (default: 0), atau path gambar/video.",
    )
    parser.add_argument(
        "--model",
        default="yolo26n.pt",
        help="Bobot model Ultralytics (default: yolo26n.pt).",
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
        help="Jangan tampilkan jendela hasil deteksi.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Jangan simpan hasil deteksi ke folder runs/detect/predict.",
    )
    args = parser.parse_args()

    if not 0 <= args.conf <= 1:
        parser.error("--conf harus bernilai antara 0 dan 1.")

    model = YOLO(args.model)
    class_names = model.names
    print("Label bawaan model:")
    print(", ".join(class_names.values()))
    print("\nMulai deteksi. Hasil akan disimpan oleh Ultralytics kecuali --no-save digunakan.")

    results = model.predict(
        source=parse_source(args.source),
        conf=args.conf,
        show=not args.no_show,
        save=not args.no_save,
        stream=True,
    )

    for result in results:
        if result.boxes is None or len(result.boxes) == 0:
            print(f"{result.path}: tidak ada objek terdeteksi.")
            continue

        for box in result.boxes:
            class_id = int(box.cls.item())
            confidence = float(box.conf.item())
            label = class_names[class_id]
            print(f"{result.path}: {label} ({confidence:.1%})")


if __name__ == "__main__":
    main()
