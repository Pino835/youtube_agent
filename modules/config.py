"""
Configuración central del proyecto: variables de entorno, constantes
y categorías de video soportadas.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from modules.errores import ErrorConfiguracion

load_dotenv()

# --- Rutas base ---
DIR_RAIZ = Path(__file__).resolve().parent.parent
DIR_SALIDAS = DIR_RAIZ / "salidas"

# --- API de Claude ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODELO_CLAUDE = "claude-sonnet-4-6"

# --- YouTube Data API v3 ---
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secret.json")
YOUTUBE_TOKEN_FILE = DIR_RAIZ / "token.json"
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Estado de privacidad por defecto al subir un video.
# Regla del proyecto: nunca publicar automáticamente en público.
PRIVACIDAD_POR_DEFECTO = "private"

# --- Categorías de video soportadas ---
CATEGORIAS = {
    "gaming": "Videojuegos y gameplay",
    "vlog": "Vlogs personales, día a día",
    "futbol": "Análisis y reacciones de fútbol",
    "reaccion": "Videoreacciones",
    "general": "Cualquier otro tipo de contenido",
}

CANTIDAD_ETIQUETAS = 15


def validar_configuracion_ia() -> None:
    """Verifica que la clave de la API de Claude esté configurada.

    Lanza ErrorConfiguracion con un mensaje claro si falta, en vez de
    fallar más adelante con un error críptico de la librería anthropic.
    """
    if not ANTHROPIC_API_KEY:
        raise ErrorConfiguracion(
            "No se encontró ANTHROPIC_API_KEY.\n"
            "Copia .env.example como .env y completa tu clave de la API de Anthropic."
        )


def validar_configuracion_youtube() -> None:
    """Verifica que exista el archivo de credenciales OAuth de YouTube."""
    ruta_credenciales = DIR_RAIZ / YOUTUBE_CLIENT_SECRETS_FILE
    if not ruta_credenciales.exists():
        raise ErrorConfiguracion(
            f"No se encontró el archivo de credenciales OAuth en '{ruta_credenciales}'.\n"
            "Revisa el README.md para generar el archivo client_secret.json desde Google Cloud Console."
        )
