"""
Konfigurasi Hermano.
Semua setting dibaca dari file .env (lihat .env.example).
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "ya", "on")


# --- Otak (backend AI) ---
# "ollama" : model AI lokal di laptop (gratis, offline)
# "claude" : Claude API (lebih pintar, butuh saldo API)
BRAIN_BACKEND = os.getenv("BRAIN_BACKEND", "ollama").lower()

# Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "16384"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
# Ganti model otomatis: OLLAMA_MODEL saat dicas, OLLAMA_MODEL_BATTERY saat pakai baterai
OLLAMA_AUTO_MODEL = _bool("OLLAMA_AUTO_MODEL", True)
OLLAMA_MODEL_BATTERY = os.getenv("OLLAMA_MODEL_BATTERY", "qwen2.5:7b")

# --- API ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-6")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))

# --- Identitas ---
ASSISTANT_NAME = "Hermano"
USER_NAME = os.getenv("USER_NAME", "Boss")

# --- Mode ---
# "text"  : ngetik di terminal (buat testing)
# "voice" : ngomong pakai mic + speaker
RUN_MODE = os.getenv("RUN_MODE", "text").lower()

# Cara memanggil Hermano di mode suara:
# "push_to_talk" : tekan Enter dulu baru ngomong (paling aman, kontrol penuh di kamu)
# "wake_word"    : panggil pakai suara ("jarvis" / custom "hermano")
ACTIVATION = os.getenv("ACTIVATION", "push_to_talk").lower()

# --- Kontrol / izin ---
# "keyboard" : persetujuan aksi lewat ketik y/n di terminal (paling aman)
# "voice"    : persetujuan lewat ucapan kata sandi (lebih praktis, kurang aman)
APPROVAL_METHOD = os.getenv("APPROVAL_METHOD", "keyboard").lower()
# Kata sandi suara untuk menyetujui aksi (dipakai kalau APPROVAL_METHOD=voice)
VOICE_APPROVAL_PHRASE = os.getenv("VOICE_APPROVAL_PHRASE", "setuju").lower()
# True = SEMUA aksi (termasuk buka aplikasi/website) harus kamu setujui dulu
STRICT_MODE = _bool("STRICT_MODE", False)

# --- Suara ---
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
SPEECH_LANGUAGE = os.getenv("SPEECH_LANGUAGE", "id")
# "pyttsx3" (offline) atau "edge" (online, suara natural bahasa Indonesia)
TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3").lower()
EDGE_VOICE = os.getenv("EDGE_VOICE", "id-ID-ArdiNeural")

# --- Wake word ---
WAKE_WORD_PATH = os.getenv("WAKE_WORD_PATH") or None  # contoh: hermano_windows.ppn
BUILT_IN_WAKE_WORD = os.getenv("BUILT_IN_WAKE_WORD", "jarvis")

# --- Batas ---
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "30"))
MAX_TOOL_STEPS = int(os.getenv("MAX_TOOL_STEPS", "10"))

# --- Keamanan ---
SECURITY_MONITOR = _bool("SECURITY_MONITOR", True)
SECURITY_CHECK_MINUTES = int(os.getenv("SECURITY_CHECK_MINUTES", "10"))

# --- Folder data ---
DATA_DIR = os.path.join(BASE_DIR, "memory_data")
os.makedirs(DATA_DIR, exist_ok=True)

if BRAIN_BACKEND == "claude" and not ANTHROPIC_API_KEY:
    print("[WARNING] ANTHROPIC_API_KEY belum diset. Cek file .env kamu.")
