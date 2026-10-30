# Hermano — Asisten AI Pribadi ala JARVIS

Hermano bisa ngobrol (teks/suara), buka & tutup aplikasi, jalanin command, kelola file,
cek status laptop, pasang timer, cari di web, dan inget hal penting tentang kamu.

**Kontrol tetap di tangan kamu:**
| Lapisan | Cara kerja |
|---|---|
| Aktivasi | Hermano cuma "bangun" kalau kamu tekan Enter (push-to-talk) atau panggil wake word |
| Izin aksi | Aksi berisiko (command, timpa/hapus file, tutup app, sleep) **wajib** kamu setujui. Ini dicek oleh kode, AI tidak bisa melewatinya |
| Blokir total | Format disk, diskpart, hapus registry, dll ditolak walaupun kamu setuju |
| Bisa di-undo | Hapus file = pindah ke Recycle Bin, bukan hapus permanen |
| Audit | Semua aksi + keputusan kamu tercatat di `memory_data/hermano.db` (tabel `actions`) |
| Strict mode | `STRICT_MODE=true` → buka app/website pun harus minta izin |

## Struktur
```
hermano/
├── .env.example      -> copy jadi .env, isi API key
├── config.py         -> semua setting
├── approval.py       -> gerbang izin (kamu yang mutusin)
├── brain.py          -> otak: Claude + tool calling
├── tools.py          -> tangan: semua aksi + level risiko
├── memory.py         -> ingatan: obrolan, catatan, audit
├── ears.py           -> telinga: rekam sampai diam + Whisper
├── mouth.py          -> mulut: TTS (offline / suara Indonesia natural)
├── wake_word.py      -> deteksi "jarvis" / custom "hermano"
├── main.py           -> jalankan ini
└── start_hermano.bat -> launcher Windows
```

## 0. Pilih otak (`BRAIN_BACKEND` di `.env`)
| Backend | Biaya | Internet | Kecerdasan |
|---|---|---|---|
| `ollama` (default) | Gratis | Gak perlu | Cukup, model kecil kadang salah pilih tool |
| `claude` | Bayar per pemakaian (saldo API) | Perlu | Jauh lebih pintar |

Ganti kapan aja cukup ubah satu baris di `.env`, tools & gerbang izin tetap sama.

### Setup Ollama (otak lokal)
1. Download & install dari **https://ollama.com/download** (pilih Windows)
2. Setelah install, Ollama jalan otomatis di background (ada ikon llama di taskbar)
3. Buka terminal, download modelnya (sekali aja, ±4,7GB untuk 7b):
   ```bash
   ollama pull qwen2.5:7b
   ```
   RAM cuma 8GB? Pakai `ollama pull qwen2.5:3b` lalu set `OLLAMA_MODEL=qwen2.5:3b` di `.env`.
4. Tes modelnya langsung: `ollama run qwen2.5:7b` → ketik "halo" → `/bye` untuk keluar

## 1. Setup project
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Buka `.env`, cek `BRAIN_BACKEND`, `OLLAMA_MODEL`, dan `USER_NAME`.
(Kalau pakai Claude: isi `ANTHROPIC_API_KEY` dari console.anthropic.com.)

## 2. Tes otak
```bash
python brain.py
```
Kalau Hermano bisa jawab, otaknya aman.

## 3. Mode teks + tools
```bash
python main.py text
```
Coba: `jam berapa?`, `cek baterai laptop`, `bukain notepad`, `ingat ya project aktif gw TrashChain`,
`ingetin gw 5 menit lagi minum`, `bikin folder test di desktop` (ini bakal minta izin).

## 4. Tes telinga & mulut
```bash
python ears.py
python mouth.py
```
Whisper download model ±150MB saat pertama kali. **Tidak butuh ffmpeg.**
Kalau suaranya logat Inggris, set `TTS_ENGINE=edge` di `.env` (butuh internet, suara Indonesia natural).

## 5. Mode suara penuh
```bash
python main.py voice
```
Alur: tekan Enter → bilang perintah → Hermano jawab → kamu bisa langsung lanjut ngomong
(mode percakapan) → diam beberapa detik atau bilang "standby" untuk berhenti.

### Wake word (opsional)
1. Daftar gratis di https://console.picovoice.ai, isi `PICOVOICE_ACCESS_KEY`
2. Set `ACTIVATION=wake_word` → panggil "Jarvis"
3. Custom "Hermano": bikin di dashboard Porcupine, download `.ppn` (Windows), taruh di folder
   project, isi `WAKE_WORD_PATH=nama_file.ppn`

> Pakai wake word = orang lain / video di sekitar juga bisa manggil Hermano. Karena itu
> `APPROVAL_METHOD=keyboard` direkomendasikan supaya aksi berisiko tetap harus lewat kamu.

## 6. Auto-start pas laptop nyala
1. `Win + R` → `shell:startup` → Enter
2. Taruh **shortcut** ke `start_hermano.bat` di folder itu
3. (Opsional) klik kanan shortcut → Properties → Run: **Minimized**

Jangan pakai `pythonw`: jendela terminal dibutuhkan untuk tombol Enter dan persetujuan y/n.

## Fitur opsional
- **Mute/unmute volume**: butuh `nircmd.exe` (nirsoft.net), taruh di `C:\Windows` atau folder di PATH.

## Nambah tool baru
1. Tambah definisi di `TOOL_DEFINITIONS` (`tools.py`)
2. Bikin method `_t_<nama_tool>` di `ToolExecutor` yang return `(hasil, decision)`
3. Tentukan risikonya: pakai `self._allowed(SAFE, ...)` atau `self._allowed(CONFIRM, ...)`

## Troubleshooting
| Masalah | Solusi |
|---|---|
| "Gak bisa nyambung ke Ollama" | Buka aplikasi Ollama (cek ikon llama di taskbar) |
| "Model belum di-download" | `ollama pull <nama_model>` sesuai `OLLAMA_MODEL` |
| Jawaban lokal lambat banget | Pakai `qwen2.5:3b`, tutup aplikasi berat, atau turunkan `OLLAMA_NUM_CTX=4096` |
| Model lokal salah pilih tool / ngaco | Normal untuk model kecil. Coba `qwen2.5:7b` / `llama3.1:8b`, atau pakai Claude |
| Saldo Claude habis | Isi di console.anthropic.com, atau `BRAIN_BACKEND=ollama` |
| API key error | Pastikan file bernama `.env` (bukan `_env` / `.env.example`) |
| Whisper lambat | `WHISPER_MODEL=tiny` |
| Hermano gak nangkep suara | Ruangan bising → jalankan ulang biar kalibrasi mic ulang, cek izin mic di Windows |
| Perintah kepotong | Ngomong tanpa jeda panjang; jeda >1,2 detik dianggap selesai |
| Model error 404 | Ganti `MODEL_NAME` di `.env` ke model yang tersedia di akun kamu |

**Keamanan:** jangan pernah upload `.env` ke GitHub atau share ke orang. `.gitignore` sudah disiapkan.
