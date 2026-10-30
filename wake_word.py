"""
Wake word Hermano (Picovoice Porcupine).
Default pakai kata bawaan "jarvis". Untuk custom "Hermano", isi WAKE_WORD_PATH di .env
dengan file .ppn dari https://console.picovoice.ai
"""
import os
import struct

import pvporcupine
import sounddevice as sd

from config import BASE_DIR, BUILT_IN_WAKE_WORD, PICOVOICE_ACCESS_KEY, WAKE_WORD_PATH


class WakeWordDetector:
    def __init__(self):
        if not PICOVOICE_ACCESS_KEY:
            raise RuntimeError("PICOVOICE_ACCESS_KEY belum diisi di .env")
        if WAKE_WORD_PATH:
            path = WAKE_WORD_PATH
            if not os.path.isabs(path):
                path = os.path.join(BASE_DIR, path)
            self.porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY,
                                                keyword_paths=[path])
            self.label = os.path.splitext(os.path.basename(path))[0]
        else:
            self.porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY,
                                                keywords=[BUILT_IN_WAKE_WORD])
            self.label = BUILT_IN_WAKE_WORD

    def wait_for_wake_word(self):
        """Blocking: tunggu sampai wake word terdengar.
        Mic hanya dibuka selama menunggu, jadi tidak bentrok dengan perekaman perintah."""
        print(f"[Hermano] 💤 Standby, panggil '{self.label}'...")
        n = self.porcupine.frame_length
        with sd.RawInputStream(samplerate=self.porcupine.sample_rate, blocksize=n,
                               channels=1, dtype="int16") as stream:
            while True:
                data, _ = stream.read(n)
                pcm = struct.unpack_from("h" * n, data)
                if self.porcupine.process(pcm) >= 0:
                    print("[Hermano] Wake word terdeteksi!")
                    return True

    def close(self):
        self.porcupine.delete()


if __name__ == "__main__":
    d = WakeWordDetector()
    try:
        d.wait_for_wake_word()
    finally:
        d.close()
