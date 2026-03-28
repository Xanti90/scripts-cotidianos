"""
RENOMBRADOR INTELIGENTE DE ARCHIVOS
=====================================
Analiza el contenido de cada archivo y le asigna un nombre
lógico y descriptivo automáticamente.

Soporta: imágenes, PDFs, Word, Excel, audio, vídeo y más.
Funciona en carpetas locales e iCloud Drive.

Modos:
  python3 renombrar_archivos.py              → Escanea y renombra todo
  python3 renombrar_archivos.py --simular    → Muestra qué haría sin tocar nada
  python3 renombrar_archivos.py --ruta /ruta → Renombra solo esa carpeta

Autor: Santiago Jiménez
"""

import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

# Librerías opcionales (cargadas solo si están disponibles)
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import fitz  # PyMuPDF
    FITZ_OK = True
except ImportError:
    FITZ_OK = False

try:
    from mutagen.easyid3 import EasyID3
    from mutagen.mp4 import MP4
    from mutagen.flac import FLAC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

try:
    from docx import Document
    DOCX_OK = True
except ImportError:
    DOCX_OK = False


# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────

HOME = Path.home()

CARPETAS_VIGILADAS = [
    HOME / "Downloads",
    HOME / "Desktop",
    HOME / "Documents",
    HOME / "Pictures",
    HOME / "Movies",
    HOME / "Library/Mobile Documents/com~apple~CloudDocs",
]

# Patrones de nombres MALOS que hay que renombrar
PATRONES_MALOS = [
    r"^IMG_\d+",
    r"^DSC_\d+",
    r"^DCIM",
    r"^Gemini_Generated",
    r"^Leonardo_",
    r"^Gen-3",
    r"^ScreenShot",
    r"^Screenshot",
    r"^Captura de pantalla",
    r"^Captura \d{4}",
    r"^captura",
    r"^\d{8,}$",                     # Solo números largos: 20230918094521
    r"^ACFrOg",                      # Nombres generados por Google Drive
    r"^[A-Z0-9_]{25,}$",             # Todo mayúsculas + números, muy largo
    r"%20",                          # URLs codificadas
    r"^https?",                      # URLs como nombre
    r"^[0-9a-f]{8}-[0-9a-f]{4}",    # UUIDs
    r"\.jpeg\.png$",                 # Doble extensión
]

# Extensiones por tipo
TIPOS = {
    "imagen":    {".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp", ".bmp", ".tiff", ".svg", ".nef", ".raw"},
    "pdf":       {".pdf"},
    "word":      {".docx", ".doc", ".odt", ".pages"},
    "excel":     {".xlsx", ".xls", ".csv", ".numbers"},
    "audio":     {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"},
    "video":     {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm"},
    "comprimido":{".zip", ".rar", ".tar", ".gz", ".7z", ".dmg", ".pkg"},
}

EXTENSIONES_IGNORADAS = {".py", ".sh", ".plist", ".app", ".ds_store", ".icloud"}


# ─────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────

def limpiar_texto(texto: str, max_palabras: int = 5) -> str:
    """Convierte un texto en un nombre de archivo limpio."""
    if not texto:
        return ""
    # Eliminar caracteres especiales
    texto = re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ-]", " ", texto)
    # Normalizar espacios
    texto = re.sub(r"\s+", "_", texto.strip())
    # Tomar las primeras N palabras
    partes = texto.split("_")[:max_palabras]
    resultado = "_".join(p for p in partes if p and len(p) > 1)
    # Minúsculas y sin acentos básicos para compatibilidad
    resultado = resultado.lower()
    resultado = resultado.replace("á","a").replace("é","e").replace("í","i")
    resultado = resultado.replace("ó","o").replace("ú","u").replace("ñ","n")
    return resultado[:60]  # máximo 60 caracteres


def fecha_archivo(ruta: Path) -> str:
    """Obtiene la fecha del archivo en formato YYYY-MM-DD."""
    try:
        ts = ruta.stat().st_birthtime  # fecha de creación en macOS
    except AttributeError:
        ts = ruta.stat().st_mtime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def nombre_unico(destino: Path) -> Path:
    """Si el nombre ya existe, añade un contador."""
    if not destino.exists():
        return destino
    contador = 2
    while True:
        candidato = destino.parent / f"{destino.stem}_{contador}{destino.suffix}"
        if not candidato.exists():
            return candidato
        contador += 1


def nombre_es_malo(nombre: str) -> bool:
    """Devuelve True si el nombre actual es uno de los que hay que renombrar."""
    for patron in PATRONES_MALOS:
        if re.search(patron, nombre, re.IGNORECASE):
            return True
    return False


def nombre_ya_es_bueno(nombre: str) -> bool:
    """Devuelve True si el nombre ya tiene un formato limpio (no renombrar)."""
    # Si ya empieza por fecha YYYY-MM-DD, lo dejamos
    if re.match(r"^\d{4}-\d{2}-\d{2}_", nombre):
        return True
    return False


def tipo_archivo(ruta: Path) -> str:
    ext = ruta.suffix.lower()
    for tipo, exts in TIPOS.items():
        if ext in exts:
            return tipo
    return "otro"


# ─────────────────────────────────────────────────────────────
# GENERADORES DE NOMBRE POR TIPO
# ─────────────────────────────────────────────────────────────

def nombre_imagen(ruta: Path) -> str:
    fecha = fecha_archivo(ruta)
    subtipo = "imagen"

    if PIL_OK:
        try:
            img = Image.open(ruta)
            raw_exif = img.getexif()
            exif_data = dict(raw_exif) if raw_exif else {}
            exif = {TAGS.get(k, k): v for k, v in exif_data.items()}

            # Fecha real de la foto desde EXIF
            if "DateTimeOriginal" in exif:
                try:
                    fecha = datetime.strptime(
                        str(exif["DateTimeOriginal"]), "%Y:%m:%d %H:%M:%S"
                    ).strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Determinar subtipo
            make = str(exif.get("Make", "")).lower()
            if make in ("apple", "samsung", "sony", "canon", "nikon", "google"):
                subtipo = "foto"
            elif ruta.suffix.lower() in {".heic"}:
                subtipo = "foto"
        except Exception:
            pass

    # Detectar capturas de pantalla por nombre original
    nombre_orig = ruta.stem.lower()
    if any(p in nombre_orig for p in ["screenshot", "captura", "screen"]):
        subtipo = "captura"
    elif any(p in nombre_orig for p in ["gemini", "leonardo", "gen-3", "dalle", "midjourney", "ia", "ai_"]):
        subtipo = "imagen_ia"
    elif ruta.suffix.lower() in {".nef", ".raw"}:
        subtipo = "foto_raw"

    return f"{fecha}_{subtipo}"


def nombre_pdf(ruta: Path) -> str:
    fecha = fecha_archivo(ruta)
    titulo = ""

    if FITZ_OK:
        try:
            doc = fitz.open(str(ruta))
            meta = doc.metadata or {}

            # 1. Título en metadatos
            titulo = limpiar_texto(meta.get("title", ""), max_palabras=5)

            # 2. Si no hay título, leer primera página
            if not titulo and len(doc) > 0:
                texto = doc[0].get_text("text")
                lineas = [l.strip() for l in texto.split("\n") if len(l.strip()) > 4]
                if lineas:
                    titulo = limpiar_texto(lineas[0], max_palabras=5)
            doc.close()
        except Exception:
            pass

    # Fallback: usar mdls de macOS
    if not titulo:
        try:
            resultado = subprocess.run(
                ["mdls", "-name", "kMDItemTitle", str(ruta)],
                capture_output=True, text=True, timeout=5
            )
            linea = resultado.stdout.strip()
            if "(null)" not in linea:
                titulo = limpiar_texto(linea.split("=")[-1].strip().strip('"'), max_palabras=5)
        except Exception:
            pass

    return f"{fecha}_{titulo}" if titulo else f"{fecha}_documento"


def nombre_word(ruta: Path) -> str:
    fecha = fecha_archivo(ruta)
    titulo = ""

    if DOCX_OK and ruta.suffix.lower() == ".docx":
        try:
            doc = Document(str(ruta))
            # Título en propiedades del documento
            titulo = limpiar_texto(doc.core_properties.title or "", max_palabras=5)
            # Si no, primer párrafo con contenido
            if not titulo:
                for para in doc.paragraphs:
                    if para.text.strip():
                        titulo = limpiar_texto(para.text, max_palabras=5)
                        break
        except Exception:
            pass

    return f"{fecha}_{titulo}" if titulo else f"{fecha}_documento"


def nombre_excel(ruta: Path) -> str:
    fecha = fecha_archivo(ruta)
    # Para Excel, el nombre del archivo suele ser descriptivo
    # Limpiar el nombre actual si no es terrible
    nombre_limpio = limpiar_texto(ruta.stem, max_palabras=4)
    if nombre_limpio and not nombre_es_malo(ruta.stem):
        return f"{fecha}_{nombre_limpio}"
    return f"{fecha}_tabla"


def nombre_audio(ruta: Path) -> str:
    fecha = fecha_archivo(ruta)
    artista, titulo_cancion = "", ""

    if MUTAGEN_OK:
        try:
            ext = ruta.suffix.lower()
            if ext == ".mp3":
                tags = EasyID3(str(ruta))
                artista = limpiar_texto(tags.get("artist", [""])[0], max_palabras=2)
                titulo_cancion = limpiar_texto(tags.get("title", [""])[0], max_palabras=3)
            elif ext in {".m4a", ".mp4"}:
                tags = MP4(str(ruta))
                artista = limpiar_texto(str(tags.get("\xa9ART", [""])[0]), max_palabras=2)
                titulo_cancion = limpiar_texto(str(tags.get("\xa9nam", [""])[0]), max_palabras=3)
            elif ext == ".flac":
                tags = FLAC(str(ruta))
                artista = limpiar_texto(str(tags.get("artist", [""])[0]), max_palabras=2)
                titulo_cancion = limpiar_texto(str(tags.get("title", [""])[0]), max_palabras=3)
        except Exception:
            pass

    if artista and titulo_cancion:
        return f"{artista}-{titulo_cancion}"
    elif titulo_cancion:
        return titulo_cancion
    return f"{fecha}_audio"


def nombre_video(ruta: Path) -> str:
    fecha = fecha_archivo(ruta)
    titulo = ""

    # Intentar leer metadatos con mdls
    try:
        resultado = subprocess.run(
            ["mdls", "-name", "kMDItemTitle", str(ruta)],
            capture_output=True, text=True, timeout=5
        )
        linea = resultado.stdout.strip()
        if "(null)" not in linea and "=" in linea:
            titulo = limpiar_texto(linea.split("=")[-1].strip().strip('"'), max_palabras=4)
    except Exception:
        pass

    return f"{fecha}_{titulo}" if titulo else f"{fecha}_video"


def nombre_generico(ruta: Path) -> str:
    fecha = fecha_archivo(ruta)
    return f"{fecha}_archivo"


# ─────────────────────────────────────────────────────────────
# MOTOR PRINCIPAL
# ─────────────────────────────────────────────────────────────

def generar_nombre(ruta: Path) -> Optional[str]:
    """Genera el nuevo nombre para un archivo. Devuelve None si no hay que renombrarlo."""
    nombre = ruta.name
    ext = ruta.suffix.lower()

    # Ignorar archivos del sistema, ocultos o con extensión excluida
    if nombre.startswith(".") or ext in EXTENSIONES_IGNORADAS:
        return None

    # Ignorar archivos de iCloud no descargados (.icloud placeholder)
    if nombre.endswith(".icloud"):
        return None

    # Si el nombre ya es bueno, no tocarlo
    if nombre_ya_es_bueno(ruta.stem):
        return None

    # Si el nombre no es malo y no es un patrón conocido, no tocarlo
    if not nombre_es_malo(nombre):
        return None

    # Generar nombre según tipo
    tipo = tipo_archivo(ruta)
    if tipo == "imagen":
        base = nombre_imagen(ruta)
    elif tipo == "pdf":
        base = nombre_pdf(ruta)
    elif tipo == "word":
        base = nombre_word(ruta)
    elif tipo == "excel":
        base = nombre_excel(ruta)
    elif tipo == "audio":
        base = nombre_audio(ruta)
    elif tipo == "video":
        base = nombre_video(ruta)
    elif tipo == "comprimido":
        return None  # No renombrar instaladores/comprimidos
    else:
        base = nombre_generico(ruta)

    if not base:
        return None

    return f"{base}{ext}"


def renombrar_archivo(ruta: Path, simular: bool = False) -> Tuple[bool, str]:
    """Renombra un archivo. Devuelve (éxito, mensaje)."""
    try:
        nuevo_nombre = generar_nombre(ruta)
        if not nuevo_nombre:
            return False, ""

        destino = nombre_unico(ruta.parent / nuevo_nombre)

        if simular:
            return True, f"  ~  {ruta.name}\n     → {destino.name}"

        ruta.rename(destino)
        return True, f"  ✓  {ruta.name}\n     → {destino.name}"

    except Exception as e:
        return False, f"  ✗  {ruta.name} — {e}"


def procesar_carpeta(carpeta: Path, simular: bool = False) -> int:
    """Procesa todos los archivos de una carpeta recursivamente."""
    if not carpeta.exists():
        return 0

    total = 0
    try:
        for ruta in sorted(carpeta.rglob("*")):
            if ruta.is_file():
                exito, msg = renombrar_archivo(ruta, simular)
                if exito and msg:
                    print(msg)
                    total += 1
    except PermissionError:
        pass
    return total


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    simular  = "--simular" in sys.argv
    ruta_arg = None
    if "--ruta" in sys.argv:
        idx = sys.argv.index("--ruta")
        if idx + 1 < len(sys.argv):
            ruta_arg = Path(sys.argv[idx + 1])

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    modo  = "SIMULACIÓN (sin cambios)" if simular else "RENOMBRANDO"

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║      RENOMBRADOR INTELIGENTE DE ARCHIVOS         ║")
    print(f"║      {ahora} — {modo:<21}║")
    print("╚══════════════════════════════════════════════════╝\n")

    carpetas = [ruta_arg] if ruta_arg else CARPETAS_VIGILADAS
    total_global = 0

    for carpeta in carpetas:
        if not carpeta.exists():
            continue
        nombre_display = str(carpeta).replace(str(HOME), "~")
        print(f"📂 {nombre_display}")
        n = procesar_carpeta(carpeta, simular)
        if n == 0:
            print("   ✓ Todos los archivos ya tienen buen nombre\n")
        else:
            print(f"   → {n} archivo(s) procesado(s)\n")
        total_global += n

    print("─" * 52)
    accion = "renombraría" if simular else "renombrados"
    print(f"  Total {accion}: {total_global} archivo(s)")
    print("─" * 52)
    if total_global > 0 and not simular:
        print("\n✅ ¡Archivos renombrados correctamente!\n")
    elif total_global == 0:
        print("\n✅ Todo estaba en orden, nada que cambiar.\n")


if __name__ == "__main__":
    main()
