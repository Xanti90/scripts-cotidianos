"""
VIGILANTE DE ARCHIVOS EN TIEMPO REAL
======================================
Observa las carpetas del usuario y renombra automáticamente
cualquier archivo nuevo que tenga un nombre horrible.

Se ejecuta en segundo plano desde el arranque del Mac.
No requiere intervención manual.

Autor: Santiago Jiménez
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Añadir el directorio actual al path para que Python encuentre renombrar_archivos
sys.path.insert(0, str(Path(__file__).parent))

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from renombrar_archivos import renombrar_archivo, CARPETAS_VIGILADAS

# ─────────────────────────────────────────────────────────────
# LOG
# ─────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "vigilante.log"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


# ─────────────────────────────────────────────────────────────
# MANEJADOR DE EVENTOS
# ─────────────────────────────────────────────────────────────

class VigilanteArchivos(FileSystemEventHandler):

    def __init__(self) -> None:
        super().__init__()
        # Cola de archivos pendientes para evitar renombrar
        # mientras el archivo aún se está escribiendo
        self._pendientes: dict = {}

    def on_created(self, event: object) -> None:
        if hasattr(event, "is_directory") and not event.is_directory:  # type: ignore[union-attr]
            self._programar(event.src_path)  # type: ignore[union-attr]

    def on_moved(self, event: object) -> None:
        if hasattr(event, "is_directory") and not event.is_directory:  # type: ignore[union-attr]
            self._programar(event.dest_path)  # type: ignore[union-attr]

    def _programar(self, ruta_str: str) -> None:
        """Espera 3 segundos antes de renombrar (el archivo puede seguir escribiéndose)."""
        self._pendientes[ruta_str] = time.time()

    def procesar_pendientes(self) -> None:
        """Procesa archivos que llevan más de 3 segundos esperando."""
        ahora = time.time()
        procesados = []

        for ruta_str, timestamp in list(self._pendientes.items()):
            if ahora - timestamp >= 3:
                ruta = Path(ruta_str)
                if ruta.exists() and ruta.is_file():
                    exito, msg = renombrar_archivo(ruta)
                    if exito and msg:
                        logging.info(msg.replace("\n", " "))
                        print(f"[{datetime.now().strftime('%H:%M:%S')}]{msg}")
                procesados.append(ruta_str)

        for ruta_str in procesados:
            self._pendientes.pop(ruta_str, None)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main() -> None:
    inicio = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n Vigilante de archivos iniciado — {inicio}")
    print(f"   Observando {len(CARPETAS_VIGILADAS)} carpetas...\n")
    logging.info(f"Vigilante iniciado — observando {len(CARPETAS_VIGILADAS)} carpetas")

    manejador = VigilanteArchivos()
    observer  = Observer()

    for carpeta in CARPETAS_VIGILADAS:
        if carpeta.exists():
            observer.schedule(manejador, str(carpeta), recursive=True)
            print(f"   - {str(carpeta).replace(str(Path.home()), '~')}")

    observer.start()
    print("\n   En espera de nuevos archivos...\n")

    try:
        while True:
            manejador.procesar_pendientes()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        logging.info("Vigilante detenido")
        print("\n   Vigilante detenido.\n")


if __name__ == "__main__":
    main()
