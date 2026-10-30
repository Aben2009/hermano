"""
"Telinga" Hermano: rekam suara sampai kamu berhenti bicara, lalu ubah jadi teks (Whisper lokal).
Audio dikirim langsung ke Whisper sebagai array, jadi TIDAK butuh ffmpeg.
"""
import numpy as np
import sounddevice as sd
import whisper

from config import SPEECH_LANGUAGE, WHISPER_MODEL

SAMPLE_RATE = 16000
BLOCK = 1600  # 0.1 detik per blok


class Ears:
    def __init__(self, model_size: str = WHISPER_MODEL):
        print(f"[Hermano] Loading Whisper '{model_size}' (pertama kali akan download)...")
        self.model = whisper.load_model(model_size)
        self.noise_level = None
        print("[Hermano] Telinga siap.")

    def calibrate(self, seconds: float = 1.0):
        """Ukur tingkat bising ruangan biar deteksi suara lebih akurat."""
        audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                       channels=1, dtype="int16")
        sd.wait()
        self.noise_level = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        print(f"[Hermano] Kalibrasi mic selesai (noise: {self.noise_level:.0f}).")

    def record(self, max_duration: float = 15, silence_after: float = 1.2,
               wait_for_speech: float = 5) -> np.ndarray:
        """Rekam sampai ada jeda diam `silence_after` detik setelah kamu bicara."""
        if self.noise_level is None:
            self.calibrate(0.5)
        threshold = max(self.noise_level * 2.5, 300)

        chunks, started, silent_time, total = [], False, 0.0, 0.0
        print("[Hermano] 🎙️  Mendengarkan...")
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=BLOCK) as stream:
            while total < max_duration:
                block, _ = stream.read(BLOCK)
                total += BLOCK / SAMPLE_RATE
                rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))
                if rms > threshold:
                    started, silent_time = True, 0.0
                elif started:
                    silent_time += BLOCK / SAMPLE_RATE
                if started:
                    chunks.append(block.copy())
                    if silent_time >= silence_after:
                        break
                elif total >= wait_for_speech:
                    break  # gak ada yang ngomong
        if not chunks:
            return np.array([], dtype=np.float32)
        audio = np.concatenate(chunks).flatten().astype(np.float32) / 32768.0
        return audio

    def transcribe(self, audio: np.ndarray, language: str = SPEECH_LANGUAGE) -> str:
        if audio.size < SAMPLE_RATE * 0.3:  # < 0.3 detik = anggap gak ada suara
            return ""
        result = self.model.transcribe(audio, language=language, fp16=False)
        return result["text"].strip()

    def listen(self, max_duration: float = 15) -> str:
        return self.transcribe(self.record(max_duration=max_duration))


if __name__ == "__main__":
    ears = Ears()
    ears.calibrate()
    print(f"Kamu bilang: {ears.listen()}")
