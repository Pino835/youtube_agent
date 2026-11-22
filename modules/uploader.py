"""
Subida de videos a YouTube usando YouTube Data API v3, con autenticación
OAuth 2.0 (flujo de aplicación instalada).
"""

import http.client
import socket
import time
from pathlib import Path
from typing import Callable, Optional

import google.auth.transport.requests
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeElapsedColumn,
    TransferSpeedColumn,
)

from modules import config
from modules.errores import ErrorArchivoNoEncontrado, ErrorConfiguracion, ErrorSubidaYouTube

# Callback de progreso: recibe (bytes_subidos, bytes_totales). Lo usa la
# interfaz gráfica para actualizar su propia barra de progreso; la interfaz
# de terminal no lo necesita porque usa la barra de 'rich' directamente.
CallbackProgreso = Callable[[int, int], None]

# Callback de reintento: recibe un mensaje de texto describiendo el corte de
# conexión y el intento actual, para que la interfaz gráfica pueda mostrarlo.
CallbackReintento = Callable[[str], None]

# Tamaño de cada fragmento al subir el video (8 MB). Con esto la subida se
# hace por partes y se puede mostrar una barra de progreso real, en vez de
# bloquearse en una sola llamada sin señal de avance (crítico para archivos
# de varios GB, donde la subida puede tardar bastante).
TAMANO_FRAGMENTO_BYTES = 8 * 1024 * 1024

# Categoría numérica genérica de YouTube ("22" = People & Blogs).
# YouTube exige un id de categoría válido; este sirve como valor por defecto
# razonable para todas las categorías de contenido del proyecto.
CATEGORIA_YOUTUBE_POR_DEFECTO = "22"

# Errores transitorios de red: en subidas de varios GB es normal que la
# conexión se corte a mitad de camino (wifi, ISP, etc.). La subida es
# resumible, así que reintentar el fragmento que falló es más barato que
# perder todo el progreso y obligar a reiniciar desde cero.
ERRORES_RED_REINTENTABLES = (
    ConnectionError,
    ConnectionResetError,
    TimeoutError,
    socket.timeout,
    http.client.IncompleteRead,
    http.client.BadStatusLine,
)
MAX_REINTENTOS = 10
ESPERA_MAXIMA_SEGUNDOS = 60


def _obtener_credenciales() -> Credentials:
    """Obtiene credenciales OAuth válidas, reutilizando el token guardado si existe.

    En el primer uso abre el navegador para que el usuario autorice la app.
    En usos posteriores reutiliza token.json y lo refresca automáticamente.
    """
    credenciales = None
    ruta_token = config.YOUTUBE_TOKEN_FILE

    if ruta_token.exists():
        credenciales = Credentials.from_authorized_user_file(str(ruta_token), config.YOUTUBE_SCOPES)

    if not credenciales or not credenciales.valid:
        if credenciales and credenciales.expired and credenciales.refresh_token:
            try:
                credenciales.refresh(google.auth.transport.requests.Request())
            except RefreshError:
                credenciales = None

        if not credenciales:
            ruta_secrets = config.DIR_RAIZ / config.YOUTUBE_CLIENT_SECRETS_FILE
            flujo = InstalledAppFlow.from_client_secrets_file(
                str(ruta_secrets), config.YOUTUBE_SCOPES
            )
            credenciales = flujo.run_local_server(port=0)

        ruta_token.write_text(credenciales.to_json(), encoding="utf-8")

    return credenciales


def _construir_servicio():
    """Crea el cliente de la YouTube Data API ya autenticado."""
    credenciales = _obtener_credenciales()
    return build(
        config.YOUTUBE_API_SERVICE_NAME,
        config.YOUTUBE_API_VERSION,
        credentials=credenciales,
    )


def subir_video(
    ruta_video: Path,
    titulo: str,
    descripcion: str,
    etiquetas: list[str],
    privacidad: str = config.PRIVACIDAD_POR_DEFECTO,
    on_progreso: Optional[CallbackProgreso] = None,
    on_reintento: Optional[CallbackReintento] = None,
) -> str:
    """Sube un video a YouTube y devuelve su videoId.

    Si se pasan on_progreso/on_reintento, se usan para reportar avance en vez
    de la barra de 'rich' (así lo usa la interfaz gráfica); si se omiten, se
    muestra una barra de progreso en la terminal (comportamiento de main.py).

    Lanza ErrorArchivoNoEncontrado, ErrorConfiguracion o ErrorSubidaYouTube
    con un mensaje claro ante errores de autenticación, cuota excedida o
    problemas de red, en vez de propagar la excepción cruda.
    """
    if not ruta_video.exists():
        raise ErrorArchivoNoEncontrado(f"No se encontró el archivo de video en '{ruta_video}'.")

    hashtags = " ".join(f"#{tag.replace(' ', '')}" for tag in etiquetas)
    descripcion_con_hashtags = f"{descripcion}\n\n{hashtags}"

    cuerpo_peticion = {
        "snippet": {
            "title": titulo,
            "description": descripcion_con_hashtags,
            "tags": etiquetas,
            "categoryId": CATEGORIA_YOUTUBE_POR_DEFECTO,
        },
        "status": {
            "privacyStatus": privacidad,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(ruta_video), chunksize=TAMANO_FRAGMENTO_BYTES, resumable=True, mimetype="video/*"
    )

    try:
        servicio = _construir_servicio()
        peticion = servicio.videos().insert(
            part="snippet,status",
            body=cuerpo_peticion,
            media_body=media,
        )
        respuesta = _ejecutar_subida_con_reintentos(
            peticion, ruta_video, on_progreso, on_reintento
        )
    except FileNotFoundError as error:
        raise ErrorConfiguracion(
            f"No se encontró el archivo de credenciales OAuth "
            f"'{config.YOUTUBE_CLIENT_SECRETS_FILE}'. Revisa el README.md."
        ) from error
    except HttpError as error:
        raise ErrorSubidaYouTube(
            f"Error de la YouTube Data API ({error.resp.status}): {error}"
        ) from error

    return respuesta["id"]


def _ejecutar_subida_con_reintentos(
    peticion,
    ruta_video: Path,
    on_progreso: Optional[CallbackProgreso],
    on_reintento: Optional[CallbackReintento],
) -> dict:
    """Ejecuta una petición de subida resumible, con reintentos ante cortes de red.

    Sube el archivo en fragmentos (en vez de una sola llamada bloqueante) para
    poder reportar avance real — necesario en archivos de varios GB, donde una
    subida sin progreso visible parece "trabada" aunque esté avanzando.

    Si un fragmento falla por un corte de conexión transitorio, reintenta ese
    mismo fragmento con espera creciente en vez de abortar toda la subida:
    en archivos de varios GB es normal que la red falle a mitad de camino,
    y la API de YouTube permite retomar la subida justo donde se quedó.

    Si se pasan callbacks (modo GUI), se usan para reportar avance/reintentos.
    Si no (modo terminal), se muestra una barra de progreso con 'rich'.
    """
    tamano_total = ruta_video.stat().st_size

    if on_progreso is not None:
        return _bucle_subida(
            peticion,
            tamano_total,
            on_progreso=on_progreso,
            on_reintento=on_reintento or (lambda _mensaje: None),
        )

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeElapsedColumn(),
    ) as progreso:
        tarea = progreso.add_task("Subiendo video...", total=tamano_total)

        def _reportar_progreso(subido: int, _total: int) -> None:
            progreso.update(tarea, completed=subido)

        def _reportar_reintento(mensaje: str) -> None:
            progreso.console.print(f"[yellow]{mensaje}[/yellow]")

        respuesta = _bucle_subida(
            peticion, tamano_total, _reportar_progreso, _reportar_reintento
        )
        progreso.update(tarea, completed=tamano_total)

    return respuesta


def _bucle_subida(
    peticion,
    tamano_total: int,
    on_progreso: CallbackProgreso,
    on_reintento: CallbackReintento,
) -> dict:
    """Bucle de subida por fragmentos compartido entre el modo terminal y GUI."""
    respuesta = None
    intentos_fallidos = 0
    max_subido = 0

    while respuesta is None:
        try:
            estado, respuesta = peticion.next_chunk()
        except ERRORES_RED_REINTENTABLES as error:
            intentos_fallidos += 1
            if intentos_fallidos > MAX_REINTENTOS:
                raise ErrorSubidaYouTube(
                    f"Se perdió la conexión repetidamente y se agotaron los "
                    f"{MAX_REINTENTOS} reintentos: {error}"
                ) from error

            espera = min(2**intentos_fallidos, ESPERA_MAXIMA_SEGUNDOS)
            on_reintento(
                f"Se cortó la conexión ({error}). "
                f"Reintentando en {espera}s (intento {intentos_fallidos}/{MAX_REINTENTOS})..."
            )
            time.sleep(espera)
            continue
        except HttpError as error:
            if error.resp.status not in (500, 502, 503, 504):
                raise ErrorSubidaYouTube(
                    f"Error de la YouTube Data API ({error.resp.status}): {error}"
                ) from error
            intentos_fallidos += 1
            if intentos_fallidos > MAX_REINTENTOS:
                raise ErrorSubidaYouTube(
                    f"El servidor de YouTube siguió fallando tras "
                    f"{MAX_REINTENTOS} reintentos: {error}"
                ) from error

            espera = min(2**intentos_fallidos, ESPERA_MAXIMA_SEGUNDOS)
            on_reintento(
                f"Error temporal del servidor de YouTube ({error.resp.status}). "
                f"Reintentando en {espera}s (intento {intentos_fallidos}/{MAX_REINTENTOS})..."
            )
            time.sleep(espera)
            continue

        intentos_fallidos = 0
        if estado:
            max_subido = max(max_subido, estado.resumable_progress)
            on_progreso(max_subido, tamano_total)

    on_progreso(tamano_total, tamano_total)
    return respuesta


def subir_miniatura(video_id: str, ruta_miniatura: Path) -> None:
    """Sube una imagen como miniatura personalizada de un video ya subido.

    Requiere que el canal tenga la verificación de teléfono habilitada en
    YouTube; si no la tiene, la API devuelve un error que se relanza aquí
    con un mensaje explicativo en vez de propagarlo crudo.
    """
    if not ruta_miniatura.exists():
        raise ErrorArchivoNoEncontrado(
            f"No se encontró la imagen de miniatura en '{ruta_miniatura}'."
        )

    media = MediaFileUpload(str(ruta_miniatura), mimetype="image/jpeg")

    try:
        servicio = _construir_servicio()
        servicio.thumbnails().set(videoId=video_id, media_body=media).execute()
    except HttpError as error:
        raise ErrorSubidaYouTube(
            f"Error al subir la miniatura ({error.resp.status}): {error}\n"
            "Nota: subir miniaturas personalizadas requiere tener la verificación "
            "de teléfono habilitada en YouTube (Configuración del canal → Función avanzada)."
        ) from error
