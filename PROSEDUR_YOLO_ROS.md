# Prosedur Pembuatan Program ROS 2 YOLO (Deteksi Objek + Estimasi Titik Tengah)

**Workspace:** `~/ros2_ws`  
**Paket:** `robotika_dasar` (node YOLO) & `robotika_msgs` (pesan deteksi)  
**Perintah akhir:**

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch robotika_dasar yolo.launch.py use_camera:=true use_viewer:=true device:=cpu
```

---

## 1. Ringkasan

Program ini menghubungkan **YOLO (Ultralytics)** ke dalam **ROS 2 Jazzy** untuk:

1. Berlangganan gambar kamera dari topik `image_raw`.
2. Menjalankan inferensi `yolo26n.pt` pada setiap frame.
3. Menerbitkan **gambar beranotasi** ke topik `yolo/annotated`.
4. Menerbitkan **data deteksi terstruktur** ke topik `yolo/detections`, lengkap dengan **titik tengah** objek (`center_x`, `center_y`) dan **offset terhadap pusat kamera** (`offset_x`, `offset_y`) — dasar untuk kendali end-effector pada riset ROV.

**Alur data:**

```
 ┌──────────────┐   /image_raw    ┌──────────────┐   /yolo/annotated   ┌────────────────┐
 │  v4l2_camera │ ──────────────▶ │  yolo_node   │ ──────────────────▶ │ rqt_image_view │
 │  (kamera)    │                 │  (YOLO26n)   │                     └────────────────┘
 └──────────────┘                 │              │   /yolo/detections   ┌────────────────┐
                                  │              │ ──────────────────▶ │  konsumen /    │
                                  └──────────────┘   DetectionArray    │  kontrol robot │
                                                                       └────────────────┘
```

---

## 2. Lingkungan Sistem

| Komponen | Versi |
|---|---|
| OS | Ubuntu 24.04.3 LTS (kernel 6.14) |
| ROS 2 | Jazzy (ros-jazzy-ros-base 0.11.0) |
| Python | 3.12.9 (conda: `/home/angdes/miniconda3`) |
| Ultralytics | 8.4.174 |
| PyTorch | 2.6.0+cu124 (CUDA tersedia) |
| GPU | NVIDIA GeForce MX350, 2048 MiB, driver 550.163.01 |
| Kamera | `/dev/video0` (Integrated Camera) |
| Driver kamera | `v4l2_camera` (sudah terpasang) |

> **Penting:** ROS 2 Jazzy resmi memakai **Python sistem** (`/usr/bin/python3`), sedangkan
> `ultralytics` + `torch` terpasang di **Python conda**. Perbedaan ini adalah akar dari
> dua masalah yang dibahas di bagian Troubleshooting, dan solusinya sudah tertanam di
> rancangan program ini.

---

## 3. Struktur File yang Dibuat

```
~/ros2_ws/
├── run_yolo.sh                       # launcher praktis (opsional)
├── docs/
│   ├── PROSEDUR_YOLO_ROS.md          # dokumen ini
│   └── assets/                       # screenshot & capture output
└── src/
    ├── robotika_msgs/                # [BARU] paket pesan
    │   ├── package.xml
    │   ├── CMakeLists.txt
    │   └── msg/
    │       ├── Detection.msg
    │       └── DetectionArray.msg
    └── robotika_dasar/               # [DIUBAH] paket node
        ├── package.xml
        ├── setup.py
        ├── launch/
        │   └── yolo.launch.py        # [BARU]
        └── robotika_dasar/
            ├── halo_node.py          # (sudah ada)
            └── yolo_node.py          # [BARU]
```

---

## 4. Prosedur Langkah demi Langkah

### Langkah 0 — Prasyarat dependensi build di conda

Karena build `colcon` memakai Python conda (agar konsisten dengan runtime), dua paket
build ROS berikut perlu ada di conda:

```bash
python3 -m pip install empy==3.3.4 catkin_pkg lark
```
`empy` (modul `em`) dibutuhkan generator pesan ROS; `catkin_pkg` dibutuhkan parser
`package.xml`.

> Catatan: `empy` **harus versi 3.3.4** (menyediakan modul `em`). Versi 4.x mengganti
> nama modul dan akan gagal dengan `ModuleNotFoundError: No module named 'em'`.

### Langkah 1 — Membuat paket pesan `robotika_msgs`

Pesan kustom dipakai agar data deteksi **terstruktur** (bukan sekadar gambar).

**`src/robotika_msgs/msg/Detection.msg`**

```text
# Satu objek terdeteksi oleh YOLO
string class_name          # nama kelas, mis. "person"
float32 score              # skor keyakinan 0..1

# bounding box dalam piksel (koordinat gambar)
float32 x_min
float32 y_min
float32 x_max
float32 y_max

# titik tengah deteksi (u, v) dalam piksel
float32 center_x
float32 center_y

# offset titik tengah deteksi terhadap pusat kamera (center - image_center)
float32 offset_x
float32 offset_y
```

**`src/robotika_msgs/msg/DetectionArray.msg`**

```text
# Hasil deteksi YOLO untuk satu frame
std_msgs/Header header

uint32 image_width
uint32 image_height

Detection[] detections
```

**`src/robotika_msgs/package.xml`**

```xml
<?xml version="1.0"?>
<package format="3">
  <name>robotika_msgs</name>
  <version>0.0.0</version>
  <description>Pesan deteksi objek (YOLO) untuk paket robotika_dasar</description>
  <maintainer email="gramandha.wega@gmail.com">angdes</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  <buildtool_depend>rosidl_default_generators</buildtool_depend>

  <depend>std_msgs</depend>
  <exec_depend>rosidl_default_runtime</exec_depend>

  <member_of_group>rosidl_interface_packages</member_of_group>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

**`src/robotika_msgs/CMakeLists.txt`**

```cmake
cmake_minimum_required(VERSION 3.8)
project(robotika_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Detection.msg"
  "msg/DetectionArray.msg"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
```

### Langkah 2 — Membuat node YOLO

**`src/robotika_dasar/robotika_dasar/yolo_node.py`**

```python
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from ultralytics import YOLO

from robotika_msgs.msg import Detection, DetectionArray


def imgmsg_to_bgr(msg):
    arr = np.frombuffer(msg.data, dtype=np.uint8)
    channels = msg.step // msg.width
    img = arr.reshape(msg.height, msg.width, channels)
    if msg.encoding == 'rgb8':
        img = img[:, :, ::-1]
    elif msg.encoding in ('mono8', '8UC1'):
        return np.repeat(img, 3, axis=2)
    return np.ascontiguousarray(img)

def bgr_to_imgmsg(frame, header):
    frame = np.ascontiguousarray(frame)
    msg = Image()
    msg.header = header
    msg.height, msg.width = frame.shape[:2]
    msg.encoding = 'bgr8'
    msg.is_bigendian = 0
    msg.step = frame.shape[1] * frame.shape[2]
    msg.data = frame.tobytes()
    return msg


class YoloNode(Node):
    def __init__(self):
        super().__init__('yolo_node')

        self.declare_parameter('model', 'yolo26n.pt')
        self.declare_parameter('device', 'cuda:0')
        self.declare_parameter('conf', 0.4)
        self.declare_parameter('image_topic', 'image_raw')

        model_name = self.get_parameter('model').value
        self.device = self.get_parameter('device').value
        self.conf = self.get_parameter('conf').value
        topic = self.get_parameter('image_topic').value

        self.model = YOLO(model_name)

        self.sub = self.create_subscription(
            Image, topic, self.on_image, qos_profile_sensor_data)
        self.pub_img = self.create_publisher(Image, 'yolo/annotated', 5)
        self.pub_det = self.create_publisher(DetectionArray, 'yolo/detections', 5)
        self.get_logger().info(
            f'YoloNode siap (model={model_name}, device={self.device})')

    def on_image(self, msg):
        frame = imgmsg_to_bgr(msg)
        result = self.model.predict(
            frame, conf=self.conf, device=self.device, verbose=False)[0]
        annotated = result.plot()

        height, width = frame.shape[:2]
        cam_cx, cam_cy = width / 2.0, height / 2.0

        det_array = DetectionArray()
        det_array.header = msg.header
        det_array.image_width = width
        det_array.image_height = height

        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            u, v = (x1 + x2) / 2.0, (y1 + y2) / 2.0

            det = Detection()
            det.class_name = self.model.names[int(box.cls[0])]
            det.score = float(box.conf[0])
            det.x_min = float(x1)
            det.y_min = float(y1)
            det.x_max = float(x2)
            det.y_max = float(y2)
            det.center_x = float(u)
            det.center_y = float(v)
            det.offset_x = float(u - cam_cx)
            det.offset_y = float(v - cam_cy)
            det_array.detections.append(det)

            self.get_logger().info(
                f'{det.class_name} conf={det.score:.2f} '
                f'pusat=({u:.0f},{v:.0f}) offset=({det.offset_x:.0f},{det.offset_y:.0f}) px')

        self.pub_det.publish(det_array)
        self.pub_img.publish(bgr_to_imgmsg(annotated, msg.header))


def main(args=None):
    rclpy.init(args=args)
    node = YoloNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
```

**Poin kunci konversi gambar:**

- `imgmsg_to_bgr()` mengganti peran `cv_bridge` (lihat Troubleshooting #2). Gambar
  `sensor_msgs/Image` dibaca langsung dari buffer byte lalu di-reshape menjadi array
  NumPy `(H, W, C)`, dan `rgb8` → `bgr8` bila perlu.
- `bgr_to_imgmsg()` mengubah kembali array OpenCV menjadi pesan ROS untuk diterbitkan.
- Titik tengah dihitung dari bounding box: `u = (x1+x2)/2`, `v = (y1+y2)/2`, lalu
  offset = titik tengah − pusat kamera `(width/2, height/2)`.

### Langkah 3 — Mendaftarkan dependensi & entry point

**`src/robotika_dasar/package.xml`** (bagian dependensi)

```xml
 <exec_depend>rclpy</exec_depend>
 <exec_depend>std_msgs</exec_depend>
 <exec_depend>sensor_msgs</exec_depend>
 <exec_depend>python3-opencv</exec_depend>
 <exec_depend>robotika_msgs</exec_depend>
 <exec_depend>launch</exec_depend>
 <exec_depend>launch_ros</exec_depend>
 <exec_depend>v4l2_camera</exec_depend>
```

**`src/robotika_dasar/setup.py`** (bagian penting)

```python
import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'robotika_dasar'

setup(
    ...
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    ...
    entry_points={
        'console_scripts': [
            'halo_node = robotika_dasar.halo_node:main',
            'yolo_node = robotika_dasar.yolo_node:main',
        ],
    },
)
```

### Langkah 4 — Membuat launch file

**`src/robotika_dasar/launch/yolo.launch.py`**

```python
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _enabled(value):
    return value.lower() in ('true', '1', 'yes', 'on')


def launch_setup(context, *args, **kwargs):
    python = LaunchConfiguration('python').perform(context)
    model = LaunchConfiguration('model').perform(context)
    device = LaunchConfiguration('device').perform(context)
    conf = LaunchConfiguration('conf').perform(context)
    image_topic = LaunchConfiguration('image_topic').perform(context)
    video_device = LaunchConfiguration('video_device').perform(context)
    use_camera = LaunchConfiguration('use_camera').perform(context)
    use_viewer = LaunchConfiguration('use_viewer').perform(context)

    actions = []

    # Node YOLO dijalankan lewat modul Python (bukan `ros2 run`) karena butuh
    # ultralytics/torch yang terpasang di Python conda.
    actions.append(ExecuteProcess(
        cmd=[
            python, '-m', 'robotika_dasar.yolo_node',
            '--ros-args',
            '-p', f'model:={model}',
            '-p', f'device:={device}',
            '-p', f'conf:={conf}',
            '-p', f'image_topic:={image_topic}',
        ],
        output='screen',
    ))

    if _enabled(use_camera):
        actions.append(Node(
            package='v4l2_camera',
            executable='v4l2_camera_node',
            name='v4l2_camera',
            parameters=[{'video_device': video_device}],
            output='screen',
        ))

    if _enabled(use_viewer):
        actions.append(ExecuteProcess(
            cmd=['ros2', 'run', 'rqt_image_view', 'rqt_image_view', '/yolo/annotated'],
            output='screen',
        ))

    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='yolo26n.pt'),
        DeclareLaunchArgument('device', default_value='cuda:0'),
        DeclareLaunchArgument('conf', default_value='0.4'),
        DeclareLaunchArgument('image_topic', default_value='image_raw'),
        DeclareLaunchArgument('python', default_value='python3'),
        DeclareLaunchArgument('use_camera', default_value='false'),
        DeclareLaunchArgument('video_device', default_value='/dev/video0'),
        DeclareLaunchArgument('use_viewer', default_value='false'),
        OpaqueFunction(function=launch_setup),
    ])
```

> **Mengapa `ExecuteProcess` bukan `Node`?** Karena `ros2 run` menjalankan executable
> dengan shebang `/usr/bin/python3` (Python sistem, tanpa ultralytics). Dengan
> `ExecuteProcess` + `python3 -m robotika_dasar.yolo_node`, node dijalankan memakai
> Python conda yang memiliki ultralytics/torch. Kamera & viewer tetap memakai `Node`
> biasa karena tidak butuh paket conda.

### Langkah 5 — Build workspace

```bash
cd ~/ros2_ws
colcon build --packages-select robotika_msgs robotika_dasar
source install/setup.bash
```

**Hasil build (screenshot):**

![colcon build](assets/screenshot_build.png)

### Langkah 6 — Menjalankan

```bash
ros2 launch robotika_dasar yolo.launch.py use_camera:=true use_viewer:=true device:=cpu
```

**Output saat berjalan (screenshot):**

![ros2 launch](assets/screenshot_launch.png)

Terlihat: `v4l2_camera` mendeteksi kamera `Integrated Camera` pada `YUYV @ 640x480`,
`YoloNode siap`, lalu deteksi `person conf=0.90 pusat=(313,286) offset=(-7,46) px`.

---

## 5. Verifikasi Hasil

### 5.1 Daftar topik & definisi pesan

![topik & interface](assets/screenshot_topics.png)

### 5.2 Membaca data deteksi terstruktur

```bash
ros2 topic echo /yolo/detections --once
```

![echo detections](assets/screenshot_echo.png)

Contoh isi (satu frame dari kamera 640×480):

```yaml
header:
  frame_id: camera
image_width: 640
image_height: 480
detections:
- class_name: person
  score: 0.898
  x_min: 252.79
  y_min: 269.15
  x_max: 518.76
  y_max: 479.81
  center_x: 385.78     # titik tengah objek (u)
  center_y: 374.48     # titik tengah objek (v)
  offset_x: 65.78      # center_x - 640/2
  offset_y: 134.48     # center_y - 480/2
- class_name: bottle
  score: 0.428
  ...
```

### 5.3 Laju publikasi gambar beranotasi

```bash
ros2 topic hz /yolo/annotated
```

![hz annotated](assets/screenshot_hz.png)

Diperoleh **≈ 6.9 Hz** pada CPU (interval ~0.045–0.574 s), cukup untuk uji fungsi.
`device:=cuda:0` tersedia bila ingin mempercepat.

### 5.4 Hasil deteksi beranotasi (screenshot program)

Contoh keluaran visual `result.plot()` dari YOLO26n (gambar uji `bus.jpg`):

![hasil deteksi](assets/screenshot_deteksi.png)

---

## 6. Prosedur Menjalankan dengan Kamera `v4l2_camera` (Live Capture)

Bagian ini menjelaskan cara menjalankan sistem **langsung dari kamera perangkat** dan
**menangkap hasilnya** (frame mentah + frame beranotasi YOLO) menjadi berkas gambar.
Seluruh gambar pada bagian ini **diambil langsung dari kamera perangkat** saat dokumen
ini disusun.

### 6.1 Pastikan kamera terdeteksi

```bash
ls /dev/video*                 # mis. /dev/video0 /dev/video1
v4l2-ctl --list-devices        # opsional, bila v4l-utils terpasang
```

Driver `v4l2_camera` sudah tersedia (terpasang bersama ROS 2 Jazzy), sehingga **tidak
perlu** memasang `usb_cam`.

### 6.2 Jalankan (satu perintah)

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch robotika_dasar yolo.launch.py use_camera:=true use_viewer:=true device:=cpu
```

Yang dijalankan launch:

1. `v4l2_camera_node` → menerbitkan gambar kamera ke `image_raw` (default `/dev/video0`).
2. `yolo_node` → inferensi YOLO26n → `yolo/annotated` + `yolo/detections`.
3. `rqt_image_view /yolo/annotated` (bila `use_viewer:=true`) → jendela tampilan langsung.

Saat berjalan, terlihat log kamera mendeteksi perangkat dan node deteksi siap:

```text
[v4l2_camera_node-2] [INFO] [v4l2_camera]: Device: Integrated Camera: Integrated C
[v4l2_camera_node-2] [INFO] [v4l2_camera]: Current pixel format: YUYV @ 640x480
[python3-1] [INFO] [yolo_node]: YoloNode siap (model=yolo26n.pt, device=cpu)
[python3-1] [INFO] [yolo_node]: person conf=0.89 pusat=(300,302) offset=(-20,62) px
```

> Catatan kamera alternatif: ganti dengan `video_device:=/dev/video1`, atau ubah
> resolusi dengan menambahkan parameter `image_size` pada node `v4l2_camera`.

### 6.3 Menangkap hasil langsung ke file gambar

Saat sistem berjalan, buka **terminal kedua**, source lingkungan, lalu jalankan skrip
penangkap frame (`docs/capture_frame.py`) untuk menyimpan **satu frame** dari topik mana
pun:

```bash
source /opt/ros/jazzy/setup.bash && source ~/ros2_ws/install/setup.bash

# frame mentah dari kamera
python3 ~/ros2_ws/docs/capture_frame.py /image_raw          ~/kamera_raw.png

# frame beranotasi hasil YOLO (ada kotak + label)
python3 ~/ros2_ws/docs/capture_frame.py /yolo/annotated     ~/kamera_annotated.png
```

Skrip penangkap (`docs/capture_frame.py`) — menyimpan frame pertama yang diterima:

```python
import sys
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

topic = sys.argv[1] if len(sys.argv) > 1 else '/yolo/annotated'
out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/opencode/capture.png'


class Capture(Node):
    def __init__(self):
        super().__init__('frame_capture')
        self.done = False
        self.sub = self.create_subscription(
            Image, topic, self.cb, qos_profile_sensor_data)

    def cb(self, msg):
        if self.done:
            return
        arr = np.frombuffer(msg.data, dtype=np.uint8)
        img = arr.reshape(msg.height, msg.width, msg.step // msg.width)
        if msg.encoding == 'rgb8':
            img = img[:, :, ::-1]
        cv2.imwrite(out, np.ascontiguousarray(img))
        self.get_logger().info(
            f'saved {out} ({msg.width}x{msg.height}, {msg.encoding})')
        self.done = True


def main():
    rclpy.init()
    node = Capture()
    while rclpy.ok() and not node.done:
        rclpy.spin_once(node, timeout_sec=1.0)
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
```

> **Mengapa QoS `sensor_data`?** Kamera menerbitkan `image_raw` dengan QoS sensor
> (best-effort). Subscriber memakai profil yang sama agar cocok dan tidak kehilangan
> pesan.

### 6.4 Hasil tangkapan langsung dari perangkat

**Frame mentah (`/image_raw`, 640×480):**

![kamera mentah](assets/kamera_raw.png)

**Frame beranotasi (`/yolo/annotated`) — objek diberi kotak & label:**

![kamera beranotasi](assets/kamera_annotated.png)

**Perbandingan berdampingan (mentah ⇆ beranotasi):**

![kamera hasil](assets/kamera_hasil.png)

Deteksi yang terbaca pada frame kamera saat pengambilan:

| Kelas | Score | center (u,v) | offset (du,dv) | Catatan |
|---|---|---|---|---|
| person | 0.89 | (300, 302) | (-20, 62) | kotak hijau |

Contoh pesan terstruktur dari kamera nyata (640×480):

```yaml
image_width: 640
image_height: 480
detections:
- class_name: person
  score: 0.89
  x_min: 43.0
  y_min: 124.0
  x_max: 556.0
  y_max: 479.0
  center_x: 300.0      # titik tengah objek (u)
  center_y: 302.0      # titik tengah objek (v)
  offset_x: -20.0      # center_x - 640/2
  offset_y: 62.0       # center_y - 480/2
```

---

## 7. Troubleshooting

### #1 — `package 'usb_cam' not found` saat `use_camera:=true`

Penyebab: launch versi awal memanggil paket `usb_cam` yang belum terpasang.
**Solusi:** ganti ke paket **`v4l2_camera`** yang sudah terpasang di sistem (tanpa
sudo). Node kamera menjadi `v4l2_camera_node` dan menerbitkan `image_raw`.

### #2 — Node crash (core dump) dengan `cv_bridge`

Gejala:

```
ImportError: A module that was compiled using NumPy 1.x cannot be run in NumPy 2.1.1
...
File ".../cv_bridge/core.py", line 194, in imgmsg_to_cv2
    res = cvtColor2(im, img_msg.encoding, desired_encoding)
timeout: the monitored command dumped core
```

Penyebab: `cv_bridge` dikompilasi terhadap **NumPy 1.x**, sedangkan conda memakai
**NumPy 2.1.1** → segfault saat `cvtColor2`.

**Solusi:** hilangkan ketergantungan `cv_bridge` dan lakukan konversi manual dengan
NumPy (`imgmsg_to_bgr` / `bgr_to_imgmsg` pada `yolo_node.py`). Efek samping: peringatan
NumPy juga hilang.

### #3 — `ros2 run robotika_dasar yolo_node` gagal: `No module named 'ultralytics'`

Penyebab: `ros2 run` memakai Python sistem, bukan conda.
**Solusi:** jalankan lewat module, mis. lewat launch file (sudah) atau:

```bash
python3 -m robotika_dasar.yolo_node --ros-args -p device:=cpu
# atau helper:
~/ros2_ws/run_yolo.sh --ros-args -p device:=cpu
```

### #4 — Pesan error kamera (boleh diabaikan)

- `Failed getting value for control ...: Permission denied` → izin kontrol kamera.
- `Failed mapping device memory` → muncul namun streaming tetap jalan.
- `Unable to open camera calibration file ...` → belum ada file kalibrasi; deteksi
  tetap berjalan (hanya `camera_info` yang kosong).

### #5 — `ModuleNotFoundError: No module named 'em' / 'catkin_pkg'` saat build

Penyebab: build memakai Python conda yang belum punya dependensi build ROS.
**Solusi:** `python3 -m pip install empy==3.3.4 catkin_pkg lark`.

---

## 8. Referensi Argumen Launch

| Argumen | Default | Keterangan |
|---|---|---|
| `model` | `yolo26n.pt` | File/nama model YOLO |
| `device` | `cuda:0` | `cuda:0` (GPU) atau `cpu` |
| `conf` | `0.4` | Ambang confidence |
| `image_topic` | `image_raw` | Topik gambar masukan |
| `python` | `python3` | Interpreter (harus punya ultralytics/torch) |
| `use_camera` | `false` | Jalankan driver `v4l2_camera` |
| `video_device` | `/dev/video0` | Perangkat kamera |
| `use_viewer` | `false` | Buka `rqt_image_view` untuk `/yolo/annotated` |

---

## 9. Kesimpulan

Program berhasil mengintegrasikan **YOLO26n** ke dalam **ROS 2 Jazzy** pada `~/ros2_ws`
dengan dua keluaran: gambar beranotasi (`/yolo/annotated`) dan deteksi terstruktur
(`/yolo/detections`) yang menyertakan **titik tengah objek** dan **offset terhadap pusat
kamera**. Tiga penyesuaian penting agar stabil: (1) memakai `v4l2_camera` yang sudah
tersedia, (2) mengganti `cv_bridge` dengan konversi NumPy untuk menghindari konflik
ABI NumPy 2, dan (3) menjalankan node YOLO lewat Python conda via `ExecuteProcess`.
