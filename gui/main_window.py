import customtkinter as ctk
from core.agent_manager import AgentManager
from .panels.agents_panel import AgentsPanel
from .panels.terminal_panel import TerminalPanel
from .panels.actions_panel import ActionsPanel
import config


NAV = [
    ("agents",   "Agents",   "👥"),
    ("actions",  "Actions",  "⚡"),
    ("terminal", "Terminal", "⌨"),
]


class MainWindow(ctk.CTkFrame):
    def __init__(self, parent, manager: AgentManager):
        super().__init__(parent, fg_color="#0d1117", corner_radius=0)
        self._manager = manager
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._setup_sidebar()
        self._setup_content()
        self._register_events()
        self._show_panel("agents")

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _setup_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=230, fg_color="#161b22", corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent", height=90)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)

        ctk.CTkLabel(
            logo_frame,
            text="VIDO",
            font=ctk.CTkFont(family="Consolas", size=36, weight="bold"),
            text_color="#00d4ff",
        ).place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(
            logo_frame,
            text="Admin Panel",
            font=ctk.CTkFont(size=11),
            text_color="#4a5568",
        ).place(relx=0.5, rely=0.80, anchor="center")

        # Séparateur
        ctk.CTkFrame(sidebar, fg_color="#21262d", height=1).pack(fill="x", padx=16)

        # Statut serveur
        status_frame = ctk.CTkFrame(sidebar, fg_color="#0d1117", corner_radius=8)
        status_frame.pack(fill="x", padx=12, pady=12)

        row = ctk.CTkFrame(status_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=8)

        self._dot = ctk.CTkLabel(
            row, text="●", font=ctk.CTkFont(size=10), text_color="#3fb950", width=16
        )
        self._dot.pack(side="left")

        self._srv_label = ctk.CTkLabel(
            row,
            text=f"Serveur actif · port {config.SERVER_PORT}",
            font=ctk.CTkFont(size=11),
            text_color="#7c8c96",
        )
        self._srv_label.pack(side="left", padx=(6, 0))

        # Navigation
        ctk.CTkLabel(
            sidebar,
            text="NAVIGATION",
            font=ctk.CTkFont(size=10),
            text_color="#4a5568",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 4))

        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=8)

        for key, label, icon in NAV:
            btn = ctk.CTkButton(
                nav_frame,
                text=f"  {icon}  {label}",
                anchor="w",
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                hover_color="#21262d",
                text_color="#8b949e",
                height=40,
                corner_radius=6,
                command=lambda k=key: self._show_panel(k),
            )
            btn.pack(fill="x", pady=2)
            self._nav_btns[key] = btn

        # Pied de page
        self._agent_count = ctk.CTkLabel(
            sidebar,
            text="0 agent connecté",
            font=ctk.CTkFont(size=11),
            text_color="#4a5568",
        )
        self._agent_count.pack(side="bottom", pady=(0, 8))

        ctk.CTkLabel(
            sidebar,
            text=f"VIDO Admin  v{config.APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color="#3d4a54",
        ).pack(side="bottom", pady=(0, 4))

    # ------------------------------------------------------------------
    # Content area
    # ------------------------------------------------------------------

    def _setup_content(self):
        self._content = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=0)
        self._content.pack(side="right", fill="both", expand=True)

        self._panels = {
            "agents":   AgentsPanel(self._content, self._manager),
            "actions":  ActionsPanel(self._content, self._manager),
            "terminal": TerminalPanel(self._content, self._manager),
        }

    def _show_panel(self, name: str):
        for key, panel in self._panels.items():
            panel.pack_forget()
            btn = self._nav_btns.get(key)
            if btn:
                btn.configure(fg_color="transparent", text_color="#8b949e")

        panel = self._panels.get(name)
        if panel:
            panel.pack(fill="both", expand=True)

        btn = self._nav_btns.get(name)
        if btn:
            btn.configure(fg_color="#1f3a5f", text_color="#58a6ff")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _register_events(self):
        self._manager.server.on("agent_connected", lambda a: self.after(0, self._refresh_count))
        self._manager.server.on("agent_disconnected", lambda a: self.after(0, self._refresh_count))

    def _refresh_count(self):
        n = len(self._manager.get_agents())
        self._agent_count.configure(text=f"{n} agent{'s' if n > 1 else ''} connecté{'s' if n > 1 else ''}")
