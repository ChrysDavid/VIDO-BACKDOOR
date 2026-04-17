import socket
import threading
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable

from .protocol import recv_msg, send_msg, make_msg, MsgType, Action
import config

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    id: str
    ip: str
    port: int
    sock: socket.socket
    hostname: str = "?"
    os: str = "?"
    arch: str = "?"
    username: str = "?"
    cpu: str = "?"
    cpu_count: int = 0
    ram_total: int = 0
    ram_available: int = 0
    cwd: str = "?"
    connected: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def addr_str(self) -> str:
        return f"{self.ip}:{self.port}"

    def ram_gb(self) -> str:
        if self.ram_total:
            return f"{self.ram_total / 1024**3:.1f} GB"
        return "?"


class Server:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._agents: dict[str, AgentInfo] = {}
        self._lock = threading.Lock()
        self._running = False
        self._srv_sock: socket.socket | None = None
        self._callbacks: dict[str, list[Callable]] = {
            "agent_connected": [],
            "agent_disconnected": [],
            "message_received": [],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on(self, event: str, cb: Callable):
        if event in self._callbacks:
            self._callbacks[event].append(cb)

    def start(self):
        self._running = True
        threading.Thread(target=self._listen, daemon=True, name="srv-listen").start()
        logger.info(f"Serveur démarré sur {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self._srv_sock:
            try:
                self._srv_sock.close()
            except Exception:
                pass
        with self._lock:
            for agent in list(self._agents.values()):
                try:
                    agent.sock.close()
                except Exception:
                    pass
            self._agents.clear()

    def get_agents(self) -> list[AgentInfo]:
        with self._lock:
            return list(self._agents.values())

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        with self._lock:
            return self._agents.get(agent_id)

    def send_command(self, agent_id: str, action: str, params: dict = None) -> tuple[bool, str | None]:
        agent = self.get_agent(agent_id)
        if not agent or not agent.connected:
            return False, None
        msg = make_msg(MsgType.COMMAND, action=action, data=params or {})
        try:
            with agent._lock:
                send_msg(agent.sock, msg)
            return True, msg.get("id")
        except Exception as e:
            logger.error(f"Erreur envoi commande à {agent_id}: {e}")
            return False, None

    def build_audit_entry(self, agent: AgentInfo, action: str, request_id: str, params: dict | None = None) -> dict:
        return {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent.id,
            "agent_hostname": agent.hostname,
            "agent_ip": agent.ip,
            "action": action,
            "params": params or {},
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, event: str, *args):
        for cb in list(self._callbacks.get(event, [])):
            try:
                cb(*args)
            except Exception as e:
                logger.error(f"Callback '{event}' error: {e}")

    def _listen(self):
        self._srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv_sock.bind((self.host, self.port))
        self._srv_sock.listen(config.MAX_AGENTS)
        self._srv_sock.settimeout(1.0)
        logger.info("En attente de connexions...")

        while self._running:
            try:
                conn, addr = self._srv_sock.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True,
                    name=f"agent-{addr[0]}:{addr[1]}",
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, sock: socket.socket, addr: tuple):
        ip, port = addr
        agent_id = f"{ip}:{port}"

        try:
            # Handshake auth
            msg = recv_msg(sock)
            if not msg or msg.get("type") != MsgType.AUTH:
                sock.close()
                return
            if msg.get("data", {}).get("token") != config.AUTH_TOKEN:
                send_msg(sock, make_msg(MsgType.AUTH_FAIL, data={"reason": "Token invalide"}))
                sock.close()
                logger.warning(f"Auth échouée depuis {agent_id}")
                return
            send_msg(sock, make_msg(MsgType.AUTH_OK))

            # Attendre sysinfo
            si_msg = recv_msg(sock)
            si = si_msg.get("data", {}) if si_msg else {}

            agent = AgentInfo(
                id=agent_id,
                ip=ip,
                port=port,
                sock=sock,
                hostname=si.get("hostname", "?"),
                os=si.get("os", "?"),
                arch=si.get("arch", "?"),
                username=si.get("username", "?"),
                cpu=si.get("cpu", "?"),
                cpu_count=si.get("cpu_count", 0),
                ram_total=si.get("ram_total", 0),
                ram_available=si.get("ram_available", 0),
                cwd=si.get("cwd", "?"),
            )

            with self._lock:
                self._agents[agent_id] = agent
            self._emit("agent_connected", agent)
            logger.info(f"Agent connecté: {agent_id} ({agent.hostname})")

            # Boucle de réception
            while self._running and agent.connected:
                msg = recv_msg(sock)
                if not msg:
                    break
                self._emit("message_received", agent, msg)

        except Exception as e:
            logger.error(f"Erreur client {agent_id}: {e}")
        finally:
            with self._lock:
                agent = self._agents.pop(agent_id, None)
            if agent:
                agent.connected = False
                self._emit("agent_disconnected", agent)
                logger.info(f"Agent déconnecté: {agent_id}")
            try:
                sock.close()
            except Exception:
                pass
