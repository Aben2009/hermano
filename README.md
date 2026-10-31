# Hermano - Asisten AI Pribadi

Asisten AI yang jalan **lokal di laptop sendiri** (lewat Ollama), dengan tampilan ala ChatGPT.
Hermano bisa mengontrol laptop, mencari info di internet, membaca dokumen, memantau keamanan,
dan memasang pengingat, tapi **setiap aksi berisiko tetap harus disetujui pemiliknya**.

> Dibangun sebagai proyek belajar AI & cybersecurity. Kode dikembangkan dengan bantuan AI
> (Claude) sebagai alat pengujian, debugging, dan keputusan dilakukan sendiri.

## Fitur

| Fitur | Keterangan |
|---|---|
| Tampilan aplikasi | Jendela ala ChatGPT: riwayat chat di sidebar, dibuka lewat ikon di Desktop/Start Menu |
| Otak lokal | Ollama (`qwen2.5:14b` saat dicas, `qwen2.5:7b` saat baterai - ganti otomatis) |
| Kontrol laptop | Buka/tutup aplikasi (termasuk dari Start Menu), folder & file, status baterai/CPU/jaringan |
| Internet | Cari berita & web (DuckDuckGo/Bing, tanpa API key), baca artikel, buka hasil di browser |
| Dokumen | Cari file di laptop, baca & rangkum PDF, Word (.docx), PowerPoint (.pptx), teks |
| Keamanan | Status Windows Defender, ancaman terdeteksi/diizinkan, cek proses & startup mencurigakan, Quick Scan, penjaga otomatis tiap 10 menit |
| Pengingat | Tersimpan di database, tetap ada walau Hermano ditutup; yang terlewat diberitahukan |
| Briefing harian | Keamanan, laptop, internet, pengingat, berita, dan ringkasan aksi kemarin |
| Riwayat aksi | Semua yang pernah dilakukan Hermano, diambil dari catatan audit asli |

## Lapisan keamanan

| Lapisan | Cara kerja |
|---|---|
| Gerbang izin | Aksi berisiko (command, timpa/hapus file, tutup aplikasi, dll) muncul sebagai pop-up **Setujui / Tolak**. Dicek oleh kode, AI tidak bisa melewatinya |
| Blokir total | Format disk, diskpart, hapus registry, dll ditolak walaupun disetujui |
| Mode waspada | Setelah membaca konten luar (internet/dokumen), **semua** aksi wajib izin - melindungi dari prompt injection |
| Satpam anti-klaim palsu | Kalau AI bilang "sudah dikerjakan" tanpa benar-benar memanggil tool, kode menegur dan memberi label peringatan |
| Verifikasi aksi | Setelah aksi, kode mengecek hasil nyatanya (aplikasi benar jalan, folder benar ada, dll) |
| Tolak URL palsu | URL karangan model ditolak; hasil pencarian dibuka lewat nomor, URL asli ditampilkan di pop-up izin |
| Bisa di-undo | Hapus file = pindah ke Recycle Bin |
| Audit | Semua aksi + keputusan pengguna tercatat di database lokal |

## Struktur
hermano/
|-- gui.py -> aplikasi (tampilan ala ChatGPT)
|-- main.py -> alur percakapan + mode teks (cadangan)
|-- brain.py -> otak: Ollama / Claude + tool calling + satpam
|-- tools.py -> semua aksi, level risiko, mode waspada, verifikasi
|-- approval.py -> gerbang izin
|-- security.py -> modul keamanan (Windows Defender + heuristik)
|-- web.py -> pencarian web & berita, baca halaman
|-- docs.py -> cari file, baca PDF/DOCX/PPTX
|-- reminders.py -> pengingat tahan restart
|-- briefing.py -> briefing harian
|-- chats.py -> riwayat chat (sidebar)
|-- memory.py -> database lokal: catatan, audit, pengingat
|-- paths.py -> deteksi Desktop/Dokumen/Downloads asli (termasuk OneDrive)
|-- config.py -> semua setting (dibaca dari .env)
|-- hermano.ico/png -> ikon aplikasi
`-- start_hermano_gui.bat

Data pribadi (`.env`, `memory_data/`) **tidak** ikut ke Git.

## Instalasi (Windows)

1. Install **Python 3.11** dan **Ollama** (https://ollama.com/download).
2. Download model:
ollama pull qwen2.5:14b
ollama pull qwen2.5:7b

3. Siapkan project:
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env

4. Isi `.env` minimal:
BRAIN_BACKEND=ollama
OLLAMA_MODEL=qwen2.5:14b
USER_NAME=NamaKamu

5. Jalankan: `.\venv\Scripts\python.exe gui.py`, atau double-click `start_hermano_gui.bat`.

Mode teks (tanpa jendela): `.\venv\Scripts\python.exe main.py text`

## Setting penting (.env)

| Setting | Fungsi |
|---|---|
| `OLLAMA_MODEL` / `OLLAMA_MODEL_BATTERY` | Model saat dicas / saat baterai |
| `OLLAMA_AUTO_MODEL` | `true` = ganti model otomatis sesuai daya |
| `STRICT_MODE` | `true` = semua aksi (termasuk buka aplikasi/website) wajib izin |
| `BRIEFING_TOPICS` | Topik berita briefing, dipisah `;` |
| `SECURITY_MONITOR` / `SECURITY_CHECK_MINUTES` | Penjaga Defender otomatis |

## Troubleshooting

| Masalah | Solusi |
|---|---|
| "Gak bisa nyambung ke Ollama" | Buka aplikasi Ollama (ikon llama di taskbar) |
| Jawaban sangat lambat | Colok charger + mode Performance (GPU laptop dibatasi saat baterai) |
| Model ngaco setelah baca dokumen panjang | Klik **Chat baru**, lalu minta per bagian (misal "rangkum halaman 5-8") |
| Pencarian web hasilnya tidak relevan | Matikan VPN (mis. Cloudflare WARP) lalu coba lagi |
| Error di aplikasi | Lihat `memory_data/gui_error.log` |

## Catatan

Fitur suara (mic & speaker) sengaja **tidak** dipasang: perintah suara bisa dipicu orang lain
atau suara dari video, terlalu berisiko untuk asisten yang bisa mengontrol laptop.
