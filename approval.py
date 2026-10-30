"""
Gerbang Kontrol Hermano.

Prinsip: keputusan "boleh atau tidak" dipegang KAMU, bukan AI.
AI cuma bisa MINTA izin. Kode di sini yang benar-benar nanya ke kamu,
dan AI tidak punya cara untuk melewatinya.
"""
from config import APPROVAL_METHOD, VOICE_APPROVAL_PHRASE

YES_WORDS = {"y", "ya", "yes", "iya", "ok", "oke"}


class ApprovalGate:
    def __init__(self, method: str = APPROVAL_METHOD, ears=None, mouth=None):
        self.method = method
        self.ears = ears
        self.mouth = mouth
        if self.method == "voice" and (ears is None or mouth is None):
            # Tanpa mic/speaker, fallback ke keyboard
            self.method = "keyboard"

    def request(self, description: str) -> bool:
        """Tanya persetujuan user. Return True kalau disetujui."""
        if self.method == "voice":
            return self._ask_voice(description)
        return self._ask_keyboard(description)

    def _ask_keyboard(self, description: str) -> bool:
        print("\n" + "=" * 60)
        print("⚠️  HERMANO MINTA IZIN")
        print(description)
        print("=" * 60)
        try:
            answer = input("Setujui aksi ini? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        approved = answer in YES_WORDS
        print("✅ Disetujui." if approved else "❌ Ditolak.")
        return approved

    def _ask_voice(self, description: str) -> bool:
        print("\n⚠️  HERMANO MINTA IZIN:\n" + description)
        self.mouth.speak(
            f"Saya perlu izin. {description}. "
            f"Ucapkan '{VOICE_APPROVAL_PHRASE}' untuk lanjut."
        )
        heard = self.ears.listen(max_duration=6).lower()
        print(f"[Izin] Terdengar: '{heard}'")
        approved = VOICE_APPROVAL_PHRASE in heard and "tidak" not in heard
        self.mouth.speak("Oke, saya kerjakan." if approved else "Dibatalkan.")
        return approved
