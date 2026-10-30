# Briefing harian Hermano: semua data diambil dari sumber asli (Defender, sistem,
# database pengingat, catatan audit, berita), bukan dikarang model.
import datetime as dt
import os

import config  # noqa: F401  (memastikan .env sudah dibaca)

DEFAULT_TOPICS = "berita utama Indonesia hari ini;harga emas hari ini"
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]


def _topics():
    raw = os.getenv("BRIEFING_TOPICS", DEFAULT_TOPICS)
    return [t.strip() for t in raw.split(";") if t.strip()][:4]


def _safe(fn, fallback):
    try:
        return fn()
    except Exception as e:
        return f"{fallback} ({type(e).__name__})"


def _security():
    import security
    s = security.security_status()
    if "== Perlu perhatian ==" in s:
        return s.split("== Perlu perhatian ==", 1)[1].strip()
    if "Gagal" in s:
        return s.strip().splitlines()[0]
    return "Aman. Tidak ada masalah yang terdeteksi Windows Defender."


def _reminders(memory, now):
    rows = memory.pending_reminders() if memory else []
    today, later = [], 0
    for rid, due_s, msg in rows:
        try:
            due = dt.datetime.fromisoformat(due_s)
        except ValueError:
            continue
        if due.date() == now.date():
            today.append(f"- jam {due:%H:%M}: {msg} (#{rid})")
        else:
            later += 1
    lines = today or ["- Tidak ada pengingat untuk sisa hari ini."]
    if later:
        lines.append(f"- (+{later} pengingat lain di hari berikutnya)")
    return "\n".join(lines)


def _yesterday(memory, now):
    if not memory:
        return "Memory tidak aktif."
    start = dt.datetime.combine(now.date() - dt.timedelta(days=1), dt.time())
    end = dt.datetime.combine(now.date(), dt.time())
    rows = [r for r in memory.get_actions(start.isoformat(), end.isoformat(), limit=500)
            if r[1] not in ("get_action_history", "daily_briefing")]
    if not rows:
        return "Tidak ada aksi kemarin."
    denied = sum(1 for r in rows if (r[3] or "").startswith("denied"))
    blocked = sum(1 for r in rows if r[3] == "blocked")
    failed = sum(1 for r in rows if "[VERIFIKASI GAGAL]" in (r[4] or ""))
    tools = {}
    for r in rows:
        tools[r[1]] = tools.get(r[1], 0) + 1
    top = ", ".join(f"{k} x{v}" for k, v in sorted(tools.items(), key=lambda x: -x[1])[:5])
    return (f"{len(rows)} aksi (ditolak: {denied}, diblokir: {blocked}, verifikasi gagal: {failed}). "
            f"Paling sering: {top}")


def build(executor):
    import web
    now = dt.datetime.now()
    print("[Hermano] Menyiapkan briefing (cek Defender, sistem, berita)...")
    memory = getattr(executor, "memory", None)
    parts = [f"Tanggal: {HARI[now.weekday()]}, {now.day} {BULAN[now.month]} {now.year}, jam {now:%H:%M}"]
    parts.append("\n[KEAMANAN]\n" + _safe(_security, "Gagal membaca status Defender"))
    parts.append("\n[LAPTOP]\n" + _safe(lambda: executor._t_get_system_status()[0], "Gagal membaca status laptop"))
    parts.append(_safe(lambda: executor._t_get_network_status()[0].splitlines()[0], "Gagal cek internet"))
    parts.append("\n[PENGINGAT HARI INI]\n" + _safe(lambda: _reminders(memory, now), "Gagal membaca pengingat"))
    for topic in _topics():
        parts.append(f"\n[BERITA: {topic}]\n" +
                     _safe(lambda t=topic: web.news_search(t, max_results=3), "Gagal mengambil berita"))
    parts.append("\n[AKSI HERMANO KEMARIN]\n" + _safe(lambda: _yesterday(memory, now), "Gagal membaca riwayat"))
    return "\n".join(parts)
