# Riwayat chat Hermano (seperti sidebar ChatGPT): banyak percakapan, tersimpan di database.
import datetime as dt
import re


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


class ChatStore:
    def __init__(self, memory):
        self.m = memory
        self.m._exec("""CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created TEXT, updated TEXT)""")
        self.m._exec("""CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, role TEXT,
            content TEXT, timestamp TEXT)""")

    @staticmethod
    def make_title(text):
        title = re.sub(r"\s+", " ", text).strip()
        return (title[:40] + "...") if len(title) > 40 else (title or "Chat baru")

    def create(self, first_text):
        cur = self.m._exec("INSERT INTO chats (title, created, updated) VALUES (?, ?, ?)",
                           (self.make_title(first_text), _now(), _now()))
        return cur.lastrowid

    def add(self, chat_id, role, content):
        self.m._exec("INSERT INTO chat_messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                     (chat_id, role, content, _now()))
        self.m._exec("UPDATE chats SET updated = ? WHERE id = ?", (_now(), chat_id))

    def list(self, limit=60):
        with self.m.lock:
            cur = self.m.conn.cursor()
            cur.execute("SELECT id, title, updated FROM chats ORDER BY updated DESC LIMIT ?", (limit,))
            return cur.fetchall()

    def messages(self, chat_id):
        with self.m.lock:
            cur = self.m.conn.cursor()
            cur.execute("SELECT role, content, timestamp FROM chat_messages WHERE chat_id = ? ORDER BY id",
                        (chat_id,))
            return cur.fetchall()

    def title(self, chat_id):
        with self.m.lock:
            cur = self.m.conn.cursor()
            cur.execute("SELECT title FROM chats WHERE id = ?", (chat_id,))
            row = cur.fetchone()
            return row[0] if row else "Chat"

    def delete(self, chat_id):
        self.m._exec("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))
        self.m._exec("DELETE FROM chats WHERE id = ?", (chat_id,))
