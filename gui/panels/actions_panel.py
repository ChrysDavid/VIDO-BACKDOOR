"""
Panel d'actions — 33 actions organisées en 6 catégories, interface moderne en grille.
"""
import base64
from io import BytesIO
from datetime import datetime

import customtkinter as ctk
from PIL import Image

from core.agent_manager import AgentManager
from core.server import AgentInfo
from core.protocol import MsgType

# ──────────────────────────────────────────────
# Catalogue des 33 actions
# ──────────────────────────────────────────────
CATEGORIES = [
    {"id": "system",   "label": "Système",  "color": "#1f6feb"},
    {"id": "screen",   "label": "Écran",    "color": "#8957e5"},
    {"id": "files",    "label": "Fichiers", "color": "#3fb950"},
    {"id": "network",  "label": "Réseau",   "color": "#f0883e"},
    {"id": "shell",    "label": "Shell",    "color": "#00d4ff"},
    {"id": "security", "label": "Sécurité", "color": "#f85149"},
]

ACTIONS: dict[str, list] = {
    "system": [
        {"id": "sysinfo",      "icon": "💻", "label": "Infos système",     "desc": "OS, CPU, RAM, hostname"},
        {"id": "processes",    "icon": "⚙",  "label": "Processus",         "desc": "Liste des processus actifs"},
        {"id": "services",     "icon": "🔧", "label": "Services",           "desc": "Services système actifs"},
        {"id": "users",        "icon": "👥", "label": "Utilisateurs",       "desc": "Utilisateurs connectés"},
        {"id": "env_vars",     "icon": "📋", "label": "Variables env.",     "desc": "Variables d'environnement"},
        {"id": "uptime",       "icon": "⏱",  "label": "Uptime",             "desc": "Temps de fonctionnement"},
        {"id": "disk_usage",   "icon": "💾", "label": "Disques",            "desc": "Usage des partitions"},
        {"id": "installed_sw", "icon": "📦", "label": "Logiciels installés","desc": "Logiciels sur le système"},
    ],
    "screen": [
        {"id": "screenshot",   "icon": "📷", "label": "Capture d'écran",   "desc": "Screenshot distant"},
        {"id": "clipboard",    "icon": "📋", "label": "Presse-papiers",    "desc": "Contenu du clipboard"},
        {"id": "active_window","icon": "🪟", "label": "Fenêtre active",    "desc": "Application en premier plan"},
    ],
    "files": [
        {"id": "listdir",      "icon": "📁", "label": "Lister répertoire", "desc": "Contenu d'un dossier"},
        {"id": "dl",           "icon": "⬇",  "label": "Télécharger",       "desc": "Récupère un fichier"},
        {"id": "file_search",  "icon": "🔍", "label": "Rechercher fichier","desc": "Cherche par nom"},
        {"id": "recent_files", "icon": "🕐", "label": "Fichiers récents",  "desc": "Derniers fichiers ouverts"},
        {"id": "file_hash",    "icon": "🔐", "label": "Hash fichier",      "desc": "SHA256 d'un fichier"},
        {"id": "read_file",    "icon": "📄", "label": "Lire fichier",      "desc": "Affiche le contenu texte"},
    ],
    "network": [
        {"id": "network_info", "icon": "🌐", "label": "Interfaces réseau", "desc": "Adresses IP et adaptateurs"},
        {"id": "open_ports",   "icon": "🔌", "label": "Ports en écoute",   "desc": "Ports ouverts (LISTENING)"},
        {"id": "connections",  "icon": "🔗", "label": "Connexions actives","desc": "Connexions ESTABLISHED"},
        {"id": "dns_lookup",   "icon": "🔎", "label": "Résolution DNS",    "desc": "Résout un nom de domaine"},
        {"id": "ping_target",  "icon": "📡", "label": "Ping cible",        "desc": "Ping une adresse"},
        {"id": "arp_table",    "icon": "🗺",  "label": "Table ARP",         "desc": "Table ARP locale"},
    ],
    "shell": [
        {"id": "shell",        "icon": "⌨",  "label": "Commande shell",    "desc": "Exécute une commande"},
        {"id": "cmd_history",  "icon": "📜", "label": "Historique",        "desc": "Commandes précédentes"},
        {"id": "whoami",       "icon": "🪪", "label": "Identité",          "desc": "whoami /all"},
        {"id": "cwd",          "icon": "📍", "label": "Répertoire actuel", "desc": "Dossier courant"},
    ],
    "security": [
        {"id": "startup_items",   "icon": "🚀", "label": "Démarrage",         "desc": "Programmes au démarrage"},
        {"id": "scheduled_tasks", "icon": "📅", "label": "Tâches planifiées", "desc": "schtasks /query"},
        {"id": "wifi_profiles",   "icon": "📶", "label": "Profils WiFi",      "desc": "SSID + mots de passe"},
        {"id": "firewall",        "icon": "🛡",  "label": "Pare-feu",          "desc": "Statut du pare-feu"},
        {"id": "antivirus",       "icon": "🦠", "label": "Antivirus",         "desc": "Antivirus détecté"},
        {"id": "event_logs",      "icon": "📝", "label": "Journaux système",  "desc": "20 derniers événements"},
        {"id": "ping",            "icon": "🏓", "label": "Ping agent",        "desc": "Test de latence"},
    ],
}

# Actions nécessitant un paramètre : (id, label_dialog, clé_param)
NEED_PARAM = {
    "dl":          ("Télécharger un fichier",     "Chemin du fichier distant",  "file"),
    "file_search": ("Rechercher un fichier",      "Nom ou motif (ex: *.txt)",   "name"),
    "file_hash":   ("Hash SHA256",                "Chemin du fichier",          "file"),
    "read_file":   ("Lire un fichier",            "Chemin du fichier",          "file"),
    "dns_lookup":  ("Résolution DNS",             "Nom de domaine",             "host"),
    "ping_target": ("Ping",                       "Adresse IP ou domaine",      "host"),
    "shell":       ("Exécuter une commande shell","Commande à exécuter",        "cmd"),
    "listdir":     ("Lister un répertoire",       "Chemin (vide = courant)",    "path"),
}


class ActionCard(ctk.CTkFrame):
    def __init__(self, parent, action: dict, cat_color: str, on_click):
        super().__init__(
            parent,
            fg_color="#161b22",
            border_color="#30363d",
            border_width=1,
            corner_radius=10,
            cursor="hand2",
            width=158,
            height=100,
        )
        self.pack_propagate(False)
        self._action = action
        self._on_click = on_click
        self._cat_color = cat_color
        self._build()
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Barre colorée en haut
        bar = ctk.CTkFrame(self, fg_color=self._cat_color, height=3, corner_radius=0)
        bar.pack(fill="x")

        # Icône
        self._icon_lbl = ctk.CTkLabel(
            self,
            text=self._action["icon"],
            font=ctk.CTkFont(size=28),
            text_color="#c9d1d9",
        )
        self._icon_lbl.pack(pady=(6, 0))

        # Nom
        self._name_lbl = ctk.CTkLabel(
            self,
            text=self._action["label"],
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#c9d1d9",
            wraplength=140,
        )
        self._name_lbl.pack()

        # Description
        ctk.CTkLabel(
            self,
            text=self._action["desc"],
            font=ctk.CTkFont(size=9),
            text_color="#4a5568",
            wraplength=140,
        ).pack()

        for w in self.winfo_children():
            if not isinstance(w, ctk.CTkFrame):
                w.bind("<Button-1>", self._click)
                w.bind("<Enter>", self._hover_on)
                w.bind("<Leave>", self._hover_off)

    def _click(self, _=None):
        self._on_click(self._action)

    def _hover_on(self, _=None):
        self.configure(fg_color="#1c2128", border_color=self._cat_color)

    def _hover_off(self, _=None):
        self.configure(fg_color="#161b22", border_color="#30363d")

    def set_running(self, val: bool):
        self._icon_lbl.configure(text="⏳" if val else self._action["icon"])


class ActionsPanel(ctk.CTkFrame):
    def __init__(self, parent, manager: AgentManager):
        super().__init__(parent, fg_color="#0d1117", corner_radius=0)
        self._manager = manager
        self._cards: dict[str, ActionCard] = {}
        self._active_cat = "system"
        self._last_screenshot: Image.Image | None = None
        self._pending_by_action: dict[str, str] = {}
        self._build()
        self._register_events()

    # ──────────────────────────────────────────────
    # Construction UI
    # ──────────────────────────────────────────────

    def _build(self):
        # ── En-tête ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Actions",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#c9d1d9",
        ).pack(side="left", padx=20, pady=16)

        self._agent_badge = ctk.CTkLabel(
            header, text="Aucun agent sélectionné",
            font=ctk.CTkFont(size=12), text_color="#4a5568",
        )
        self._agent_badge.pack(side="left", padx=8)

        # Compteur actions
        ctk.CTkLabel(
            header,
            text=f"{sum(len(v) for v in ACTIONS.values())} actions disponibles",
            font=ctk.CTkFont(size=11), text_color="#4a5568",
        ).pack(side="right", padx=20)

        # ── Tabs catégories ───────────────────────────────────────────────
        tabs_frame = ctk.CTkFrame(self, fg_color="#0b0f14", corner_radius=0, height=48)
        tabs_frame.pack(fill="x")
        tabs_frame.pack_propagate(False)

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for cat in CATEGORIES:
            btn = ctk.CTkButton(
                tabs_frame,
                text=cat["label"],
                font=ctk.CTkFont(size=12),
                width=100,
                height=32,
                corner_radius=16,
                fg_color="transparent",
                hover_color="#21262d",
                text_color="#7c8c96",
                border_width=1,
                border_color="#30363d",
                command=lambda c=cat: self._switch_cat(c),
            )
            btn.pack(side="left", padx=(8, 0), pady=8)
            self._tab_btns[cat["id"]] = btn

        # ── Corps : grille + résultat ─────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="#0d1117")
        body.pack(fill="both", expand=True)

        # Zone scrollable des cartes
        self._cards_scroll = ctk.CTkScrollableFrame(
            body, fg_color="#0d1117", corner_radius=0,
            scrollbar_button_color="#30363d", width=520,
        )
        self._cards_scroll.pack(side="left", fill="y", padx=12, pady=12)

        # Séparateur
        ctk.CTkFrame(body, fg_color="#21262d", width=1).pack(side="left", fill="y")

        # Panneau résultat
        self._result_pane = ctk.CTkFrame(body, fg_color="#0d1117")
        self._result_pane.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        result_hdr = ctk.CTkFrame(self._result_pane, fg_color="#0d1117")
        result_hdr.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            result_hdr, text="RÉSULTAT",
            font=ctk.CTkFont(size=10),
            text_color="#4a5568", anchor="w",
        ).pack(side="left")

        self._result_action_lbl = ctk.CTkLabel(
            result_hdr, text="",
            font=ctk.CTkFont(size=11),
            text_color="#58a6ff",
        )
        self._result_action_lbl.pack(side="left", padx=8)

        self._result_time_lbl = ctk.CTkLabel(
            result_hdr, text="",
            font=ctk.CTkFont(size=10),
            text_color="#4a5568",
        )
        self._result_time_lbl.pack(side="right")

        # Zone résultat (textbox par défaut)
        self._result_box = ctk.CTkFrame(
            self._result_pane, fg_color="#161b22",
            corner_radius=8, border_color="#30363d", border_width=1,
        )
        self._result_box.pack(fill="both", expand=True)

        # ── Widgets résultat — tous gérés avec pack (jamais place) ──────────
        # Placeholder visible au départ
        self._res_placeholder = ctk.CTkLabel(
            self._result_box,
            text="Sélectionnez un agent\net cliquez sur une action.",
            font=ctk.CTkFont(size=13),
            text_color="#3d4a54",
            justify="center",
        )
        self._res_placeholder.pack(expand=True)  # pack, pas place

        # Textbox (caché par défaut)
        self._result_text = ctk.CTkTextbox(
            self._result_box,
            fg_color="#161b22", text_color="#c9d1d9",
            font=ctk.CTkFont(family="Consolas", size=12),
            border_width=0, state="disabled",
        )
        # Ne pas pack ici — sera packéé dans _show_text

        # Image screenshot (cachée par défaut)
        self._result_img_lbl = ctk.CTkLabel(self._result_box, text="")
        # Ne pas pack ici — sera packée dans _show_image

        # Barre de statut
        self._status = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=11), text_color="#7c8c96", anchor="w",
        )
        self._status.pack(fill="x", padx=20, pady=(0, 6))

        # Premier affichage
        self._switch_cat(CATEGORIES[0])

    def _switch_cat(self, cat: dict):
        self._active_cat = cat["id"]

        # Mise à jour des boutons d'onglets
        for cid, btn in self._tab_btns.items():
            is_active = cid == cat["id"]
            cat_color = next((c["color"] for c in CATEGORIES if c["id"] == cid), "#7c8c96")
            btn.configure(
                fg_color=cat_color if is_active else "transparent",
                text_color="white" if is_active else "#7c8c96",
                border_color=cat_color if is_active else "#30363d",
            )

        # Reconstruction de la grille
        for w in self._cards_scroll.winfo_children():
            w.destroy()
        self._cards.clear()

        actions = ACTIONS.get(cat["id"], [])
        cat_color = cat["color"]
        cols = 3

        for idx, action in enumerate(actions):
            row, col = divmod(idx, cols)
            card = ActionCard(
                self._cards_scroll, action, cat_color,
                on_click=self._on_card_click,
            )
            card.grid(row=row, column=col, padx=6, pady=6)
            self._cards[action["id"]] = card

    # ──────────────────────────────────────────────
    # Interactions
    # ──────────────────────────────────────────────

    def _on_card_click(self, action: dict):
        agent = self._manager.selected
        if not agent:
            self._set_status("Aucun agent sélectionné. Allez dans l'onglet Agents.", error=True)
            return

        action_id = action["id"]

        if action_id in NEED_PARAM:
            title, prompt, key = NEED_PARAM[action_id]
            self._ask_param(title, prompt, lambda v, aid=action_id, k=key: self._execute(aid, {k: v}))
        else:
            self._execute(action_id)

    def _execute(self, action_id: str, params: dict = None):
        card = self._cards.get(action_id)
        if card:
            card.set_running(True)

        self._set_status(f"Exécution : {action_id}...")
        dispatch = self._manager.execute(action_id, params or {})
        if not dispatch.ok:
            self._set_status("Impossible d'envoyer la commande.", error=True)
            if card:
                card.set_running(False)
            return

        if dispatch.request_id:
            self._pending_by_action[action_id] = dispatch.request_id

    def _ask_param(self, title: str, prompt: str, callback):
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("380x180")
        popup.resizable(False, False)
        popup.configure(fg_color="#161b22")
        popup.grab_set()
        popup.lift()
        popup.focus_force()

        popup.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 380) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 180) // 2
        popup.geometry(f"380x180+{px}+{py}")

        ctk.CTkLabel(
            popup, text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#c9d1d9",
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            popup, text=prompt,
            font=ctk.CTkFont(size=11), text_color="#7c8c96",
        ).pack()

        entry = ctk.CTkEntry(
            popup, fg_color="#0d1117",
            border_color="#30363d", text_color="#c9d1d9",
            font=ctk.CTkFont(size=13), width=320, height=36,
        )
        entry.pack(pady=10)
        entry.focus_set()

        def confirm(_=None):
            val = entry.get().strip()
            popup.destroy()
            if val or val == "":
                callback(val)

        entry.bind("<Return>", confirm)

        btns = ctk.CTkFrame(popup, fg_color="#161b22")
        btns.pack()
        ctk.CTkButton(
            btns, text="Annuler", width=90, height=30,
            fg_color="#21262d", hover_color="#30363d", text_color="#c9d1d9",
            command=popup.destroy,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btns, text="Exécuter", width=90, height=30,
            fg_color="#1f6feb", hover_color="#388bfd",
            command=confirm,
        ).pack(side="left", padx=4)

    # ──────────────────────────────────────────────
    # Affichage des résultats
    # ──────────────────────────────────────────────

    def _show_text(self, text: str, action_label: str):
        self._res_placeholder.pack_forget()
        self._result_img_lbl.pack_forget()
        self._result_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._result_text.configure(state="normal")
        self._result_text.delete("0.0", "end")
        self._result_text.insert("end", text)
        self._result_text.configure(state="disabled")
        self._result_action_lbl.configure(text=f"  {action_label}")
        self._result_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))

    def _show_image(self, b64_data: str):
        try:
            img = Image.open(BytesIO(base64.b64decode(b64_data)))
            self._last_screenshot = img
            w = max(1, self._result_box.winfo_width() - 16)
            h = max(1, self._result_box.winfo_height() - 16)
            img.thumbnail((w, h), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self._result_text.pack_forget()
            self._res_placeholder.pack_forget()
            self._result_img_lbl.configure(image=ctk_img, text="")
            self._result_img_lbl.image = ctk_img
            self._result_img_lbl.pack(expand=True)
            self._result_action_lbl.configure(text="  Capture d'écran")
            self._result_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        except Exception as e:
            self._show_text(f"[Erreur décodage image: {e}]", "Screenshot")

    def _set_status(self, msg: str, error: bool = False):
        self._status.configure(
            text=msg,
            text_color="#f85149" if error else "#7c8c96",
        )

    # ──────────────────────────────────────────────
    # Callbacks réseau
    # ──────────────────────────────────────────────

    def _register_events(self):
        self._manager.on_response(self._on_response)
        self._manager.on_selection(lambda a: self.after(0, lambda: self._on_selection(a)))

    def _on_selection(self, agent: AgentInfo | None):
        if agent:
            self._agent_badge.configure(
                text=f"→ {agent.hostname} ({agent.ip})", text_color="#00d4ff"
            )
        else:
            self._agent_badge.configure(text="Aucun agent sélectionné", text_color="#4a5568")

    def _on_response(self, agent: AgentInfo, msg: dict):
        if msg.get("type") != MsgType.RESPONSE:
            return

        selected = self._manager.selected
        if not selected or agent.id != selected.id:
            return

        action_id = msg.get("action", "")
        data = msg.get("data", {})
        pending_meta = (msg.get("meta") or {}).get("pending")

        expected_req_id = self._pending_by_action.get(action_id)
        incoming_req_id = msg.get("id")
        if expected_req_id and incoming_req_id and expected_req_id != incoming_req_id:
            return

        # Trouver le label de l'action
        action_label = action_id
        for cat_actions in ACTIONS.values():
            for a in cat_actions:
                if a["id"] == action_id:
                    action_label = f"{a['icon']} {a['label']}"
                    break

        def update():
            try:
                if pending_meta is None:
                    self._set_status("Reponse hors suivi (ancienne requete ou redemarrage).")
                self._update_result(action_id, action_label, data)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._set_status(f"Erreur affichage: {e}", error=True)

        self.after(0, update)

    def _update_result(self, action_id: str, action_label: str, data: dict):
        self._pending_by_action.pop(action_id, None)
        card = self._cards.get(action_id)
        if card:
            card.set_running(False)

        if "error" in data:
            self._show_text(f"[ERREUR]\n{data['error']}", action_label)
            self._set_status(f"Erreur : {data['error'][:60]}", error=True)
            return

        self._set_status(f"Résultat reçu : {action_label}")

        if action_id == "screenshot":
            b64 = data.get("screenshot")
            if b64:
                self._show_image(b64)
            else:
                self._show_text("Pas de données screenshot.", action_label)
        else:
            if "output" in data:
                text = data["output"]
                if action_id == "shell":
                    meta = []
                    if "exit_code" in data:
                        meta.append(f"exit={data['exit_code']}")
                    if "duration_ms" in data:
                        meta.append(f"duree={data['duration_ms']}ms")
                    if "shell" in data:
                        meta.append(f"shell={data['shell']}")
                    if meta:
                        text = "[exec] " + " | ".join(meta) + "\n\n" + text
            elif "cwd" in data:
                text = f"Répertoire : {data['cwd']}"
            elif "entries" in data:
                entries = data["entries"]
                path = data.get("path", ".")
                lines = [f"📁  {path}\n"]
                for e in entries:
                    icon = "📂" if e.get("is_dir") else "📄"
                    lines.append(f"  {icon}  {e['name']}")
                text = "\n".join(lines)
            elif "pong" in data:
                text = "✓ Pong reçu — agent réactif"
            else:
                text = "\n".join(f"{k:<18}: {v}" for k, v in data.items())
            self._show_text(text, action_label)
