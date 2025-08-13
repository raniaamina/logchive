# logchive Simple API

logchive, perkakas sederhana untuk menyimpan catatan/log, baik secara publik maupun privat, dengan dukungan kedaluwarsa otomatis dan antarmuka web sederhana untuk menilik kembali log yang telah disimpan sebelumnya.

## Fitur
- Simpan log publik dan privat
- Batas waktu kedaluwarsa log (menit, jam, hari, bulan, tahun)
- CLI untuk upload log (`logchive.py`)
- Simple web interface untuk mengakses daftar log

---

## Pemasangan

### 1. Klon Repo
```bash
git clone https://github.com/username/logchive.git
cd logchive
```

### 2. Buat dan aktifkan virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Install dependensi
```bash
pip install -r requirements.txt
```

---

## Konfigurasi

Bila diperlukan, edit file `config.py` untuk mengatur:
```python
BASE_URL = "http://localhost:8077"
ALLOWED_ORIGINS = [
    "http://localhost:8077",
    "http://127.0.0.1:8077",
]
```
---

## Menjalankan Server

```bash
uvicorn app:app --reload --port 8077
```

---

## Membuat User

```bash
curl -X POST "http://127.0.0.1:8077/register?username=fulan&password=p4ssword"

```

## CLI Upload Log

### Simpan log publik:
```bash
# Simpan dari cli output
echo "Hello World" | python logchive.py


# Upload dari file
python logchive.py -f nama-file.txt
```

### Simpan log dengan nama custom:
```bash
echo "Rahasia" | python logchive.py -n log-saya.txt
```

### Simpan log privat:
```bash
echo "Rahasia" | python logchive.py --private --login -u username -p p4ssw0rd
```

### Simpan log dengan kedaluwarsa:
```bash
echo "Catatan sementara" | python logchive.py -xp 10m
```

---

## API Endpoints

Silakan cek http://localhost:8077/redoc untuk melihat rincian endpoint yang tersedia.

---
