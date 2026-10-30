"""
Memory Hermano (SQLite lokal).
- conversations : histori obrolan
- notes         : hal penting yang perlu diingat jangka panjang
- actions       : catatan audit semua aksi yang Hermano lakukan / minta
"""
import os
import sqlite3
import threading
from datetime import datetime

from config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "hermano.db")


class Memory:
    def __init__(self, db_path: str = DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._setup()

    def _setup(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, role TEXT, content TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, topic TEXT, content TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, tool TEXT, input TEXT, decision TEXT, result TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created TEXT, due TEXT, message TEXT, status TEXT)""")
            self.conn.commit()

    def _exec(self, sql, params=()):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            self.conn.commit()
            return cur

    # --- Percakapan ---
    def log_message(self, role: str, content: str):
        self._exec(
            "INSERT INTO conversations (timestamp, role, content) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), role, content),
        )

    def get_recent_conversation(self, limit: int = 10):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return list(reversed(cur.fetchall()))

    # --- Catatan ---
    def save_note(self, topic: str, content: str) -> int:
        cur = self._exec(
            "INSERT INTO notes (timestamp, topic, content) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), topic, content),
        )
        return cur.lastrowid

    def get_notes(self, topic: str = None):
        with self.lock:
            cur = self.conn.cursor()
            if topic:
                cur.execute(
                    "SELECT id, topic, content FROM notes WHERE topic LIKE ? ORDER BY id DESC",
                    (f"%{topic}%",),
                )
            else:
                cur.execute("SELECT id, topic, content FROM notes ORDER BY id DESC")
            return cur.fetchall()

    def delete_note(self, note_id: int) -> bool:
        cur = self._exec("DELETE FROM notes WHERE id = ?", (note_id,))
        return cur.rowcount > 0

    # --- Audit ---
    def log_action(self, tool: str, tool_input: str, decision: str, result: str):
        self._exec(
            "INSERT INTO actions (timestamp, tool, input, decision, result) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), tool, tool_input, decision, result[:500]),
        )

    def get_actions(self, since_iso: str = None, until_iso: str = None, limit: int = 40):
        """Ambil catatan audit aksi (terbaru dulu)."""
        sql, params = "SELECT timestamp, tool, input, decision, result FROM actions WHERE 1=1", []
        if since_iso:
            sql += " AND timestamp >= ?"; params.append(since_iso)
        if until_iso:
            sql += " AND timestamp < ?"; params.append(until_iso)
        sql += " ORDER BY id DESC LIMIT ?"; params.append(int(limit))
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()

    # --- Pengingat ---
    def add_reminder(self, due_iso: str, message: str) -> int:
        cur = self._exec(
            "INSERT INTO reminders (created, due, message, status) VALUES (?, ?, ?, 'aktif')",
            (datetime.now().isoformat(timespec="seconds"), due_iso, message))
        return cur.lastrowid

    def pending_reminders(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT id, due, message FROM reminders WHERE status = 'aktif' ORDER BY due")
            return cur.fetchall()

    def mark_reminder(self, rid: int, status: str):
        self._exec("UPDATE reminders SET status = ? WHERE id = ?", (status, rid))

    def cancel_reminder(self, rid: int) -> bool:
        cur = self._exec("UPDATE reminders SET status = 'dibatalkan' WHERE id = ? AND status = 'aktif'",
                         (rid,))
        return cur.rowcount > 0

    # --- Konteks buat system prompt ---
    def build_context(self, max_notes: int = 20, recent: int = 0) -> str:
        parts = []
        notes = self.get_notes()[:max_notes]
        if notes:
            parts.append("Catatan penting tentang user (dari memory):")
            parts += [f"- [#{i}] ({t}) {c}" for i, t, c in notes]
        convo = self.get_recent_conversation(recent)
        if convo:
            parts.append("\nCuplikan percakapan terakhir (sesi sebelumnya):")
            parts += [f"- {r}: {c[:200]}" for r, c in convo]
        return "\n".join(parts)


if __name__ == "__main__":
    mem = Memory()
    mem.save_note("tes", "memory berjalan normal")
    print(mem.build_context())
