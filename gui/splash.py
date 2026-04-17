import threading
import time
from pathlib import Path

import customtkinter as ctk
from PIL import Image as PILImage

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, parent, on_done: callable, duration: float = 3.0):
        super().__init__(parent)
        self._on_done = on_done
        self._duration = duration
        self._setup_ui()
        self._animate()

    def _setup_ui(self):
        self.title("")
        self.geometry("480x420")
        self.resizable(False, False)
        self.overrideredirect(True)
        self.configure(fg_color="#0d1117")
        self.lift()
        self.focus_force()

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 480) // 2
        y = (self.winfo_screenheight() - 420) // 2
        self.geometry(f"480x420+{x}+{y}")

        # Cadre principal avec bordure
        card = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=16,
                            border_color="#21262d", border_width=1)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.96, relheight=0.96)

        # --- Logo ---
        try:
            pil_img = PILImage.open(_LOGO_PATH).convert("RGBA")
            pil_img.thumbnail((140, 140), PILImage.LANCZOS)
            logo_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                                    size=(140, 140))
            logo_lbl = ctk.CTkLabel(card, image=logo_ctk, text="")
            logo_lbl.image = logo_ctk  # conserver la référence
            logo_lbl.place(relx=0.5, rely=0.24, anchor="center")
        except Exception:
            # fallback texte si logo introuvable
            ctk.CTkLabel(
                card, text="VIDO",
                font=ctk.CTkFont(family="Consolas", size=60, weight="bold"),
                text_color="#00d4ff",
            ).place(relx=0.5, rely=0.24, anchor="center")

        # --- Sous-titre ---
        ctk.CTkLabel(
            card,
            text="A D M I N   P A N E L",
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color="#58a6ff",
        ).place(relx=0.5, rely=0.53, anchor="center")

        # --- Version ---
        ctk.CTkLabel(
            card,
            text="v1.0.0  ·  Cybersécurité Académique",
            font=ctk.CTkFont(size=11),
            text_color="#3d4a54",
        ).place(relx=0.5, rely=0.64, anchor="center")

        # --- Barre de progression ---
        self._bar = ctk.CTkProgressBar(
            card, width=360, height=3,
            progress_color="#00d4ff", fg_color="#21262d",
        )
        self._bar.place(relx=0.5, rely=0.79, anchor="center")
        self._bar.set(0)

        # --- Status ---
        self._lbl = ctk.CTkLabel(
            card,
            text="Initialisation...",
            font=ctk.CTkFont(size=11),
            text_color="#4a5568",
        )
        self._lbl.place(relx=0.5, rely=0.90, anchor="center")

    # ------------------------------------------------------------------
    # Animation — thread de fond, MAIS mises à jour UI via after()
    # ------------------------------------------------------------------

    def _animate(self):
        steps = [
            (0.25, "Chargement de la configuration..."),
            (0.55, "Démarrage du serveur..."),
            (0.82, "Préparation de l'interface..."),
            (1.00, "Prêt."),
        ]

        def run():
            delay = self._duration / (len(steps) + 1)
            for progress, status in steps:
                time.sleep(delay)
                # Marshal vers le thread principal
                try:
                    self.after(0, lambda p=progress, s=status: self._update(p, s))
                except RuntimeError:
                    return
            time.sleep(0.5)
            try:
                self.after(0, self._finish)
            except RuntimeError:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _update(self, progress: float, status: str):
        try:
            self._bar.set(progress)
            self._lbl.configure(text=status)
        except Exception:
            pass

    def _finish(self):
        try:
            self.destroy()
        except Exception:
            pass
        self._on_done()  # appelé depuis le thread principal ✓
