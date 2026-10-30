"""
Hermano - asisten AI pribadi ala JARVIS.

Jalankan:  python main.py            (mode sesuai RUN_MODE di .env)
           python main.py text       (paksa mode teks)
           python main.py voice      (paksa mode suara)

Kontrol tetap di kamu:
  - Hermano cuma "bangun" kalau kamu panggil (Enter / wake word)
  - Aksi berisiko WAJIB kamu setujui dulu (y/n di terminal, atau kata sandi suara)
  - Semua aksi tercatat di memory_data/hermano.db (tabel actions)
"""
import re
import sys

from approval import ApprovalGate
from brain import create_brain
from config import (ACTIVATION, APPROVAL_METHOD, ASSISTANT_NAME, BRAIN_BACKEND,
                    MODEL_NAME, OLLAMA_MODEL, RUN_MODE, STRICT_MODE, USER_NAME)
from memory import Memory
from tools import TOOL_DEFINITIONS, ToolExecutor
from security import start_security_monitor
from reminders import start_reminders

EXIT_WORDS = {"exit", "keluar", "quit"}
SLEEP_PHRASES = ("istirahat", "cukup dulu", "standby", "tidur dulu")


def banner(mode: str, activation: str = "-", approval: str = "keyboard"):
    print("=" * 60)
    model = OLLAMA_MODEL if BRAIN_BACKEND == "ollama" else MODEL_NAME
    print(f"  {ASSISTANT_NAME.upper()} ONLINE  |  mode: {mode}  |  otak: {BRAIN_BACKEND} ({model})")
    print(f"  Aktivasi: {activation}  |  Izin aksi: {approval}"
          f"{'  |  STRICT MODE' if STRICT_MODE else ''}")
    print("  Ketik/ucapkan 'reset' untuk hapus konteks obrolan.")
    print("=" * 60)


def warn_if_not_ready(brain):
    problem = brain.check_ready()
    if problem:
        print(f"\n[!] {problem}\n")


HISTORY_Q = re.compile(r"\b(lu|lo|loe|kamu|anda|hermano|kau)\b.{0,30}"
                       r"(ngapain|lakuin|lakukan|kerjain|kerjakan|perbuat|jalankan)\b", re.I)
PAST_MARK = re.compile(r"\b(sudah|udah|udh|dah|tadi|barusan|kemarin|hari ini|minggu ini|"
                       r"seminggu|selama|pernah)\b", re.I)


def _with_history_context(text, executor):
    """Pertanyaan 'udah ngapain aja?' -> tempel riwayat aksi ASLI dari audit, biar model tidak mengarang."""
    low = text.lower()
    if not ("riwayat aksi" in low or (HISTORY_Q.search(text) and PAST_MARK.search(text))):
        return text
    if "kemarin" in low:
        period = "kemarin"
    elif "minggu" in low or "7 hari" in low:
        period = "7_hari"
    elif "semua" in low:
        period = "semua"
    else:
        period = "hari_ini"
    data = executor("get_action_history", {"period": period})
    return (text + "\n\n[DATA SISTEM - riwayat aksi ASLI dari catatan audit. Jawab HANYA berdasarkan "
            "data ini, jangan menambah aksi lain]\n" + data)


BRIEF_Q = re.compile(r"\bbriefing\b|\b(ringkasan|rangkuman|laporan)\s+(pagi|harian|hari ini)\b", re.I)


def _with_briefing_context(text, executor):
    """'briefing' -> kumpulkan data asli dulu, model tinggal menyusun."""
    if not BRIEF_Q.search(text):
        return text
    data = executor("daily_briefing", {})
    return (text + "\n\n[DATA BRIEFING - data ASLI dari sistem. Susun jadi briefing singkat & rapi; "
            "jangan menambah info di luar data ini]\n" + data)


def handle_turn(brain, memory: Memory, executor: ToolExecutor, text: str) -> str:
    memory.log_message("user", text)
    executor.new_turn()
    reply = brain.think(_with_briefing_context(_with_history_context(text, executor), executor),
                        TOOL_DEFINITIONS, executor)
    if getattr(executor, "failed_checks", None):
        reply += ("\n\n[!] Sistem: verifikasi GAGAL untuk " + ", ".join(executor.failed_checks)
                  + ". Aksi tersebut kemungkinan TIDAK benar-benar terjadi.")
    memory.log_message("assistant", reply)
    return reply


def run_text_mode():
    memory = Memory()
    gate = ApprovalGate(method="keyboard")
    executor = ToolExecutor(gate, memory, notifier=lambda m: print(f"\n⏰ {m}\nKamu: ", end=""))
    brain = create_brain(memory=memory, voice_mode=False)
    start_security_monitor(executor.notifier)
    start_reminders(memory, executor.notifier)
    banner("teks", approval="keyboard")
    warn_if_not_ready(brain)
    print(f"Halo {USER_NAME}, ada yang bisa saya bantu? (ketik 'exit' untuk keluar)\n")

    while True:
        try:
            text = input("Kamu: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text.lower() in EXIT_WORDS:
            break
        if text.lower() == "reset":
            brain.reset()
            print(f"{ASSISTANT_NAME}: Konteks obrolan dibersihkan.\n")
            continue
        print(f"\n{ASSISTANT_NAME}: {handle_turn(brain, memory, executor, text)}\n")
    print(f"{ASSISTANT_NAME} offline. Sampai jumpa, {USER_NAME}.")


def run_voice_mode():
    from ears import Ears
    from mouth import Mouth

    memory = Memory()
    ears = Ears()
    mouth = Mouth()
    gate = ApprovalGate(method=APPROVAL_METHOD, ears=ears, mouth=mouth)
    executor = ToolExecutor(gate, memory, notifier=mouth.speak)
    brain = create_brain(memory=memory, voice_mode=True)
    start_security_monitor(executor.notifier)
    start_reminders(memory, executor.notifier)

    activation = ACTIVATION
    detector = None
    if activation == "wake_word":
        try:
            from wake_word import WakeWordDetector
            detector = WakeWordDetector()
        except Exception as e:
            print(f"[Hermano] Wake word gagal ({e}). Pindah ke push-to-talk.")
            activation = "push_to_talk"

    banner("suara", activation, gate.method)
    warn_if_not_ready(brain)
    ears.calibrate()
    mouth.speak(f"{ASSISTANT_NAME} online. Siap membantu, {USER_NAME}.")

    try:
        while True:
            # 1. Tunggu dipanggil (kontrol dari kamu)
            if activation == "wake_word":
                detector.wait_for_wake_word()
            else:
                cmd = input("\n[Tekan Enter untuk bicara, ketik 'exit' untuk keluar] ").strip().lower()
                if cmd in EXIT_WORDS:
                    break
            mouth.speak("Ya?")

            # 2. Mode percakapan: lanjut dengerin selama kamu masih ngomong
            while True:
                text = ears.listen()
                if not text:
                    print("[Hermano] (tidak ada suara, kembali standby)")
                    break
                print(f"🗣️  Kamu: {text}")
                low = text.lower()
                if any(p in low for p in SLEEP_PHRASES):
                    mouth.speak("Siap, saya standby.")
                    break
                if low.strip(" .!") == "reset":
                    brain.reset()
                    mouth.speak("Konteks obrolan dibersihkan.")
                    continue
                mouth.speak(handle_turn(brain, memory, executor, text))
    except KeyboardInterrupt:
        pass
    finally:
        if detector:
            detector.close()
        print(f"\n{ASSISTANT_NAME} offline.")


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else RUN_MODE
    if mode == "voice":
        run_voice_mode()
    else:
        run_text_mode()
