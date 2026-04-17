from pathlib import Path

import customtkinter as ctk
from PIL import Image as PILImage, ImageTk

from .splash import SplashScreen
from .main_window import MainWindow
from core.server import Server
from core.agent_manager import AgentManager
import config

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        self._server = Server(config.SERVER_HOST, config.SERVER_PORT)
        self._manager = AgentManager(self._server)

        self.title(config.APP_NAME)
        self.geometry("1280x760")
        self.minsize(960, 600)
        self.configure(fg_color="#0d1117")

        # Icône de fenêtre (logo VIDO)
        try:
            icon_img = PILImage.open(_LOGO_PATH).resize((32, 32), PILImage.LANCZOS)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.after(100, lambda: self.iconphoto(True, self._icon_photo))
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_splash()

    def _show_splash(self):
        SplashScreen(self, on_done=self._after_splash)

    def _after_splash(self):
        """Appelé depuis le thread principal via after() dans SplashScreen._finish()."""
        self._server.start()
        main = MainWindow(self, self._manager)
        main.pack(fill="both", expand=True)
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self):
        self._server.stop()
        self.destroy()
