# Pembaca dokumen Hermano: cari file dan baca PDF / Word / PowerPoint / teks, per bagian.
# Isi dokumen = DATA dari luar (bisa berisi instruksi jahat), bukan perintah.
import datetime as dt
import html
import os
import re
import zipfile

from paths import FOLDERS, resolve_path

CHUNK_CHARS = 6000          # kira-kira sebanyak ini teks per sekali baca
PSEUDO_PAGE = 3000          # dokumen tanpa halaman (docx/txt) dipecah per sekian karakter
MAX_FILE_MB = 50
TEXT_EXT = {".txt", ".md", ".csv", ".json", ".log", ".py", ".html", ".xml"}
SKIP_DIRS = {"node_modules", "venv", "__pycache__", "appdata", ".git", "$recycle.bin"}


# ------------------------------------------------------------------ cari file
def find_files(query, folder=None, limit=15):
    words = [w for w in re.split(r"[\s_\-]+", (query or "").lower()) if w]
    if not words:
        return "Isi kata kunci nama file yang dicari."
    roots = [resolve_path(folder)] if folder else [FOLDERS["desktop"], FOLDERS["documents"],
                                                   FOLDERS["downloads"]]
    found = {}
    for root in dict.fromkeys(roots):
        if not os.path.isdir(root):
            continue
        base = root.rstrip("\\/").count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            if dirpath.count(os.sep) - base >= 4:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for f in filenames:
                name = f.lower().replace("_", " ").replace("-", " ")
                if all(w in name for w in words):
                    full = os.path.join(dirpath, f)
                    try:
                        found[os.path.normcase(full)] = (os.path.getmtime(full), os.path.getsize(full), full)
                    except OSError:
                        pass
    if not found:
        return f"Tidak ada file yang namanya mengandung '{query}' di Desktop/Dokumen/Downloads."
    found = sorted(found.values(), reverse=True)
    lines = [f"Ditemukan {len(found)} file (terbaru dulu):"]
    for i, (mtime, size, path) in enumerate(found[:limit], 1):
        when = dt.datetime.fromtimestamp(mtime).strftime("%d-%m-%Y")
        lines.append(f"{i}. {path} | {size / 1e6:.1f} MB | diubah {when}")
    return "\n".join(lines)


# ------------------------------------------------------------------ ekstraksi
def _xml_text(xml, para_tag):
    xml = re.sub(r"</" + para_tag + r">", "\n", xml)
    xml = re.sub(r"<w:tab/>|<a:tab/>", "\t", xml)
    text = html.unescape(re.sub(r"<[^>]+>", "", xml))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_pseudo(text):
    text = text.strip()
    return [text[i:i + PSEUDO_PAGE] for i in range(0, len(text), PSEUDO_PAGE)] or [""]


def _pages(path):
    """Return (jenis, label_unit, daftar_teks_per_halaman)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise ValueError("PDF ini dikunci password, tidak bisa dibaca.")
        return "PDF", "halaman", [(p.extract_text() or "") for p in reader.pages]
    if ext == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        return "Word", "bagian", _split_pseudo(_xml_text(xml, "w:p"))
    if ext == ".pptx":
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
            names.sort(key=lambda n: int(re.findall(r"\d+", n)[-1]))
            slides = [_xml_text(z.read(n).decode("utf-8", "ignore"), "a:p") for n in names]
        return "PowerPoint", "slide", slides
    if ext in TEXT_EXT:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return "Teks", "bagian", _split_pseudo(f.read())
    raise ValueError(f"Jenis file '{ext or '(tanpa ekstensi)'}' belum didukung. "
                     "Yang didukung: PDF, DOCX, PPTX, TXT/MD/CSV.")


def read_document(path, start_page=1):
    path = resolve_path(path)
    if not os.path.isfile(path):
        return f"File tidak ditemukan: {path}. Coba cari dulu pakai find_files."
    if os.path.getsize(path) > MAX_FILE_MB * 1e6:
        return f"File terlalu besar (> {MAX_FILE_MB} MB)."
    try:
        kind, unit, pages = _pages(path)
    except Exception as e:
        return f"Gagal membaca dokumen: {e}"
    total = len(pages)
    if total == 0:
        return "Dokumen kosong."
    start = max(1, min(int(start_page or 1), total))
    out, used, end = [], 0, start - 1
    for i in range(start - 1, total):
        text = re.sub(r"[ \t]+", " ", pages[i]).strip()
        if out and used + len(text) > CHUNK_CHARS:
            break
        out.append(f"--- {unit} {i + 1} ---\n{text[:CHUNK_CHARS]}")
        used += len(text)
        end = i + 1
    body = "\n".join(out)
    if kind == "PDF" and not body.replace("-", "").replace(unit, "").strip(" \n0123456789"):
        return (f"PDF '{os.path.basename(path)}' ({total} halaman) tidak punya teks yang bisa dibaca. "
                "Kemungkinan hasil scan/gambar (butuh OCR, belum didukung).")
    head = (f"Dokumen: {os.path.basename(path)} | {kind} | total {total} {unit} | "
            f"ditampilkan {unit} {start}-{end}")
    tail = (f"\n(Masih ada {unit} {end + 1}-{total}. Baca lanjutannya dengan start_page={end + 1}.)"
            if end < total else "\n(Sudah sampai akhir dokumen.)")
    return head + "\n" + body + tail
