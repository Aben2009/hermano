"""
"Mulut" Hermano.
- pyttsx3 : offline, gratis, suara agak robot
- edge    : online, gratis, suara Indonesia natural (id-ID-ArdiNeural / id-ID-GadisNeural)
"""
import asyncio
import os
import re
import tempfile
import threading

from config import EDGE_VOICE, TTS_ENGINE


def clean_for_speech(text: str) -> str:
    """Buang markdown/emoji biar gak dibacain simbolnya."""
    text = re.sub(r"```.*?```", " (kodenya saya tampilkan di layar) ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)      # [teks](link)
    text = re.sub(r"[*_#>|~]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.M)
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", text)  # emoji
    return re.sub(r"\s+", " ", text).strip()


class Mouth:
    def __init__(self, engine: str = TTS_ENGINE, rate: int = 175):
        self.engine_name = engine
        self.rate = rate
        self.lock = threading.Lock()  # biar timer & jawaban gak ngomong barengan
        if engine == "edge":
            try:
                import edge_tts  # noqa: F401
                import pygame
                pygame.mixer.init()
            except Exception as e:
                print(f"[Hermano] Edge TTS gagal ({e}), pakai pyttsx3.")
                self.engine_name = "pyttsx3"

    def speak(self, text: str):
        print(f"🤖 Hermano: {text}")
        spoken = clean_for_speech(text)
        if not spoken:
            return
        with self.lock:
            try:
                if self.engine_name == "edge":
                    self._speak_edge(spoken)
                else:
                    self._speak_pyttsx3(spoken)
            except Exception as e:
                print(f"[Hermano] Gagal bicara: {e}")

    def _speak_pyttsx3(self, text: str):
        import pyttsx3
        # Init ulang tiap kali: menghindari bug pyttsx3 di Windows yang "diam" setelah ucapan pertama
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        for voice in engine.getProperty("voices"):
            langs = str(voice.languages).lower()
            if "indones" in (voice.name or "").lower() or "id_" in langs or "id-" in langs:
                engine.setProperty("voice", voice.id)
                break
        engine.say(text)
        engine.runAndWait()
        engine.stop()

    def _speak_edge(self, text: str):
        import edge_tts
        import pygame
        path = os.path.join(tempfile.gettempdir(), "hermano_tts.mp3")
        asyncio.run(edge_tts.Communicate(text, EDGE_VOICE).save(path))
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
        pygame.mixer.music.unload()


if __name__ == "__main__":
    Mouth().speak("Halo, saya **Hermano**. Semua sistem siap 🚀")
