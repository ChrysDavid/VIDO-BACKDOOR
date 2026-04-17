"""
Gère l'état partagé (agent sélectionné) et les callbacks de réponse.
Fait le lien entre le serveur réseau et l'interface graphique.
"""
import threading
from typing import Callable
from dataclasses import dataclass
from datetime import datetime

from .server import Server, AgentInfo
from .protocol import MsgType


@dataclass
class CommandDispatch:
    ok: bool
    request_id: str | None = None
    agent_id: str | None = None
    action: str | None = None
    sent_at: str | None = None


class AgentManager:
    def __init__(self, server: Server):
        self.server = server
        self._selected: AgentInfo | None = None
        self._sel_lock = threading.Lock()

        self._response_handlers: list[Callable] = []
        self._selection_handlers: list[Callable] = []
        self._pending_commands: dict[str, dict] = {}
        self._pending_lock = threading.Lock()

        server.on("message_received", self._on_message)
        server.on("agent_disconnected", self._on_disconnected)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    @property
    def selected(self) -> AgentInfo | None:
        with self._sel_lock:
            return self._selected

    @selected.setter
    def selected(self, agent: AgentInfo | None):
        with self._sel_lock:
            self._selected = agent
        for cb in list(self._selection_handlers):
            try:
                cb(agent)
            except Exception:
                pass

    def on_selection(self, cb: Callable):
        self._selection_handlers.append(cb)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def execute(self, action: str, params: dict = None, agent: AgentInfo = None) -> CommandDispatch:
        target = agent or self.selected
        if not target:
            return CommandDispatch(ok=False)

        ok, request_id = self.server.send_command(target.id, action, params)
        if not ok or not request_id:
            return CommandDispatch(ok=False, agent_id=target.id, action=action)

        sent_at = datetime.utcnow().isoformat()
        with self._pending_lock:
            self._pending_commands[request_id] = {
                "request_id": request_id,
                "agent_id": target.id,
                "action": action,
                "sent_at": sent_at,
                "params": params or {},
            }

        return CommandDispatch(
            ok=True,
            request_id=request_id,
            agent_id=target.id,
            action=action,
            sent_at=sent_at,
        )

    def get_agents(self) -> list[AgentInfo]:
        return self.server.get_agents()

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def on_response(self, cb: Callable):
        self._response_handlers.append(cb)

    def get_pending(self, request_id: str) -> dict | None:
        with self._pending_lock:
            return self._pending_commands.get(request_id)

    def _on_message(self, agent: AgentInfo, msg: dict):
        msg_id = msg.get("id")
        msg["meta"] = {
            "pending": None,
        }
        if msg.get("type") == MsgType.RESPONSE and msg_id:
            with self._pending_lock:
                pending = self._pending_commands.pop(msg_id, None)
            msg["meta"]["pending"] = pending

        for cb in list(self._response_handlers):
            try:
                cb(agent, msg)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[AgentManager] Erreur dans callback réponse: {e}")

    def _on_disconnected(self, agent: AgentInfo):
        with self._sel_lock:
            if self._selected and self._selected.id == agent.id:
                self._selected = None
        for cb in list(self._selection_handlers):
            try:
                cb(None)
            except Exception:
                pass
