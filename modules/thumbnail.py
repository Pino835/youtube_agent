"""
Guardado en disco de los metadatos generados por la IA (título, descripción,
etiquetas y brief de miniatura), para que no se pierdan si algo falla
durante la subida a YouTube.
"""

import re
from datetime import datetime
from pathlib import Path

from modules import config
from modules.errores import ErrorConfiguracion


def _generar_nombre_archivo(titulo: str) -> str:
    """Genera un nombre de archivo seguro a partir del título del video."""
    base = re.sub(r"[^\w\s-]", "", titulo).strip().lower()
    base = re.sub(r"[\s]+", "_", base)[:50] or "video"
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{marca_tiempo}_{base}_metadatos.txt"


def guardar_metadatos(metadatos) -> Path:
    """Guarda título, descripción, etiquetas y brief de miniatura en salidas/.

    Se guarda ANTES de intentar subir el video, para que si la subida falla
    (conexión, cuota, etc.) el usuario no tenga que volver a generar los
    metadatos desde cero ni copiarlos manualmente de la terminal.

    Termina el programa con un mensaje claro si no se puede escribir el
    archivo (p. ej. permisos de disco), en vez de fallar silenciosamente.
    """
    config.DIR_SALIDAS.mkdir(parents=True, exist_ok=True)
    ruta_archivo = config.DIR_SALIDAS / _generar_nombre_archivo(metadatos.titulo)

    contenido = (
        f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'=' * 60}\n\n"
        f"TÍTULO\n{'-' * 60}\n{metadatos.titulo}\n\n"
        f"DESCRIPCIÓN\n{'-' * 60}\n{metadatos.descripcion}\n\n"
        f"ETIQUETAS\n{'-' * 60}\n{', '.join(metadatos.etiquetas)}\n\n"
        f"SUGERENCIA DE MINIATURA\n{'-' * 60}\n{metadatos.brief_miniatura}\n"
    )

    try:
        ruta_archivo.write_text(contenido, encoding="utf-8")
    except OSError as error:
        raise ErrorConfiguracion(f"Error al guardar los metadatos: {error}") from error

    return ruta_archivo
