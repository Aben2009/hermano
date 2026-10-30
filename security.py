# Modul keamanan Hermano.
# Prinsip: Windows Defender yang MEMUTUSKAN ancaman. Hermano cuma membaca, mengawasi,
# dan menjelaskan. Hermano TIDAK menghapus / mengkarantina apa pun.
import base64
import json
import os
import platform
import re
import subprocess
import threading
import time

import psutil

IS_WINDOWS = platform.system() == "Windows"
NO_WINDOW = 0x08000000  # jangan munculin jendela PowerShell

SEVERITY = {0: "tidak diketahui", 1: "rendah", 2: "sedang", 4: "tinggi", 5: "berat"}
STATUS = {0: "tidak diketahui", 1: "terdeteksi", 2: "dibersihkan", 3: "dikarantina",
          4: "dihapus", 5: "diizinkan", 6: "diblokir", 102: "gagal dikarantina",
          103: "gagal dihapus", 104: "gagal diizinkan", 105: "ditinggalkan",
          107: "gagal diblokir"}
NEVER = 10000  # Defender pakai angka raksasa kalau belum pernah scan

# Folder yang sering dipakai malware untuk bersembunyi
STRONG_DIRS = ["\\appdata\\local\\temp\\", "\\windows\\temp\\", "\\downloads\\",
               "\\users\\public\\", "\\$recycle.bin\\"]
WEAK_DIRS = ["\\appdata\\roaming\\", "\\programdata\\"]
SUS_COMMAND = [r"-enc(odedcommand)?\s", r"\bmshta\b", r"\bwscript\b", r"\bcscript\b",
               r"\.vbs\b", r"\.js\b", r"\.hta\b", r"frombase64string", r"\\temp\\",
               r"\\users\\public\\", r"downloadstring", r"invoke-webrequest"]


def _not_windows():
    return "Fitur keamanan ini cuma bisa dipakai di Windows."


def _ps(script, timeout=90):
    """Jalankan PowerShell, hasilnya JSON -> object Python."""
    full = ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "$ErrorActionPreference='SilentlyContinue'; " + script)
    encoded = base64.b64encode(full.encode("utf-16-le")).decode("ascii")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-EncodedCommand", encoded],
        capture_output=True, timeout=timeout, creationflags=NO_WINDOW if IS_WINDOWS else 0)
    out = r.stdout.decode("utf-8", "ignore").strip()
    if not out:
        err = r.stderr.decode("utf-8", "ignore").strip()
        raise RuntimeError(err[:300] or "PowerShell tidak mengembalikan data")
    return json.loads(out)


def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# ------------------------------------------------------------------ Defender
PS_STATUS = r"""
$s = Get-MpComputerStatus
function F($d) { if ($d) { $d.ToString('yyyy-MM-dd HH:mm') } else { '' } }
[pscustomobject]@{
  Service=$s.AMServiceEnabled; Antivirus=$s.AntivirusEnabled;
  RealTime=$s.RealTimeProtectionEnabled; Tamper=$s.IsTamperProtected;
  SigAge=$s.AntivirusSignatureAge; SigUpdated=(F $s.AntivirusSignatureLastUpdated);
  QuickAge=$s.QuickScanAge; QuickEnd=(F $s.QuickScanEndTime); FullAge=$s.FullScanAge
} | ConvertTo-Json -Compress
"""

PS_THREATS = r"""
$names = @{}
Get-MpThreat | ForEach-Object { $names[[string]$_.ThreatID] = @($_.ThreatName, $_.SeverityID) }
$det = Get-MpThreatDetection | Sort-Object InitialDetectionTime -Descending | Select-Object -First 15
$out = @($det | ForEach-Object {
  $n = $names[[string]$_.ThreatID]
  [pscustomobject]@{
    Id=[string]$_.ThreatID; Name=$(if ($n) { $n[0] } else { '' });
    Sev=$(if ($n) { $n[1] } else { 0 });
    Time=$(if ($_.InitialDetectionTime) { $_.InitialDetectionTime.ToString('yyyy-MM-dd HH:mm') } else { '' });
    Status=$_.ThreatStatusID; Ok=$_.ActionSuccess;
    Res=((@($_.Resources) | Select-Object -First 2) -join '; ')
  }
})
$p = Get-MpPreference
$ids = @($p.ThreatIDDefaultAction_Ids); $acts = @($p.ThreatIDDefaultAction_Actions)
$allowed = @()
for ($i = 0; $i -lt $ids.Count; $i++) {
  if ($acts[$i] -eq 6) {
    $id = [string]$ids[$i]; $n = $names[$id]
    $allowed += [pscustomobject]@{ Id=$id; Name=$(if ($n) { $n[0] } else { '' }) }
  }
}
[pscustomobject]@{ Detections=$out; Allowed=$allowed } | ConvertTo-Json -Depth 4 -Compress
"""


def _status_data():
    return _ps(PS_STATUS)


def _threat_data():
    data = _ps(PS_THREATS)
    return {"Detections": _as_list(data.get("Detections")),
            "Allowed": _as_list(data.get("Allowed"))}


def _age(days):
    try:
        days = int(days)
    except (TypeError, ValueError):
        return "tidak diketahui"
    if days >= NEVER:
        return "belum pernah"
    return "hari ini" if days == 0 else f"{days} hari lalu"


def security_status():
    if not IS_WINDOWS:
        return _not_windows()
    lines, warn = [], []
    try:
        s = _status_data()
        on = lambda v: "AKTIF" if v else "MATI"
        lines += ["== Windows Defender ==",
                  f"Antivirus: {on(s.get('Antivirus'))} | Perlindungan real-time: {on(s.get('RealTime'))}"
                  f" | Tamper protection: {on(s.get('Tamper'))}",
                  f"Definisi virus terakhir update: {s.get('SigUpdated') or '-'} ({_age(s.get('SigAge'))})",
                  f"Quick scan terakhir: {_age(s.get('QuickAge'))} | Full scan terakhir: {_age(s.get('FullAge'))}"]
        if not s.get("RealTime"):
            warn.append("[!] Perlindungan real-time MATI. Laptop tidak dijaga secara langsung.")
        if not s.get("Antivirus"):
            warn.append("[!] Antivirus Defender MATI (atau digantikan antivirus lain).")
        if isinstance(s.get("SigAge"), int) and 3 < s["SigAge"] < NEVER:
            warn.append(f"[!] Definisi virus sudah {s['SigAge']} hari tidak update.")
        qa = s.get("QuickAge")
        if isinstance(qa, int) and qa > 14:
            warn.append("[i] Sudah lama tidak ada scan. Pertimbangkan Quick Scan.")
    except Exception as e:
        lines.append(f"Gagal membaca status Defender: {e}")

    try:
        t = _threat_data()
        det = t["Detections"]
        lines.append("\n== Ancaman yang pernah terdeteksi (terbaru) ==")
        if not det:
            lines.append("Tidak ada catatan ancaman.")
        for d in det[:10]:
            name = d.get("Name") or f"ID {d.get('Id')}"
            sev = SEVERITY.get(d.get("Sev"), "tidak diketahui")
            st = STATUS.get(d.get("Status"), str(d.get("Status")))
            lines.append(f"- {name} | tingkat bahaya: {sev} | {d.get('Time')} | status: {st}"
                         + (f" | lokasi: {d.get('Res')}" if d.get("Res") else ""))
            if d.get("Status") in (1, 102, 103, 105, 107):
                warn.append(f"[!] Ancaman '{name}' BELUM berhasil ditangani Defender.")
        allowed = t["Allowed"]
        if allowed:
            lines.append("\n== Ancaman yang kamu IZINKAN (Defender tidak akan memblokir) ==")
            for a in allowed:
                lines.append(f"- {a.get('Name') or 'ID ' + str(a.get('Id'))}")
            warn.append("[i] Ada ancaman yang diizinkan. Kalau tidak yakin aman, cabut izinnya di "
                        "Windows Security > Virus & threat protection > Protection history / Allowed threats.")
    except Exception as e:
        lines.append(f"\nGagal membaca daftar ancaman: {e}")

    if warn:
        lines.append("\n== Perlu perhatian ==")
        lines += warn
    else:
        lines.append("\nTidak ada masalah yang terdeteksi.")
    return "\n".join(lines)


def security_quick_scan():
    if not IS_WINDOWS:
        return _not_windows()
    script = "Start-MpScan -ScanType QuickScan"
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                     creationflags=NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ("Quick Scan Windows Defender dimulai di background (biasanya 5-15 menit). "
            "Kalau ada temuan, Defender akan menanganinya dan penjaga Hermano akan memberi tahu.")


# ------------------------------------------------------------------ heuristik
def _signatures(paths):
    """Cek tanda tangan digital beberapa file sekaligus -> {path: (status, penandatangan)}."""
    paths = [p for p in dict.fromkeys(paths) if p and os.path.isfile(p)][:30]
    if not paths:
        return {}
    arr = ",".join("'" + p.replace("'", "''") + "'" for p in paths)
    script = ("@(" + arr + ") | ForEach-Object { $s = Get-AuthenticodeSignature -FilePath $_; "
              "[pscustomobject]@{ Path=$_; Status=[string]$s.Status; "
              "Signer=$(if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { '' }) } } "
              "| ConvertTo-Json -Compress")
    try:
        rows = _as_list(_ps(script, timeout=120))
    except Exception:
        return {}
    out = {}
    for r in rows:
        signer = re.search(r"CN=([^,]+)", r.get("Signer") or "")
        out[r.get("Path")] = (r.get("Status"), signer.group(1).strip('"') if signer else "")
    return out


def _exe_from_command(cmd):
    cmd = (cmd or "").strip()
    if cmd.startswith('"'):
        end = cmd.find('"', 1)
        return os.path.expandvars(cmd[1:end]) if end > 0 else ""
    m = re.match(r"(.+?\.exe)\b", cmd, re.I)
    return os.path.expandvars(m.group(1)) if m else ""


def _in_dirs(path, dirs):
    low = (path or "").lower()
    return any(d in low for d in dirs)


def security_check_suspicious():
    if not IS_WINDOWS:
        return _not_windows()
    lines = ["Catatan: ini pemeriksaan HEURISTIK. Temuan = 'patut dicek', BELUM TENTU virus."]

    # --- proses yang jalan dari lokasi rawan
    procs = []
    for p in psutil.process_iter(["pid", "name", "exe"]):
        exe = p.info.get("exe") or ""
        if _in_dirs(exe, STRONG_DIRS) or _in_dirs(exe, WEAK_DIRS):
            procs.append((p.info["pid"], p.info["name"], exe))
    online = set()
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.raddr and c.status == "ESTABLISHED" and c.pid:
                online.add(c.pid)
    except Exception:
        pass

    # --- program startup
    try:
        startup = _as_list(_ps("Get-CimInstance Win32_StartupCommand | "
                               "Select-Object Name, Command, Location | ConvertTo-Json -Compress"))
    except Exception as e:
        startup, lines = [], lines + [f"Gagal membaca program startup: {e}"]

    sigs = _signatures([exe for _, _, exe in procs] +
                       [_exe_from_command(s.get("Command")) for s in startup])

    def sig_text(path):
        st, who = sigs.get(path, (None, ""))
        if st == "Valid":
            return f"ditandatangani {who}" if who else "ditandatangani"
        if st is None:
            return "tanda tangan tidak bisa dicek"
        return "TIDAK ditandatangani" if st == "NotSigned" else f"tanda tangan {st}"

    flagged, ok_count = [], 0
    for pid, name, exe in procs:
        valid = sigs.get(exe, (None,))[0] == "Valid"
        strong = _in_dirs(exe, STRONG_DIRS)
        if valid and not strong:
            ok_count += 1
            continue
        level = "[!]" if (strong and not valid) else "[?]"
        net = ", sedang terhubung ke internet" if pid in online else ""
        flagged.append(f"{level} {name} (PID {pid}) jalan dari {exe} | {sig_text(exe)}{net}")
    lines.append("\n== Proses dari lokasi rawan ==")
    lines += flagged or ["Tidak ada yang mencurigakan."]
    if ok_count:
        lines.append(f"({ok_count} proses lain di AppData/ProgramData ditandatangani resmi, dianggap wajar.)")

    s_flagged = []
    for s in startup:
        cmd = s.get("Command") or ""
        exe = _exe_from_command(cmd)
        reasons = [pat for pat in SUS_COMMAND if re.search(pat, cmd, re.I)]
        st = sigs.get(exe, (None,))[0]
        if reasons or (exe and st not in (None, "Valid")):
            why = "pola perintah mencurigakan" if reasons else sig_text(exe)
            s_flagged.append(f"[?] {s.get('Name')} | {why} | {cmd[:160]}")
    lines.append(f"\n== Program startup ({len(startup)} total) ==")
    lines += s_flagged or ["Tidak ada yang mencurigakan."]
    return "\n".join(lines)


# ------------------------------------------------------------------ penjaga
class SecurityMonitor(threading.Thread):
    """Cek Defender berkala; beri tahu kalau ada ancaman BARU atau perlindungan mati."""

    def __init__(self, notifier, minutes=10):
        super().__init__(daemon=True)
        self.notifier = notifier
        self.interval = max(1, int(minutes)) * 60
        self.seen = None
        self.realtime_warned = False

    def _check(self):
        t = _threat_data()
        keys = {(d.get("Id"), d.get("Time")) for d in t["Detections"]}
        if self.seen is None:  # pengecekan pertama = patokan, jangan spam ancaman lama
            self.seen = keys
        else:
            for d in t["Detections"]:
                key = (d.get("Id"), d.get("Time"))
                if key not in self.seen:
                    name = d.get("Name") or f"ID {d.get('Id')}"
                    st = STATUS.get(d.get("Status"), str(d.get("Status")))
                    self.notifier(f"PERINGATAN KEAMANAN: Defender mendeteksi '{name}' "
                                  f"(status: {st}). Tanya Hermano 'cek keamanan laptop' untuk detail.")
            self.seen |= keys
        s = _status_data()
        if not s.get("RealTime") and not self.realtime_warned:
            self.notifier("PERINGATAN KEAMANAN: perlindungan real-time Windows Defender MATI.")
            self.realtime_warned = True
        elif s.get("RealTime"):
            self.realtime_warned = False

    def run(self):
        while True:
            try:
                self._check()
            except Exception:
                pass  # gagal sekali bukan alasan berhenti menjaga
            time.sleep(self.interval)


def start_security_monitor(notifier):
    try:
        from config import SECURITY_MONITOR, SECURITY_CHECK_MINUTES
    except ImportError:
        SECURITY_MONITOR, SECURITY_CHECK_MINUTES = True, 10
    if not (IS_WINDOWS and SECURITY_MONITOR):
        return None
    mon = SecurityMonitor(notifier, SECURITY_CHECK_MINUTES)
    mon.start()
    print(f"[Hermano] Penjaga keamanan aktif (cek Defender tiap {SECURITY_CHECK_MINUTES} menit).")
    return mon
