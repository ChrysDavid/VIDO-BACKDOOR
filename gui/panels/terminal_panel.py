import customtkinter as ctk
from datetime import datetime
from core.agent_manager import AgentManager
from core.server import AgentInfo
from core.protocol import MsgType, Action


class TerminalPanel(ctk.CTkFrame):
    PROMPT_COLOR = "#00d4ff"
    OUTPUT_COLOR = "#c9d1d9"
    ERROR_COLOR = "#f85149"
    INFO_COLOR = "#7c8c96"
    BG = "#0d1117"

    def __init__(self, parent, manager: AgentManager):
        super().__init__(parent, fg_color=self.BG, corner_radius=0)
        self._manager = manager
        self._history: list[str] = []
        self._hist_idx = -1
        self._tab_ctx: dict | None = None   # contexte de complétion Tab en attente
        self._build()
        self._register_events()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self):
        # En-tête
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Terminal",
            font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
            text_color="#c9d1d9",
        ).pack(side="left", padx=20, pady=16)

        self._agent_label = ctk.CTkLabel(
            header,
            text="Aucun agent sélectionné",
            font=ctk.CTkFont(size=12),
            text_color="#4a5568",
        )
        self._agent_label.pack(side="left", padx=8)

        help_btn = ctk.CTkButton(
            header,
            text="? Aide",
            width=70,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#1f3a5f",
            hover_color="#1f6feb",
            text_color="#58a6ff",
            command=self._show_help,
        )
        help_btn.pack(side="right", padx=(0, 8))

        clear_btn = ctk.CTkButton(
            header,
            text="Effacer",
            width=80,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#21262d",
            hover_color="#30363d",
            text_color="#c9d1d9",
            command=self._clear_output,
        )
        clear_btn.pack(side="right", padx=(0, 8))

        # Zone de sortie
        output_frame = ctk.CTkFrame(self, fg_color="#010409", corner_radius=0)
        output_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self._output = ctk.CTkTextbox(
            output_frame,
            fg_color="#010409",
            text_color=self.OUTPUT_COLOR,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=0,
            wrap="word",
            state="disabled",
        )
        self._output.pack(fill="both", expand=True, padx=4, pady=4)

        # Configurer les tags de couleur
        self._output._textbox.tag_config("prompt", foreground=self.PROMPT_COLOR)
        self._output._textbox.tag_config("output", foreground=self.OUTPUT_COLOR)
        self._output._textbox.tag_config("error", foreground=self.ERROR_COLOR)
        self._output._textbox.tag_config("info", foreground=self.INFO_COLOR)

        # Barre de saisie
        input_frame = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=48)
        input_frame.pack(fill="x", side="bottom")
        input_frame.pack_propagate(False)

        self._prompt_label = ctk.CTkLabel(
            input_frame,
            text="$ ",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color=self.PROMPT_COLOR,
            width=24,
        )
        self._prompt_label.pack(side="left", padx=(12, 0), pady=12)

        self._input = ctk.CTkEntry(
            input_frame,
            fg_color="#0d1117",
            border_color="#30363d",
            text_color="#c9d1d9",
            font=ctk.CTkFont(family="Consolas", size=13),
            placeholder_text="Entrez une commande...",
            placeholder_text_color="#4a5568",
        )
        self._input.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self._input.bind("<Return>", self._send_command)
        self._input.bind("<Up>", self._hist_prev)
        self._input.bind("<Down>", self._hist_next)
        self._input.bind("<Tab>", self._tab_complete)

        send_btn = ctk.CTkButton(
            input_frame,
            text="Envoyer",
            width=90,
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#1f6feb",
            hover_color="#388bfd",
            command=self._send_command,
        )
        send_btn.pack(side="right", padx=(0, 12), pady=8)

        self._print_info("VIDO Admin — Terminal interactif")
        self._print_info("Sélectionnez un agent dans la liste, puis tapez vos commandes.")
        self._print_info("Commandes disponibles: screenshot, sysinfo, cd <dir>, dl <file>, ou toute commande shell.")
        self._write("\n")

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _write(self, text: str, tag: str = "output"):
        self._output.configure(state="normal")
        self._output._textbox.insert("end", text, tag)
        self._output.configure(state="disabled")
        self._output._textbox.see("end")

    def _print_prompt(self, agent: AgentInfo, cmd: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._write(f"\n[{ts}] {agent.hostname}:{agent.cwd} $ ", "prompt")
        self._write(cmd, "output")
        self._write("\n")

    def _print_output(self, text: str):
        self._write(text if text.endswith("\n") else text + "\n", "output")

    def _print_error(self, text: str):
        self._write(f"[ERREUR] {text}\n", "error")

    def _print_info(self, text: str):
        self._write(f"# {text}\n", "info")

    def _clear_output(self):
        self._output.configure(state="normal")
        self._output.delete("0.0", "end")
        self._output.configure(state="disabled")

    # ------------------------------------------------------------------
    # Popup aide commandes
    # ------------------------------------------------------------------

    _HELP_COMMANDS = [
        ("screenshot",       "Prend une capture d'écran de la machine distante"),
        ("sysinfo",          "Affiche les informations système (OS, CPU, RAM, user...)"),
        ("ping",             "Vérifie que l'agent répond (latence)"),
        ("cd <chemin>",      "Change le répertoire courant sur la machine distante"),
        ("dl <fichier>",     "Télécharge un fichier depuis la machine distante"),
        ("<commande shell>", "Toute autre commande est exécutée dans le shell distant"),
        ("",                 ""),
        ("Exemples :",       ""),
        ("  screenshot",     ""),
        ("  sysinfo",        ""),
        ("  cd C:\\Users",   ""),
        ("  dl secret.txt",  ""),
        ("  ipconfig /all",  ""),
        ("  dir",            ""),
        ("  whoami",         ""),
    ]

    def _show_help(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Commandes disponibles")
        popup.geometry("620x480")
        popup.resizable(False, False)
        popup.configure(fg_color="#0d1117")
        popup.grab_set()
        popup.lift()
        popup.focus_force()

        # Centrer
        popup.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 620) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 480) // 2
        popup.geometry(f"620x480+{px}+{py}")

        # En-tête
        hdr = ctk.CTkFrame(popup, fg_color="#161b22", corner_radius=0, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr, text="Commandes disponibles",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#c9d1d9",
        ).pack(side="left", padx=20, pady=14)

        # Zone scrollable
        scroll = ctk.CTkScrollableFrame(popup, fg_color="#0d1117", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        for cmd, desc in self._HELP_COMMANDS:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            if cmd == "Exemples :":
                ctk.CTkLabel(
                    row, text="Exemples :",
                    font=ctk.CTkFont(family="Consolas", size=12),
                    text_color="#4a5568", anchor="w",
                ).pack(fill="x", padx=4, pady=(8, 2))
                continue

            if not cmd:
                ctk.CTkFrame(row, fg_color="#21262d", height=1).pack(fill="x", padx=4, pady=4)
                continue

            cmd_lbl = ctk.CTkLabel(
                row,
                text=cmd,
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                text_color="#00d4ff",
                anchor="w",
                width=200,
            )
            cmd_lbl.pack(side="left", padx=(4, 12))

            if desc:
                ctk.CTkLabel(
                    row,
                    text=desc,
                    font=ctk.CTkFont(size=12),
                    text_color="#8b949e",
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)

        # Bouton fermer
        ctk.CTkButton(
            popup,
            text="Fermer",
            width=120,
            height=32,
            fg_color="#21262d",
            hover_color="#30363d",
            text_color="#c9d1d9",
            command=popup.destroy,
        ).pack(pady=(0, 12))

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _send_command(self, _event=None):
        cmd = self._input.get().strip()
        if not cmd:
            return
        self._input.delete(0, "end")

        agent = self._manager.selected
        if not agent:
            self._print_error("Aucun agent sélectionné.")
            return

        # Historique
        self._history.append(cmd)
        self._hist_idx = len(self._history)

        self._print_prompt(agent, cmd)

        parts = cmd.split(" ", 1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if action == "screenshot":
            dispatch = self._manager.execute(Action.SCREENSHOT, agent=agent)
        elif action == "sysinfo":
            dispatch = self._manager.execute(Action.SYSINFO, agent=agent)
        elif action == "cd":
            dispatch = self._manager.execute(Action.CD, params={"path": arg}, agent=agent)
        elif action == "dl":
            dispatch = self._manager.execute(Action.DOWNLOAD, params={"file": arg}, agent=agent)
        elif action == "ping":
            dispatch = self._manager.execute(Action.PING, agent=agent)
        else:
            dispatch = self._manager.execute(Action.SHELL, params={"cmd": cmd}, agent=agent)

        if not dispatch.ok:
            self._print_error("Impossible d'envoyer la commande.")
            return

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _register_events(self):
        self._manager.on_response(self._on_response)
        self._manager.on_selection(lambda a: self.after(0, lambda: self._on_selection(a)))

    def _on_selection(self, agent: AgentInfo | None):
        if agent:
            self._agent_label.configure(
                text=f"→ {agent.hostname} ({agent.ip})", text_color="#00d4ff"
            )
            self._prompt_label.configure(
                text=f"{agent.hostname} $ "
            )
        else:
            self._agent_label.configure(text="Aucun agent sélectionné", text_color="#4a5568")
            self._prompt_label.configure(text="$ ")

    def _on_response(self, agent: AgentInfo, msg: dict):
        if msg.get("type") != MsgType.RESPONSE:
            return

        selected = self._manager.selected
        if not selected or agent.id != selected.id:
            return

        action = msg.get("action")
        data = msg.get("data", {})
        pending_meta = (msg.get("meta") or {}).get("pending")

        def update():
            if pending_meta is None:
                self._print_info("Réponse reçue sans suivi de requête (commande ancienne ou orpheline).")

            if action == Action.SHELL:
                meta_bits = []
                if "exit_code" in data:
                    meta_bits.append(f"exit={data.get('exit_code')}")
                if "duration_ms" in data:
                    meta_bits.append(f"duree={data.get('duration_ms')}ms")
                if "shell" in data:
                    meta_bits.append(f"shell={data.get('shell')}")
                if meta_bits:
                    self._print_info("[exec] " + " | ".join(meta_bits))
                out = data.get("output", "")
                self._print_output(out if out.strip() else "(pas de sortie)")

            elif action == Action.SYSINFO:
                lines = [
                    f"Hostname : {data.get('hostname', '?')}",
                    f"OS       : {data.get('os', '?')} ({data.get('arch', '?')})",
                    f"User     : {data.get('username', '?')}",
                    f"CPU      : {data.get('cpu', '?')} x{data.get('cpu_count', '?')}",
                    f"RAM      : {data.get('ram_available', 0) // 1024**2} MB libre / "
                    f"{data.get('ram_total', 0) // 1024**2} MB total",
                    f"Rép.     : {data.get('cwd', '?')}",
                ]
                self._print_output("\n".join(lines))

            elif action == Action.CD:
                cwd = data.get("cwd")
                if cwd:
                    agent.cwd = cwd
                    self._print_output(f"Répertoire: {cwd}")
                else:
                    self._print_error(data.get("error", "Répertoire introuvable"))

            elif action == Action.DOWNLOAD:
                size = data.get("size", 0)
                name = data.get("filename", "?")
                if data.get("error"):
                    self._print_error(data["error"])
                else:
                    self._print_output(f"Fichier reçu: {name} ({size} octets)")

            elif action == Action.PING:
                self._print_output("pong")

            elif action == Action.SCREENSHOT:
                self._print_info("Capture reçue — visible dans l'onglet Actions.")

            elif action == Action.LISTDIR:
                # Complétion Tab en attente ?
                if self._tab_ctx:
                    ctx = self._tab_ctx
                    self._tab_ctx = None
                    entries = data.get("entries", [])
                    self._apply_tab_completion(entries, ctx)
                else:
                    # Commande listdir explicite
                    entries = data.get("entries", [])
                    path = data.get("path", ".")
                    lines = [f"📁  {path}"]
                    for e in entries:
                        icon = "📂" if e.get("is_dir") else "📄"
                        lines.append(f"  {icon}  {e['name']}")
                    self._print_output("\n".join(lines))

            else:
                # Actions génériques (processes, services, network_info, etc.)
                if "output" in data:
                    self._print_output(data["output"])
                elif "error" in data:
                    self._print_error(data["error"])
                else:
                    self._print_output(str(data))

        self.after(0, update)

    # ------------------------------------------------------------------
    # Historique
    # ------------------------------------------------------------------

    def _hist_prev(self, _event=None):
        if not self._history:
            return
        self._hist_idx = max(0, self._hist_idx - 1)
        self._input.delete(0, "end")
        self._input.insert(0, self._history[self._hist_idx])

    def _hist_next(self, _event=None):
        if not self._history:
            return
        self._hist_idx = min(len(self._history), self._hist_idx + 1)
        self._input.delete(0, "end")
        if self._hist_idx < len(self._history):
            self._input.insert(0, self._history[self._hist_idx])

    # ------------------------------------------------------------------
    # Complétion Tab
    # ------------------------------------------------------------------

    def _tab_complete(self, _event=None):
        agent = self._manager.selected
        if not agent:
            return "break"

        cmd = self._input.get()
        if not cmd:
            return "break"

        # Séparer la partie commande de la partie chemin
        parts = cmd.rsplit(" ", 1)
        if len(parts) < 2:
            # Pas encore de chemin après la commande → compléter depuis cwd
            cmd_part = parts[0]
            path_fragment = ""
        else:
            cmd_part, path_fragment = parts[0], parts[1]

        # Décomposer le fragment en dossier parent + préfixe
        sep = "\\" if "\\" in path_fragment else "/"
        if sep in path_fragment:
            dir_part = path_fragment.rsplit(sep, 1)[0] + sep
            file_prefix = path_fragment.rsplit(sep, 1)[1]
        else:
            dir_part = ""
            file_prefix = path_fragment

        lookup_dir = dir_part if dir_part else "."

        # Sauvegarder le contexte
        self._tab_ctx = {
            "cmd_part":    cmd_part,
            "dir_part":    dir_part,
            "file_prefix": file_prefix,
            "original":    cmd,
        }

        self._manager.execute(Action.LISTDIR, params={"path": lookup_dir}, agent=agent)
        return "break"   # empêche le focus de changer

    def _apply_tab_completion(self, entries: list, ctx: dict):
        file_prefix = ctx["file_prefix"].lower()
        matches = [
            e["name"] for e in entries
            if e["name"].lower().startswith(file_prefix)
        ]
        if not matches:
            self._print_info(f"[Tab] Aucune correspondance pour «{ctx['file_prefix']}»")
            return

        if len(matches) == 1:
            # Complétion unique → on remplace
            sep = "\\" if "\\" in ctx["dir_part"] else "/"
            completed = ctx["dir_part"] + matches[0]
            # Ajouter \ si c'est un dossier (chercher dans entries)
            is_dir = next((e["is_dir"] for e in entries if e["name"] == matches[0]), False)
            if is_dir:
                completed += sep
            new_cmd = f"{ctx['cmd_part']} {completed}" if ctx["cmd_part"] else completed
            self._input.delete(0, "end")
            self._input.insert(0, new_cmd)
        else:
            # Plusieurs correspondances → afficher la liste
            self._print_info(f"[Tab] {len(matches)} correspondance(s) :")
            self._print_output("  " + "   ".join(matches))
