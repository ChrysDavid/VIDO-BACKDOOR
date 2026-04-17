"""
Gère l'état partagé (agent sélectionné) et les callbacks de réponse.
Fait le lien entre le serveur réseau et l'interface graphique.
"""
import threading
from typing import Callable

from .server import Server, AgentInfo
from .protocol import MsgType


class AgentManager:
    def __init__(self, server: Server):
        self.server = server
        self._selected: AgentInfo | None = None
        self._sel_lock = threading.Lock()

        self._response_handlers: list[Callable] = []
        self._selection_handlers: list[Callable] = []

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

    def execute(self, action: str, params: dict = None, agent: AgentInfo = None) -> bool:
        target = agent or self.selected
        if not target:
            return False
        return self.server.send_command(target.id, action, params)

    def get_agents(self) -> list[AgentInfo]:
        return self.server.get_agents()

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def on_response(self, cb: Callable):
        self._response_handlers.append(cb)

    def _on_message(self, agent: AgentInfo, msg: dict):
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
