# Hermano - tampilan ala ChatGPT/Gemini (sidebar riwayat chat di kiri).
# Buka lewat shortcut "Hermano" di Desktop / Start Menu.
# Semua pengaman tetap sama: izin, satpam, mode waspada, verifikasi, audit.
import datetime as dt
import os
import platform
import queue
import re
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import config
import main as core
from brain import create_brain
from chats import ChatStore
from memory import Memory
from reminders import start_reminders
from security import start_security_monitor
from tools import ToolExecutor

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UI = queue.Queue()
LOG_PATH = os.path.join(config.DATA_DIR, "gui_error.log")
FONT = "Segoe UI"

C = {"bg": "#212121", "side": "#171717", "panel": "#2a2a2a", "text": "#ececec",
     "muted": "#9b9b9b", "bubble": "#303030", "accent": "#5b8def", "warn": "#ff7b72",
     "sys": "#e5b567", "code": "#151515", "hover": "#2f2f2f", "sel": "#343541"}

SUGGESTIONS = [("Briefing hari ini", "briefing"),
               ("Cek keamanan laptop", "cek keamanan laptop gw"),
               ("Pengingat gw apa aja?", "pengingat gw apa aja?"),
               ("Apa aja yang lu lakuin hari ini?", "tampilkan riwayat aksi hari ini")]


class QueueWriter:
    """Semua print() dari tool/satpam/verifikasi -> panel 'Detail aksi'."""

    def write(self, text):
        if text and text.strip():
            UI.put(("log", text.rstrip()))

    def flush(self):
        pass


class GuiApprovalGate:
    method = "gui"

    def request(self, description: str) -> bool:
        done, answer = threading.Event(), {"ok": False}
        UI.put(("approve", description, done, answer))
        done.wait()
        return answer["ok"]


def _log_error(text):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n[{dt.datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
    except OSError:
        pass


class HermanoApp:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.current = None          # id chat yang sedang dibuka (None = chat baru)
        self.log_visible = False
        root.title(config.ASSISTANT_NAME)
        root.geometry("1180x760")
        root.minsize(860, 560)
        self._set_icon()
        self._build()

        sys.stdout = QueueWriter()
        sys.stderr = QueueWriter()
        self.memory = Memory()
        self.store = ChatStore(self.memory)
        self.executor = ToolExecutor(GuiApprovalGate(), self.memory, notifier=self.notify)
        self.brain = create_brain(memory=self.memory, voice_mode=False)
        start_security_monitor(self.executor.notifier)
        start_reminders(self.memory, self.executor.notifier)

        self.refresh_sidebar()
        self.new_chat()
        threading.Thread(target=self._check_ready, daemon=True).start()
        self._tick()
        root.after(100, self._poll)

    # ================================================================ layout
    def _set_icon(self):
        ico, png = os.path.join(APP_DIR, "hermano.ico"), os.path.join(APP_DIR, "hermano.png")
        def apply():
            try:
                if os.path.exists(png):
                    self._icon_img = tk.PhotoImage(file=png)
                    self.root.iconphoto(True, self._icon_img)
            except tk.TclError:
                pass
            try:
                if platform.system() == "Windows" and os.path.exists(ico):
                    self.root.iconbitmap(ico)
            except tk.TclError:
                pass
        apply()
        self.root.after(400, apply)  # customtkinter kadang menimpa ikon saat start

    def _build(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ---------------- sidebar kiri
        side = ctk.CTkFrame(self.root, width=260, corner_radius=0, fg_color=C["side"])
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        side.grid_rowconfigure(2, weight=1)
        side.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(side, text=config.ASSISTANT_NAME, font=(FONT, 20, "bold"),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))
        self.new_btn = ctk.CTkButton(side, text="+  Chat baru", height=38, corner_radius=10,
                                     fg_color=C["panel"], hover_color=C["sel"], anchor="w",
                                     font=(FONT, 13), command=self.new_chat)
        self.new_btn.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        self.chat_list = ctk.CTkScrollableFrame(side, fg_color=C["side"], corner_radius=0,
                                                label_text="Riwayat chat", label_font=(FONT, 11),
                                                label_fg_color=C["side"], label_text_color=C["muted"])
        self.chat_list.grid(row=2, column=0, sticky="nsew", padx=6)
        self.chat_list.grid_columnconfigure(0, weight=1)

        quick = ctk.CTkFrame(side, fg_color=C["side"])
        quick.grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 4))
        quick.grid_columnconfigure((0, 1), weight=1)
        self.quick_buttons = []
        for i, (label, text) in enumerate((("Briefing", "briefing"),
                                           ("Keamanan", "cek keamanan laptop gw"),
                                           ("Pengingat", "pengingat gw apa aja?"),
                                           ("Riwayat aksi", "tampilkan riwayat aksi hari ini"))):
            b = ctk.CTkButton(quick, text=label, height=30, corner_radius=8, fg_color=C["panel"],
                              hover_color=C["sel"], font=(FONT, 12),
                              command=lambda t=text: self.send(t))
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
            self.quick_buttons.append(b)

        self.status = ctk.CTkLabel(side, text="", font=(FONT, 11), text_color=C["muted"],
                                   justify="left", anchor="w")
        self.status.grid(row=4, column=0, sticky="ew", padx=18, pady=(4, 14))

        # ---------------- area utama
        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color=C["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.title_lbl = ctk.CTkLabel(main, text="", font=(FONT, 14, "bold"), text_color=C["text"],
                                      anchor="w")
        self.title_lbl.grid(row=0, column=0, sticky="ew", padx=24, pady=(14, 4))

        holder = ctk.CTkFrame(main, fg_color=C["bg"])
        holder.grid(row=1, column=0, sticky="nsew", padx=(24, 8))
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.chat = tk.Text(holder, wrap="word", bg=C["bg"], fg=C["text"], bd=0,
                            highlightthickness=0, font=(FONT, 12), padx=6, pady=10,
                            state="disabled", cursor="arrow")
        self.chat.grid(row=0, column=0, sticky="nsew")
        sb = ctk.CTkScrollbar(holder, command=self.chat.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.chat.configure(yscrollcommand=sb.set)
        self._tags()

        self.log_btn = ctk.CTkButton(main, text="Tampilkan detail aksi", height=24, width=170,
                                     corner_radius=6, fg_color=C["bg"], hover_color=C["hover"],
                                     text_color=C["muted"], font=(FONT, 11), command=self.toggle_log)
        self.log_btn.grid(row=2, column=0, sticky="w", padx=24)
        self.log = tk.Text(main, height=7, wrap="word", bg=C["code"], fg=C["muted"], bd=0,
                           highlightthickness=0, font=("Consolas", 9), padx=10, pady=6,
                           state="disabled")

        box = ctk.CTkFrame(main, fg_color=C["panel"], corner_radius=18)
        box.grid(row=4, column=0, sticky="ew", padx=24, pady=(6, 4))
        box.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkTextbox(box, height=64, fg_color=C["panel"], text_color=C["text"],
                                    font=(FONT, 13), wrap="word", border_width=0)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(14, 6), pady=8)
        self.entry.bind("<Return>", self._on_enter)
        self.send_btn = ctk.CTkButton(box, text="Kirim", width=74, height=36, corner_radius=12,
                                      fg_color=C["accent"], font=(FONT, 13, "bold"),
                                      command=lambda: self.send())
        self.send_btn.grid(row=0, column=1, padx=(0, 10))
        ctk.CTkLabel(main, text="Enter = kirim  |  Shift+Enter = baris baru  |  "
                                "Aksi berisiko selalu minta izin kamu dulu",
                     font=(FONT, 10), text_color=C["muted"]).grid(row=5, column=0, pady=(0, 10))

    def _tags(self):
        t = self.chat
        t.tag_configure("name", foreground=C["muted"], font=(FONT, 10, "bold"), spacing1=14)
        t.tag_configure("name_user", foreground=C["muted"], font=(FONT, 10, "bold"),
                        spacing1=14, justify="right", rmargin=14)
        t.tag_configure("user", background=C["bubble"], foreground=C["text"], font=(FONT, 12),
                        lmargin1=220, lmargin2=220, rmargin=14, spacing1=4, spacing3=4,
                        justify="right")
        t.tag_configure("bot", foreground=C["text"], font=(FONT, 12), lmargin1=4, lmargin2=4,
                        rmargin=90, spacing3=2)
        t.tag_configure("bold", font=(FONT, 12, "bold"))
        t.tag_configure("h", font=(FONT, 14, "bold"), spacing1=6)
        t.tag_configure("code", font=("Consolas", 11), background=C["code"])
        t.tag_configure("sys", foreground=C["sys"], font=(FONT, 10, "italic"), justify="center",
                        spacing1=8)
        t.tag_configure("warn", foreground=C["warn"], font=(FONT, 12, "bold"), spacing1=8,
                        lmargin1=4, lmargin2=4)
        t.tag_configure("welcome", foreground=C["text"], font=(FONT, 24, "bold"),
                        justify="center", spacing1=120)
        t.tag_configure("welcome_sub", foreground=C["muted"], font=(FONT, 12), justify="center",
                        spacing1=6, spacing3=18)
        t.tag_configure("center", justify="center")

    # ================================================================ sidebar
    def refresh_sidebar(self):
        for w in self.chat_list.winfo_children():
            w.destroy()
        rows = self.store.list()
        if not rows:
            ctk.CTkLabel(self.chat_list, text="Belum ada chat.", text_color=C["muted"],
                         font=(FONT, 11)).grid(row=0, column=0, sticky="w", padx=10, pady=6)
        for i, (cid, title, updated) in enumerate(rows):
            row = ctk.CTkFrame(self.chat_list, fg_color=C["sel"] if cid == self.current else C["side"],
                               corner_radius=8)
            row.grid(row=i, column=0, sticky="ew", pady=1)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(row, text=title, anchor="w", height=32, corner_radius=8,
                          fg_color="transparent", hover_color=C["hover"], text_color=C["text"],
                          font=(FONT, 12), command=lambda c=cid: self.open_chat(c)
                          ).grid(row=0, column=0, sticky="ew")
            ctk.CTkButton(row, text="x", width=26, height=26, corner_radius=6,
                          fg_color="transparent", hover_color="#5a2a2a", text_color=C["muted"],
                          font=(FONT, 11), command=lambda c=cid, t=title: self.delete_chat(c, t)
                          ).grid(row=0, column=1, padx=(0, 4))

    def new_chat(self):
        if self.busy:
            return
        self.current = None
        self.brain.reset() if hasattr(self, "brain") else None
        self.title_lbl.configure(text="Chat baru")
        self._clear()
        self.chat.configure(state="normal")
        self.chat.insert("end", f"Ada yang bisa {config.ASSISTANT_NAME} bantu, {config.USER_NAME}?\n",
                         "welcome")
        self.chat.insert("end", "Hermano bisa kontrol laptop (dengan izin kamu), cari berita, baca PDF, "
                                "cek keamanan, dan pasang pengingat.\n", "welcome_sub")
        start = self.chat.index("end-1c")
        for label, text in SUGGESTIONS:
            b = ctk.CTkButton(self.chat, text=label, height=34, corner_radius=17,
                              fg_color=C["panel"], hover_color=C["sel"], font=(FONT, 12),
                              command=lambda t=text: self.send(t))
            self.chat.window_create("end", window=b, padx=6, pady=6)
        self.chat.insert("end", "\n")
        self.chat.tag_add("center", start, "end")
        self.chat.configure(state="disabled")
        if hasattr(self, "store"):
            self.refresh_sidebar()
        self.entry.focus_set()

    def open_chat(self, chat_id):
        if self.busy:
            return
        self.current = chat_id
        msgs = self.store.messages(chat_id)
        self.brain.reset()
        self.brain.history = [{"role": r, "content": c} for r, c, _ in msgs
                              if r in ("user", "assistant")]
        self.title_lbl.configure(text=self.store.title(chat_id))
        self._clear()
        for role, content, ts in msgs:
            self._render(role, content, ts[11:16])
        self.refresh_sidebar()
        self.entry.focus_set()

    def delete_chat(self, chat_id, title):
        if self.busy:
            return
        if not messagebox.askyesno("Hapus chat", f"Hapus chat \"{title}\"?\nIni tidak bisa dibatalkan."):
            return
        self.store.delete(chat_id)
        if chat_id == self.current:
            self.new_chat()
        else:
            self.refresh_sidebar()

    # ================================================================ chat area
    def _clear(self):
        self.chat.configure(state="normal")
        for w in self.chat.window_names():
            try:
                self.chat.nametowidget(w).destroy()
            except (KeyError, tk.TclError):
                pass
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def _insert_markdown(self, text):
        for line in text.split("\n"):
            m = re.match(r"^\s*#{1,4}\s+(.*)", line)
            if m:
                self.chat.insert("end", m.group(1) + "\n", ("bot", "h"))
                continue
            for i, part in enumerate(re.split(r"(\*\*.+?\*\*|`[^`]+`)", line)):
                if part.startswith("**") and part.endswith("**") and len(part) > 4:
                    self.chat.insert("end", part[2:-2], ("bot", "bold"))
                elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                    self.chat.insert("end", part[1:-1], ("bot", "code"))
                else:
                    self.chat.insert("end", part, "bot")
            self.chat.insert("end", "\n", "bot")

    def _render(self, role, text, stamp=None):
        stamp = stamp or dt.datetime.now().strftime("%H:%M")
        self.chat.configure(state="normal")
        if role == "user":
            self.chat.insert("end", f"{config.USER_NAME}  {stamp}\n", "name_user")
            self.chat.insert("end", " " + text.strip() + " \n", "user")
        elif role == "assistant":
            self.chat.insert("end", f"{config.ASSISTANT_NAME}  {stamp}\n", "name")
            self._insert_markdown(text.strip())
        else:
            self.chat.insert("end", text + "\n", role)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log.grid(row=3, column=0, sticky="ew", padx=24, pady=(2, 0))
            self.log_btn.configure(text="Sembunyikan detail aksi")
        else:
            self.log.grid_forget()
            self.log_btn.configure(text="Tampilkan detail aksi")

    def add_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", f"{dt.datetime.now():%H:%M:%S}  {text}\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    # ================================================================ kirim
    def _on_enter(self, event):
        if event.state & 0x0001:
            return None
        self.send()
        return "break"

    def send(self, text=None):
        if self.busy:
            return
        text = (text if text is not None else self.entry.get("1.0", "end")).strip()
        if not text:
            return
        self.entry.delete("1.0", "end")
        if self.current is None:
            self.current = self.store.create(text)
            self.title_lbl.configure(text=self.store.title(self.current))
            self._clear()
        self.store.add(self.current, "user", text)
        self._render("user", text)
        self._render("sys", "Hermano sedang berpikir...")
        self._set_busy(True)
        self.refresh_sidebar()
        threading.Thread(target=self._worker, args=(self.current, text), daemon=True).start()

    def _worker(self, chat_id, text):
        try:
            reply = core.handle_turn(self.brain, self.memory, self.executor, text)
            self.store.add(chat_id, "assistant", reply)
            UI.put(("assistant", reply))
        except Exception:
            _log_error(traceback.format_exc())
            UI.put(("warn", "Terjadi error. Detail tersimpan di memory_data/gui_error.log"))
        finally:
            UI.put(("done", None))

    def _remove_thinking(self):
        self.chat.configure(state="normal")
        idx = self.chat.search("Hermano sedang berpikir...", "end", backwards=True)
        if idx:
            self.chat.delete(idx, f"{idx} lineend +1c")
        self.chat.configure(state="disabled")

    def notify(self, message):
        UI.put(("notify", message))

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in [self.send_btn, self.new_btn] + self.quick_buttons:
            b.configure(state=state)
        self._update_status()

    # ================================================================ pop-up izin
    def _approval_dialog(self, description, done, answer):
        win = ctk.CTkToplevel(self.root)
        win.title("Hermano minta izin")
        win.configure(fg_color=C["panel"])
        win.transient(self.root)
        win.resizable(False, False)
        warn = "MODE WASPADA" in description
        ctk.CTkLabel(win, text="Hermano minta izin" + ("  -  MODE WASPADA" if warn else ""),
                     font=(FONT, 16, "bold"), text_color=C["warn"] if warn else C["sys"]
                     ).pack(anchor="w", padx=20, pady=(18, 8))
        box = ctk.CTkTextbox(win, width=640, height=min(260, 60 + 20 * description.count("\n")),
                             fg_color=C["code"], font=("Consolas", 12), wrap="word")
        box.insert("1.0", description)
        box.configure(state="disabled")
        box.pack(padx=20)
        ctk.CTkLabel(win, text="Baca detailnya dulu. Tolak kalau ada yang aneh.", font=(FONT, 11),
                     text_color=C["muted"]).pack(anchor="w", padx=20, pady=(8, 0))
        row = ctk.CTkFrame(win, fg_color=C["panel"])
        row.pack(fill="x", padx=20, pady=16)

        def finish(ok):
            if done.is_set():
                return
            answer["ok"] = ok
            done.set()
            self._render("sys", ("Kamu menyetujui: " if ok else "Kamu menolak: ")
                         + description.splitlines()[0][:90])
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        deny = ctk.CTkButton(row, text="Tolak", width=110, fg_color="#8b2c2c", hover_color="#a33",
                             command=lambda: finish(False))
        deny.pack(side="right")
        ctk.CTkButton(row, text="Setujui", width=110, fg_color=C["sel"], hover_color="#444",
                      command=lambda: finish(True)).pack(side="right", padx=10)
        win.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        win.bind("<Escape>", lambda e: finish(False))
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 3
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        win.after(80, lambda: (win.grab_set(), win.lift(), deny.focus_set()))
        self.root.bell()

    # ================================================================ loop & status
    def _poll(self):
        try:
            while True:
                item = UI.get_nowait()
                kind = item[0]
                if kind == "log":
                    self.add_log(item[1])
                elif kind == "approve":
                    self._approval_dialog(*item[1:])
                elif kind == "notify":
                    self._render("warn", item[1])
                    self.root.bell()
                    self.root.deiconify()
                    self.root.lift()
                elif kind == "assistant":
                    self._remove_thinking()
                    self._render("assistant", item[1])
                elif kind == "done":
                    self._remove_thinking()
                    self._set_busy(False)
                    self.refresh_sidebar()
                    self.entry.focus_set()
                else:
                    self._render(kind, item[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _check_ready(self):
        problem = self.brain.check_ready() if hasattr(self.brain, "check_ready") else ""
        if problem:
            UI.put(("warn", problem))

    def _update_status(self):
        try:
            import psutil
            bat = psutil.sensors_battery()
        except Exception:
            bat = None
        plugged = bat is None or bat.power_plugged
        if config.BRAIN_BACKEND == "ollama":
            auto = getattr(config, "OLLAMA_AUTO_MODEL", False)
            model = (config.OLLAMA_MODEL if (plugged or not auto)
                     else getattr(config, "OLLAMA_MODEL_BATTERY", config.OLLAMA_MODEL))
        else:
            model = config.MODEL_NAME
        power = "" if bat is None else f"\nBaterai {bat.percent:.0f}%{' (dicas)' if plugged else ''}"
        state = "Sedang berpikir..." if self.busy else "Siap"
        self.status.configure(text=f"Otak: {model}{power}\n{state}")

    def _tick(self):
        self._update_status()
        self.root.after(30000, self._tick)


def run():
    if platform.system() == "Windows":
        try:  # biar ikon di taskbar = ikon Hermano, bukan ikon Python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Aben.Hermano")
        except Exception:
            pass
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.report_callback_exception = lambda *a: _log_error("".join(traceback.format_exception(*a)))
    threading.excepthook = lambda a: _log_error(
        "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    try:
        HermanoApp(root)
    except Exception:
        _log_error(traceback.format_exc())
        raise
    root.mainloop()


if __name__ == "__main__":
    run()
