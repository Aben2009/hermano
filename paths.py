"""
Deteksi lokasi folder penting yang ASLI (Desktop, Dokumen, Downloads).
Di Windows dengan OneDrive, Desktop sering pindah ke C:\\Users\\<nama>\\OneDrive\\Desktop,
jadi kita baca langsung dari registry Windows biar gak salah alamat.
"""
import os
import platform

HOME = os.path.expanduser("~")

_REG_KEYS = {
    "desktop": "Desktop",
    "documents": "Personal",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
}

# Sebutan yang mungkin dipakai user/model -> folder asli
ALIASES = {
    "desktop": "desktop", "dekstop": "desktop", "destop": "desktop",
    "documents": "documents", "document": "documents", "dokumen": "documents",
    "my documents": "documents",
    "downloads": "downloads", "download": "downloads", "unduhan": "downloads",
}


def _from_registry(name: str):
    if platform.system() != "Windows":
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        value, _ = winreg.QueryValueEx(key, _REG_KEYS[name])
        path = os.path.expandvars(value)
        return path if os.path.isdir(path) else None
    except OSError:
        return None


def _fallback(name: str) -> str:
    onedrive = os.environ.get("OneDrive") or os.path.join(HOME, "OneDrive")
    candidates = {
        "desktop": [os.path.join(onedrive, "Desktop"), os.path.join(HOME, "Desktop")],
        "documents": [os.path.join(onedrive, "Documents"), os.path.join(onedrive, "Dokumen"),
                      os.path.join(HOME, "Documents")],
        "downloads": [os.path.join(HOME, "Downloads")],
    }[name]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[-1]


def special_folders() -> dict:
    return {name: (_from_registry(name) or _fallback(name)) for name in _REG_KEYS}


FOLDERS = special_folders()


def resolve_path(path: str) -> str:
    """Ubah path dari user/model jadi path asli.
    'desktop/tes' -> C:\\Users\\ahmad\\OneDrive\\Desktop\\tes (kalau Desktop-nya di OneDrive)."""
    path = os.path.expanduser(os.path.expandvars((path or "").strip().strip('"')))
    norm = path.replace("/", os.sep).replace("\\", os.sep)

    # 1) Path relatif yang diawali nama folder penting: "Desktop\tes", "dokumen/a.txt"
    if not os.path.isabs(norm):
        parts = norm.split(os.sep, 1)
        key = ALIASES.get(parts[0].strip().lower())
        if key:
            rest = parts[1] if len(parts) > 1 else ""
            return os.path.join(FOLDERS[key], rest) if rest else FOLDERS[key]
        return os.path.join(FOLDERS["desktop"], norm) if norm else FOLDERS["desktop"]

    # 2) Path absolut yang nebak lokasi lama, misal C:\Users\ahmad\Desktop padahal pindah ke OneDrive
    lower = norm.lower()
    for key, guess in (("desktop", "Desktop"), ("documents", "Documents"),
                       ("downloads", "Downloads")):
        guessed = os.path.join(HOME, guess)
        if (lower == guessed.lower() or lower.startswith(guessed.lower() + os.sep)) \
                and os.path.normcase(guessed) != os.path.normcase(FOLDERS[key]):
            return FOLDERS[key] + norm[len(guessed):]
    return norm


def folders_for_prompt() -> str:
    return "\n".join(f"- {k.capitalize()}: {v.replace(chr(92), '/')}" for k, v in FOLDERS.items())