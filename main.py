import logging
import sys
import threading
import traceback
import faulthandler
import customtkinter as ctk
from gui.app import App

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("vido")


def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    # Always print the full traceback so crashes are visible in the terminal.
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical("Exception non interceptee:\n%s", tb)


def _threading_excepthook(args: threading.ExceptHookArgs):
    _log_unhandled_exception(args.exc_type, args.exc_value, args.exc_traceback)


sys.excepthook = _log_unhandled_exception
threading.excepthook = _threading_excepthook

try:
    # Print native crashes (segfault/access violation) to the current terminal.
    faulthandler.enable(all_threads=True)
except Exception:
    logger.warning("Impossible d'activer faulthandler.")

if __name__ == "__main__":
    try:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        App().mainloop()
    except KeyboardInterrupt:
        logger.info("Arret demande par l'utilisateur.")
    except Exception:
        logger.exception("Crash de l'application.")
        raise
