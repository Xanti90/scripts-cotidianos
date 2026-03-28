"""
ORGANIZADOR AUTOMÁTICO DE DESCARGAS
=====================================
Organiza automáticamente los archivos de:
  - ~/Downloads  (carpeta local)
  - iCloud Drive/Downloads  (si existe)

Mueve cada archivo a una subcarpeta según su tipo.
Se puede ejecutar manualmente o corre solo cada día.

Autor: Santiago Jiménez
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────
# CONFIGURACIÓN: categorías y sus extensiones
# ─────────────────────────────────────────────────────
CATEGORIAS = {
    "Imágenes":     [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tiff"],
    "Documentos":   [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
                     ".txt", ".csv", ".odt", ".pages", ".numbers", ".key"],
    "Vídeos":       [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"],
    "Audio":        [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"],
    "Comprimidos":  [".zip", ".rar", ".tar", ".gz", ".7z", ".dmg", ".pkg"],
    "Código":       [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".sh", ".yaml", ".yml"],
    "Otros":        []
}

# Carpetas a organizar
CARPETAS_OBJETIVO = [
    Path.home() / "Downloads",
    Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Downloads",
]


def obtener_categoria(extension: str) -> str:
    ext = extension.lower()
    for categoria, extensiones in CATEGORIAS.items():
        if ext in extensiones:
            return categoria
    return "Otros"


def organizar_carpeta(carpeta: Path) -> dict:
    """Organiza una carpeta y devuelve estadísticas."""
    if not carpeta.exists():
        return {}

    archivos = [f for f in carpeta.iterdir() if f.is_file() and not f.name.startswith(".")]
    if not archivos:
        print(f"  ✓ Ya estaba vacía\n")
        return {}

    print(f"  📋 {len(archivos)} archivo(s) encontrado(s)\n")

    resumen = {}
    movidos = 0
    errores = 0

    for archivo in sorted(archivos, key=lambda f: f.name.lower()):
        categoria = obtener_categoria(archivo.suffix)
        destino_carpeta = carpeta / categoria
        destino_carpeta.mkdir(exist_ok=True)

        destino = destino_carpeta / archivo.name
        contador = 1
        while destino.exists():
            destino = destino_carpeta / f"{archivo.stem}_{contador}{archivo.suffix}"
            contador += 1

        try:
            shutil.move(str(archivo), str(destino))
            print(f"  ✓  {archivo.name}")
            print(f"     └─ {categoria}/")
            resumen[categoria] = resumen.get(categoria, 0) + 1
            movidos += 1
        except Exception as e:
            print(f"  ✗  {archivo.name}")
            print(f"     └─ Error: {e}")
            errores += 1

    print(f"\n  Movidos: {movidos}  |  Errores: {errores}")
    return resumen


def main():
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     ORGANIZADOR DE DESCARGAS                 ║")
    print(f"║     {ahora:<41}║")
    print("╚══════════════════════════════════════════════╝\n")

    resumen_total = {}

    for carpeta in CARPETAS_OBJETIVO:
        if carpeta.exists():
            nombre = "iCloud Drive/Downloads" if "CloudDocs" in str(carpeta) else "~/Downloads"
            print(f"📂 {nombre}")
            print(f"   {carpeta}\n")
            resumen = organizar_carpeta(carpeta)
            for k, v in resumen.items():
                resumen_total[k] = resumen_total.get(k, 0) + v
        else:
            nombre = "iCloud Drive/Downloads" if "CloudDocs" in str(carpeta) else "~/Downloads"
            print(f"📂 {nombre} — no encontrada, se omite\n")

    if resumen_total:
        print("\n╔══════════════════════════════════════════════╗")
        print("║  RESUMEN FINAL                               ║")
        print("╠══════════════════════════════════════════════╣")
        for categoria, cantidad in sorted(resumen_total.items()):
            linea = f"  📁 {categoria:<16} {cantidad} archivo(s)"
            print(f"║ {linea:<44}║")
        print("╚══════════════════════════════════════════════╝")
        print("\n✅ ¡Descargas organizadas perfectamente!\n")
    else:
        print("✅ Todo ya estaba organizado, nada que hacer.\n")


if __name__ == "__main__":
    main()
