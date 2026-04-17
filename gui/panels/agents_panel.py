"""
Panel de gestion des agents — Vue double : liste à gauche, détails à droite.
FIX: Pas de CTkFrame imbriqué avec fg_color="transparent" (crash customtkinter 5.2.x)
"""
import customtkinter as ctk
from core.server import AgentInfo
from core.agent_manager import AgentManager


# ──────────────────────────────────────────────
# Item de la liste (flat grid, pas de transparent nested frames)
# ──────────────────────────────────────────────
class AgentItem(ctk.CTkFrame):
    BG         = "#161b22"
    BG_SEL     = "#1f3a5f"
    BORDER     = "#30363d"
    BORDER_SEL = "#1f6feb"

    def __init__(self, parent, agent: AgentInfo, on_select):
        super().__init__(
            parent,
            fg_color=self.BG,
            border_color=self.BORDER,
            border_width=1,
            corner_radius=8,
            cursor="hand2",
        )
        self.agent = agent
        self._on_select = on_select
        self._selected = False
        self._build()
        self.bind("<Button-1>", self._click)
        # Bind sur chaque label enfant direct (pas récursif pour éviter les canvas internes)
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkLabel):
                w.bind("<Button-1>", self._click)

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        # Indicateur vert
        ctk.CTkLabel(
            self, text="●",
            font=ctk.CTkFont(size=9),
            text_color="#3fb950",
            width=22,
        ).grid(row=0, column=0, rowspan=2, padx=(12, 0), pady=8)

        # Hostname
        ctk.CTkLabel(
            self,
            text=self.agent.hostname,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#c9d1d9",
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=(8, 0))

        # IP + OS
        os_short = self.agent.os[:30] + "…" if len(self.agent.os) > 30 else self.agent.os
        ctk.CTkLabel(
            self,
            text=f"{self.agent.ip}  ·  {os_short}",
            font=ctk.CTkFont(size=11),
            text_color="#7c8c96",
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(8, 4), pady=(0, 8))

        # Badge user
        ctk.CTkLabel(
            self,
            text=self.agent.username,
            font=ctk.CTkFont(size=10),
            text_color="#58a6ff",
            width=80,
            anchor="e",
        ).grid(row=0, column=2, padx=(0, 12), pady=(8, 0))

    def set_selected(self, val: bool):
        self._selected = val
        self.configure(
            fg_color=self.BG_SEL if val else self.BG,
            border_color=self.BORDER_SEL if val else self.BORDER,
        )

    def _click(self, _=None):
        self._on_select(self.agent)


# ──────────────────────────────────────────────
# Panel détail (côté droit)
# ──────────────────────────────────────────────
class AgentDetailPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#0d1117", corner_radius=0)
        self._build_empty()

    def _build_empty(self):
        self._clear()
        self._empty_frame = ctk.CTkFrame(self, fg_color="#0d1117")
        self._empty_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            self._empty_frame,
            text="←",
            font=ctk.CTkFont(size=48),
            text_color="#21262d",
        ).pack()

        ctk.CTkLabel(
            self._empty_frame,
            text="Sélectionnez un agent",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#3d4a54",
        ).pack(pady=(4, 8))

        ctk.CTkLabel(
            self._empty_frame,
            text="Cliquez sur un agent dans la liste\npour voir ses informations et\nl'utiliser dans les autres onglets.",
            font=ctk.CTkFont(size=12),
            text_color="#3d4a54",
            justify="center",
        ).pack()

    def show_agent(self, agent: AgentInfo):
        self._clear()

        scroll = ctk.CTkScrollableFrame(self, fg_color="#0d1117", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        # ── En-tête agent ──────────────────────────────────────────────
        top = ctk.CTkFrame(scroll, fg_color="#161b22", corner_radius=12,
                           border_color="#1f6feb", border_width=1)
        top.pack(fill="x", pady=(0, 16))

        # Dot + hostname
        ctk.CTkLabel(
            top, text="●  ACTIF",
            font=ctk.CTkFont(size=11),
            text_color="#3fb950",
        ).pack(anchor="e", padx=16, pady=(12, 0))

        ctk.CTkLabel(
            top,
            text=agent.hostname,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#00d4ff",
        ).pack(padx=20, pady=(4, 2))

        ctk.CTkLabel(
            top,
            text=f"{agent.os}  ·  {agent.arch}",
            font=ctk.CTkFont(size=12),
            text_color="#7c8c96",
        ).pack(padx=20, pady=(0, 12))

        # ── Grille d'info ──────────────────────────────────────────────
        grid_frame = ctk.CTkFrame(scroll, fg_color="#0d1117")
        grid_frame.pack(fill="x", pady=(0, 12))
        grid_frame.grid_columnconfigure((0, 1), weight=1, uniform="col")

        infos = [
            ("Adresse IP",   agent.ip,                          "🌐"),
            ("Utilisateur",  agent.username,                    "👤"),
            ("CPU",          f"{agent.cpu[:24]}",               "⚙"),
            ("Coeurs",       str(agent.cpu_count),              "🔢"),
            ("RAM totale",   agent.ram_gb(),                    "💾"),
            ("Répertoire",   agent.cwd[:40] + "…" if len(agent.cwd) > 40 else agent.cwd, "📁"),
        ]

        for i, (label, value, icon) in enumerate(infos):
            row, col = divmod(i, 2)
            card = ctk.CTkFrame(
                grid_frame, fg_color="#161b22",
                corner_radius=8, border_color="#30363d", border_width=1,
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="ew")

            ctk.CTkLabel(
                card, text=f"{icon}  {label}",
                font=ctk.CTkFont(size=10),
                text_color="#4a5568",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(8, 0))

            ctk.CTkLabel(
                card, text=value,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#c9d1d9",
                anchor="w",
                wraplength=200,
            ).pack(fill="x", padx=12, pady=(2, 8))

        # ── Tip ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            scroll,
            text="✓  Agent sélectionné — utilisez les onglets Actions et Terminal",
            font=ctk.CTkFont(size=12),
            text_color="#3fb950",
        ).pack(pady=8)

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()


# ──────────────────────────────────────────────
# Panel principal
# ──────────────────────────────────────────────
class AgentsPanel(ctk.CTkFrame):
    def __init__(self, parent, manager: AgentManager):
        super().__init__(parent, fg_color="#0d1117", corner_radius=0)
        self._manager = manager
        self._items: dict[str, AgentItem] = {}
        self._build()
        self._register_events()

    def _build(self):
        # ── Colonne gauche : liste ─────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color="#0b0f14", width=300, corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # En-tête liste
        lhdr = ctk.CTkFrame(left, fg_color="#161b22", corner_radius=0, height=56)
        lhdr.pack(fill="x")
        lhdr.pack_propagate(False)

        ctk.CTkLabel(
            lhdr,
            text="Agents",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#c9d1d9",
        ).pack(side="left", padx=16, pady=16)

        self._reload_btn = ctk.CTkButton(
            lhdr,
            text="Reload",
            width=72,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#21262d",
            hover_color="#30363d",
            text_color="#c9d1d9",
            command=self._reload_agents,
        )
        self._reload_btn.pack(side="right", padx=(0, 8), pady=14)

        self._count_lbl = ctk.CTkLabel(
            lhdr, text="0",
            font=ctk.CTkFont(size=11),
            text_color="#7c8c96",
        )
        self._count_lbl.pack(side="right", padx=(0, 12))

        # Instructions
        ctk.CTkLabel(
            left,
            text="⬇  Cliquez pour sélectionner",
            font=ctk.CTkFont(size=10),
            text_color="#4a5568",
        ).pack(pady=(8, 4))

        # Séparateur
        ctk.CTkFrame(left, fg_color="#21262d", height=1).pack(fill="x", padx=12)

        # Scroll
        self._scroll = ctk.CTkScrollableFrame(
            left, fg_color="#0b0f14", corner_radius=0,
            scrollbar_button_color="#30363d",
        )
        self._scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Placeholder
        self._placeholder = ctk.CTkLabel(
            self._scroll,
            text="Aucun agent\n\nLancez :\npython agent.py",
            font=ctk.CTkFont(size=12),
            text_color="#3d4a54",
            justify="center",
        )
        self._placeholder.pack(expand=True, pady=60)

        # Séparateur vertical
        ctk.CTkFrame(self, fg_color="#21262d", width=1).pack(side="left", fill="y")

        # ── Colonne droite : détails ────────────────────────────────────
        self._detail = AgentDetailPanel(self)
        self._detail.pack(side="left", fill="both", expand=True)

    def _register_events(self):
        self._manager.server.on(
            "agent_connected",
            lambda a: self.after(0, lambda: self._add(a)),
        )
        self._manager.server.on(
            "agent_disconnected",
            lambda a: self.after(0, lambda: self._remove(a)),
        )

    def _add(self, agent: AgentInfo):
        self._placeholder.pack_forget()
        item = AgentItem(self._scroll, agent, self._select)
        item.pack(fill="x", pady=4)
        self._items[agent.id] = item
        self._update_count()

    def _remove(self, agent: AgentInfo):
        item = self._items.pop(agent.id, None)
        if item:
            item.destroy()
        if not self._items:
            self._placeholder.pack(expand=True, pady=60)
            self._detail._build_empty()
        self._update_count()

    def _select(self, agent: AgentInfo):
        for item in self._items.values():
            item.set_selected(False)
        item = self._items.get(agent.id)
        if item:
            item.set_selected(True)
        self._manager.selected = agent
        self._detail.show_agent(agent)

    def _update_count(self):
        n = len(self._items)
        self._count_lbl.configure(
            text=f"{n} agent{'s' if n > 1 else ''}",
            text_color="#00d4ff" if n > 0 else "#7c8c96",
        )

    def _reload_agents(self):
        selected = self._manager.selected
        selected_id = selected.id if selected else None

        for item in list(self._items.values()):
            item.destroy()
        self._items.clear()

        agents = self._manager.get_agents()
        if not agents:
            self._placeholder.pack(expand=True, pady=60)
            self._manager.selected = None
            self._detail._build_empty()
            self._update_count()
            return

        self._placeholder.pack_forget()

        sorted_agents = sorted(agents, key=lambda a: (a.hostname or "", a.ip or ""))
        for agent in sorted_agents:
            item = AgentItem(self._scroll, agent, self._select)
            item.pack(fill="x", pady=4)
            self._items[agent.id] = item

        if selected_id and selected_id in self._items:
            selected_agent = next((a for a in sorted_agents if a.id == selected_id), None)
            if selected_agent:
                self._select(selected_agent)
        else:
            self._manager.selected = None
            self._detail._build_empty()

        self._update_count()
