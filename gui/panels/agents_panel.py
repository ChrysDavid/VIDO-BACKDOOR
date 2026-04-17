"""
Panel de gestion des agents — Vue double : liste à gauche, détails à droite.
FIX: Pas de CTkFrame imbriqué avec fg_color="transparent" (crash customtkinter 5.2.x)
"""
import shutil
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog

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
        self._last_build_log = "Aucun log de build pour le moment."
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

        self._download_pkg_btn = ctk.CTkButton(
            lhdr,
            text="Telecharger agent",
            width=132,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#1f6feb",
            hover_color="#388bfd",
            text_color="white",
            command=self._open_download_popup,
        )
        self._download_pkg_btn.pack(side="right", padx=(0, 8), pady=14)

        self._build_logs_btn = ctk.CTkButton(
            lhdr,
            text="Logs build",
            width=92,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#21262d",
            hover_color="#30363d",
            text_color="#c9d1d9",
            command=self._show_build_log_popup,
        )
        self._build_logs_btn.pack(side="right", padx=(0, 8), pady=14)

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

        self._status_lbl = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#7c8c96",
            anchor="w",
        )
        self._status_lbl.pack(fill="x", padx=14, pady=(0, 8))

    def _set_status(self, msg: str, error: bool = False):
        self._status_lbl.configure(text=msg, text_color="#f85149" if error else "#7c8c96")

    @staticmethod
    def _run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

    @staticmethod
    def _format_cmd_output(title: str, cmd: str, proc: subprocess.CompletedProcess) -> str:
        return "\n".join([
            f"[{title}]",
            f"cmd: {cmd}",
            f"exit: {proc.returncode}",
            "--- stdout ---",
            proc.stdout.strip() or "(vide)",
            "--- stderr ---",
            proc.stderr.strip() or "(vide)",
            "",
        ])

    def _show_build_log_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Logs de generation")
        popup.geometry("900x620")
        popup.configure(fg_color="#161b22")
        popup.grab_set()
        popup.lift()
        popup.focus_force()

        ctk.CTkLabel(
            popup,
            text="Logs de build agent",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#c9d1d9",
        ).pack(anchor="w", padx=14, pady=(12, 6))

        box = ctk.CTkTextbox(
            popup,
            fg_color="#0d1117",
            text_color="#c9d1d9",
            font=ctk.CTkFont(family="Consolas", size=11),
            border_color="#30363d",
            border_width=1,
            wrap="word",
        )
        box.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        box.insert("0.0", self._last_build_log)
        box.configure(state="disabled")

        ctk.CTkButton(
            popup,
            text="Fermer",
            width=90,
            command=popup.destroy,
        ).pack(pady=(0, 12))

    def _resolve_agent_package_source(self, package_type: str) -> Path | None:
        root = Path(__file__).resolve().parents[2]
        candidates = {
            "exe": [
                root / "agent" / "dist" / "agent.exe",
                root / "assets" / "agent.exe",
                root / "agent.exe",
            ],
            "apk": [
                root / "agent" / "dist" / "agent.apk",
                root / "assets" / "agent.apk",
                root / "agent.apk",
            ],
        }

        for candidate in candidates.get(package_type, []):
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _build_agent_exe(self) -> tuple[Path, str]:
        root = Path(__file__).resolve().parents[2]
        agent_dir = root / "agent"
        script = agent_dir / "agent.py"
        if not script.exists():
            raise RuntimeError(f"Script introuvable: {script}")

        logs: list[str] = []

        check_cmd = [sys.executable, "-m", "PyInstaller", "--version"]
        check_proc = self._run_cmd(check_cmd, cwd=agent_dir)
        logs.append(self._format_cmd_output("Verification PyInstaller", " ".join(check_cmd), check_proc))

        if check_proc.returncode != 0:
            install_cmd = [sys.executable, "-m", "pip", "install", "pyinstaller"]
            install_proc = self._run_cmd(install_cmd, cwd=root)
            logs.append(self._format_cmd_output("Installation PyInstaller", " ".join(install_cmd), install_proc))
            if install_proc.returncode != 0:
                raise RuntimeError("\n".join(logs + ["Installation automatique de PyInstaller echouee."]))

        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--name",
            "agent",
            str(script),
        ]
        proc = self._run_cmd(cmd, cwd=agent_dir)
        logs.append(self._format_cmd_output("Build EXE", " ".join(cmd), proc))
        if proc.returncode != 0:
            raise RuntimeError("\n".join(logs + ["Generation EXE echouee."]))

        built = agent_dir / "dist" / "agent.exe"
        if not built.exists():
            raise RuntimeError("Build termine mais agent.exe introuvable dans agent/dist")
        return built, "\n".join(logs)

    def _prepare_android_build_files(self, build_dir: Path):
        root = Path(__file__).resolve().parents[2]
        agent_py = root / "agent" / "agent.py"
        if not agent_py.exists():
            raise RuntimeError(f"Script introuvable: {agent_py}")

        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "main.py").write_text(agent_py.read_text(encoding="utf-8"), encoding="utf-8")

        spec_file = build_dir / "buildozer.spec"
        if not spec_file.exists():
            spec_file.write_text(
                "\n".join([
                    "[app]",
                    "title = VidoAgent",
                    "package.name = vidoagent",
                    "package.domain = org.vido",
                    "source.dir = .",
                    "source.include_exts = py,png,jpg,kv,atlas",
                    "version = 1.0",
                    "requirements = python3,psutil,pillow,opencv-python",
                    "orientation = portrait",
                    "fullscreen = 0",
                    "android.permissions = INTERNET,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE",
                    "android.api = 33",
                    "android.minapi = 24",
                    "\n",
                    "[buildozer]",
                    "log_level = 2",
                ]),
                encoding="utf-8",
            )

    def _build_agent_apk(self) -> tuple[Path, str]:
        root = Path(__file__).resolve().parents[2]
        build_dir = root / "agent" / "android_build"
        self._prepare_android_build_files(build_dir)
        logs: list[str] = []

        build_succeeded = False

        if shutil.which("buildozer"):
            local_cmd = ["buildozer", "android", "debug"]
            local_proc = self._run_cmd(local_cmd, cwd=build_dir)
            logs.append(self._format_cmd_output("Build APK local", " ".join(local_cmd), local_proc))
            build_succeeded = local_proc.returncode == 0
        else:
            logs.append("[Build APK local]\nBuildozer non trouve dans l'environnement Windows.\n")

        if not build_succeeded:
            if not shutil.which("wsl"):
                raise RuntimeError("\n".join(logs + ["Buildozer absent et WSL introuvable."]))

            wslpath_cmd = ["wsl", "wslpath", "-a", str(build_dir)]
            wslpath_proc = self._run_cmd(wslpath_cmd, cwd=root)
            logs.append(self._format_cmd_output("Resolution chemin WSL", " ".join(wslpath_cmd), wslpath_proc))
            if wslpath_proc.returncode != 0:
                raise RuntimeError("\n".join(logs + ["Impossible de convertir le chemin pour WSL."]))

            wsl_build_dir = wslpath_proc.stdout.strip().splitlines()[0].strip()
            safe_dir = shlex.quote(wsl_build_dir)
            bash_cmd = f"cd {safe_dir} && buildozer android debug"
            wsl_cmd = ["wsl", "bash", "-lc", bash_cmd]
            wsl_proc = self._run_cmd(wsl_cmd, cwd=root)
            logs.append(self._format_cmd_output("Build APK via WSL", " ".join(wsl_cmd), wsl_proc))
            if wsl_proc.returncode != 0:
                raise RuntimeError("\n".join(logs + ["Generation APK echouee via WSL."]))

        bin_dir = build_dir / "bin"
        if not bin_dir.exists():
            raise RuntimeError("Build termine mais dossier bin introuvable")

        apk_files = sorted(bin_dir.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not apk_files:
            raise RuntimeError("Build termine mais aucun .apk n'a ete genere")
        return apk_files[0], "\n".join(logs)

    def _build_and_copy_package(self, package: str, target_dir: Path, filename: str) -> tuple[Path, str]:
        if package == "exe":
            source, build_logs = self._build_agent_exe()
        elif package == "apk":
            source, build_logs = self._build_agent_apk()
        else:
            raise RuntimeError(f"Format non supporte: {package}")

        target_dir = target_dir.expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = (target_dir / filename).resolve()
        shutil.copy2(source, target)
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(
                f"Copie terminee sans fichier valide dans le dossier choisi: {target_dir}"
            )

        copy_log = "\n".join([
            "[Copie locale]",
            f"source: {source}",
            f"destination: {target}",
            "",
        ])
        return target, build_logs + "\n" + copy_log

    def _open_download_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Telecharger l'agent")
        popup.geometry("620x280")
        popup.resizable(False, False)
        popup.configure(fg_color="#161b22")
        popup.grab_set()
        popup.lift()
        popup.focus_force()

        popup.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - 620) // 2
        py = self.winfo_rooty() + (self.winfo_height() - 280) // 2
        popup.geometry(f"620x280+{px}+{py}")

        choice_var = ctk.StringVar(value="exe")

        ctk.CTkLabel(
            popup,
            text="Telechargement agent",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#c9d1d9",
        ).pack(pady=(14, 4))

        ctk.CTkLabel(
            popup,
            text="Choisissez le format, le nom du fichier et le dossier de destination.",
            font=ctk.CTkFont(size=11),
            text_color="#7c8c96",
        ).pack(pady=(0, 10))

        form = ctk.CTkFrame(popup, fg_color="#0d1117", corner_radius=10)
        form.pack(fill="x", padx=16, pady=(0, 10))

        row1 = ctk.CTkFrame(form, fg_color="#0d1117")
        row1.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(row1, text="Format", width=120, anchor="w", text_color="#c9d1d9").pack(side="left")

        format_selector = ctk.CTkSegmentedButton(
            row1,
            values=["Desktop (.exe)", "Mobile (.apk)"],
            command=lambda v: _on_format_change(v),
            width=280,
        )
        format_selector.pack(side="left")
        format_selector.set("Desktop (.exe)")

        row2 = ctk.CTkFrame(form, fg_color="#0d1117")
        row2.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row2, text="Nom du fichier", width=120, anchor="w", text_color="#c9d1d9").pack(side="left")

        filename_entry = ctk.CTkEntry(
            row2,
            width=360,
            fg_color="#161b22",
            border_color="#30363d",
            text_color="#c9d1d9",
        )
        filename_entry.pack(side="left")
        filename_entry.insert(0, "agent.exe")

        row3 = ctk.CTkFrame(form, fg_color="#0d1117")
        row3.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkLabel(row3, text="Repertoire", width=120, anchor="w", text_color="#c9d1d9").pack(side="left")

        dir_entry = ctk.CTkEntry(
            row3,
            width=280,
            fg_color="#161b22",
            border_color="#30363d",
            text_color="#c9d1d9",
        )
        dir_entry.pack(side="left", padx=(0, 8))
        dir_entry.insert(0, str(Path.home() / "Downloads"))

        def choose_dir():
            selected = filedialog.askdirectory(title="Choisir le repertoire de destination")
            if selected:
                dir_entry.delete(0, "end")
                dir_entry.insert(0, selected)

        ctk.CTkButton(
            row3,
            text="Parcourir",
            width=78,
            height=30,
            fg_color="#21262d",
            hover_color="#30363d",
            command=choose_dir,
        ).pack(side="left")

        def _on_format_change(value: str):
            ext = ".exe" if value.startswith("Desktop") else ".apk"
            package = "exe" if ext == ".exe" else "apk"
            choice_var.set(package)
            filename_entry.delete(0, "end")
            filename_entry.insert(0, f"agent{ext}")

        def confirm_download():
            package = choice_var.get()
            filename = filename_entry.get().strip()
            if not filename:
                self._set_status("Nom de fichier obligatoire.", error=True)
                return

            suffix = ".exe" if package == "exe" else ".apk"
            if not filename.lower().endswith(suffix):
                filename += suffix

            target_dir_raw = dir_entry.get().strip()
            if not target_dir_raw:
                self._set_status("Repertoire de destination obligatoire.", error=True)
                return

            target_dir = Path(target_dir_raw).expanduser()
            if not target_dir.is_absolute():
                self._set_status("Le repertoire doit etre un chemin absolu.", error=True)
                return

            self._set_status(f"Generation en cours ({package})...")
            popup.destroy()

            self._download_pkg_btn.configure(state="disabled", text="Generation...")
            self._build_logs_btn.configure(state="disabled")
            self._reload_btn.configure(state="disabled")

            def run_build():
                try:
                    target, logs = self._build_and_copy_package(package, target_dir, filename)
                except Exception as e:
                    self._last_build_log = str(e)
                    self.after(0, lambda: self._set_status(f"Echec generation {package}: voir Logs build", error=True))
                else:
                    self._last_build_log = logs
                    self.after(0, lambda: self._set_status(f"Agent genere et copie dans: {target.parent}"))
                finally:
                    self.after(0, lambda: self._download_pkg_btn.configure(state="normal", text="Telecharger agent"))
                    self.after(0, lambda: self._build_logs_btn.configure(state="normal"))
                    self.after(0, lambda: self._reload_btn.configure(state="normal"))

            threading.Thread(target=run_build, daemon=True).start()

        buttons = ctk.CTkFrame(popup, fg_color="#161b22")
        buttons.pack(pady=(0, 8))

        ctk.CTkButton(
            buttons,
            text="Annuler",
            width=100,
            height=32,
            fg_color="#21262d",
            hover_color="#30363d",
            text_color="#c9d1d9",
            command=popup.destroy,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            buttons,
            text="Telecharger",
            width=120,
            height=32,
            fg_color="#1f6feb",
            hover_color="#388bfd",
            text_color="white",
            command=confirm_download,
        ).pack(side="left", padx=4)

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
