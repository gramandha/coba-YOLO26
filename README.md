# Uji pretrained YOLO26

Program ini menggunakan model pretrained Ultralytics `yolo26n.pt` dan label
bawaan COCO. Bobot model akan diunduh otomatis oleh Ultralytics saat pertama
kali dijalankan jika belum tersedia.

## Membuat environment

Di PowerShell, dari folder proyek:

```powershell
py -3.10 -m venv yolo26
.\yolo26\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Menjalankan deteksi

Jalankan webcam default (kamera indeks `0`):

```powershell
python detect.py
```

Versi kamera yang dioptimalkan untuk FPS:

```powershell
python detect_fast.py
```

`detect_fast.py` menggunakan ukuran inference 416 piksel secara default,
melewati buffer frame agar tampilan kamera tetap realtime, dan otomatis
mengaktifkan FP16 jika GPU CUDA tersedia. FPS dan waktu inference ditampilkan
di jendela. Gunakan `--imgsz 320` untuk mencoba inference lebih cepat dengan
kemungkinan penurunan akurasi, atau `--imgsz 640` untuk detail lebih tinggi.
Keluar dengan menekan `Q` atau `Esc`.

Ekspor model ke ONNX INT8 (membutuhkan dataset YAML untuk kalibrasi):

```powershell
python convert_int8.py
```

Perintah tersebut memakai `yolo26n.pt` dan `coco8.yaml` sebagai contoh kalibrasi,
lalu membuat file ONNX INT8 di folder bobot sumber. Untuk kalibrasi yang lebih
representatif, arahkan `--data` ke YAML dataset Anda sendiri (disarankan
setidaknya 300 gambar), misalnya:

```powershell
python convert_int8.py --model yolo26n.pt --data "D:\dataset\data.yaml" --imgsz 416
```

Export membuat `yolo26n_int8.onnx`; komponen ONNX yang dibutuhkan akan dipasang
otomatis oleh Ultralytics jika belum tersedia. Hasil ONNX INT8 adalah format
model baru, bukan pengganti file `.pt`. Pastikan runtime inferensi dan perangkat
yang digunakan mendukung operator INT8; konversi INT8 tidak menjamin FPS lebih
tinggi pada setiap GPU.

Uji dengan gambar atau video:

```powershell
python detect.py --source "D:\path\ke\gambar.jpg"
python detect.py --source "D:\path\ke\video.mp4"
```

Pilih bobot model lain atau atur ambang confidence:

```powershell
python detect.py --model yolo26s.pt --conf 0.4
```

Jendela hasil deteksi ditampilkan dan hasil disimpan di `runs/detect/predict`.
Tambahkan `--no-show` untuk tidak menampilkan jendela atau `--no-save` untuk
tidak menyimpan hasil. Label kelas model dicetak di terminal sebelum inferensi;
nama label yang terdeteksi beserta confidence juga dicetak untuk setiap frame.
