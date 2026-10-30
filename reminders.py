# Pengingat Hermano yang tahan restart.
# Disimpan di database (memory_data/hermano.db). Saat Hermano nyala lagi, pengingat yang
# belum bunyi tetap ditunggu, dan yang terlewat saat Hermano mati langsung diberitahukan.
import datetime as dt
import re
import threading
import time

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]
LATE_SECONDS = 120  # telat lebih dari ini = dianggap "terlewat"


def pretty(when):
    return f"{HARI[when.weekday()]}, {when.day} {BULAN[when.month]} {when.year} jam {when:%H:%M}"


def parse_when(minutes=None, at=None, now=None):
    """Return (datetime, '') kalau valid, atau (None, pesan_error)."""
    now = now or dt.datetime.now()
    when = None
    if minutes not in (None, ""):
        try:
            m = float(minutes)
        except (TypeError, ValueError):
            return None, "minutes harus angka."
        if m <= 0:
            return None, "minutes harus lebih dari 0."
        when = now + dt.timedelta(minutes=m)
    elif at:
        text = str(at).strip().replace("T", " ").replace(".", ":")
        text = re.sub(r"\s+", " ", text)
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
            try:
                when = dt.datetime.strptime(text, fmt)
                break
            except ValueError:
                pass
        if when is None:
            try:  # cuma tanggal -> jam 09:00
                when = dt.datetime.strptime(text, "%Y-%m-%d").replace(hour=9)
            except ValueError:
                pass
        if when is None:
            try:  # cuma jam -> hari ini, atau besok kalau jamnya sudah lewat
                t = dt.datetime.strptime(text, "%H:%M").time()
                when = dt.datetime.combine(now.date(), t)
                if when <= now:
                    when += dt.timedelta(days=1)
            except ValueError:
                return None, ("Format waktu tidak dikenali. Pakai 'YYYY-MM-DD HH:MM' "
                              "(contoh 2026-11-05 20:00) atau 'HH:MM'.")
    else:
        return None, "Isi salah satu: minutes (berapa menit lagi) atau at (tanggal & jam)."
    if when <= now:
        return None, f"Waktu {pretty(when)} sudah lewat. Pilih waktu di masa depan."
    if when > now + dt.timedelta(days=366):
        return None, "Pengingat maksimal 1 tahun ke depan."
    return when, ""


class ReminderService(threading.Thread):
    def __init__(self, memory, notifier, interval=10):
        super().__init__(daemon=True)
        self.memory = memory
        self.notifier = notifier
        self.interval = interval

    def check_once(self, now=None):
        now = now or dt.datetime.now()
        for rid, due_s, message in self.memory.pending_reminders():
            try:
                due = dt.datetime.fromisoformat(due_s)
            except ValueError:
                self.memory.mark_reminder(rid, "rusak")
                continue
            if due > now:
                continue
            late = (now - due).total_seconds()
            if late > LATE_SECONDS:
                self.notifier(f"PENGINGAT TERLEWAT (dijadwalkan {pretty(due)}): {message}")
                self.memory.mark_reminder(rid, "terlewat")
            else:
                self.notifier(f"PENGINGAT: {message}")
                self.memory.mark_reminder(rid, "selesai")

    def run(self):
        while True:
            try:
                self.check_once()
            except Exception:
                pass
            time.sleep(self.interval)


def start_reminders(memory, notifier):
    svc = ReminderService(memory, notifier)
    svc.start()
    n = len(memory.pending_reminders())
    if n:
        print(f"[Hermano] {n} pengingat aktif dimuat dari database.")
    return svc
