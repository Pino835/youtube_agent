"""
Generación de metadatos de video (título, descripción, etiquetas y
brief de miniatura) usando la API de Claude.
"""

import re
from dataclasses import dataclass

import anthropic

from modules import config
from modules.errores import ErrorGeneracionIA
from prompts.templates import construir_prompt


@dataclass
class MetadatosVideo:
    """Resultado estructurado de la generación de metadatos."""

    titulo: str
    descripcion: str
    etiquetas: list[str]
    brief_miniatura: str


def _extraer_seccion(texto: str, nombre_seccion: str) -> str:
    """Extrae el contenido de una sección '## NOMBRE' de la respuesta de Claude."""
    patron = rf"##\s*{nombre_seccion}\s*\n(.*?)(?=\n##\s|\Z)"
    coincidencia = re.search(patron, texto, re.DOTALL | re.IGNORECASE)
    if not coincidencia:
        return ""
    return coincidencia.group(1).strip()


def _parsear_respuesta(texto: str) -> MetadatosVideo:
    """Convierte la respuesta en texto plano de Claude en un objeto estructurado."""
    titulo = _extraer_seccion(texto, "TITULO")
    descripcion = _extraer_seccion(texto, "DESCRIPCION")
    etiquetas_raw = _extraer_seccion(texto, "ETIQUETAS")
    brief_miniatura = _extraer_seccion(texto, "MINIATURA")

    etiquetas = [
        etiqueta.strip().lstrip("#")
        for etiqueta in etiquetas_raw.split(",")
        if etiqueta.strip()
    ]

    if not titulo or not descripcion:
        raise ValueError(
            "La respuesta de Claude no tiene el formato esperado. "
            "Respuesta recibida:\n" + texto
        )

    return MetadatosVideo(
        titulo=titulo,
        descripcion=descripcion,
        etiquetas=etiquetas[: config.CANTIDAD_ETIQUETAS],
        brief_miniatura=brief_miniatura,
    )


def generar_metadatos(categoria: str, descripcion_usuario: str) -> MetadatosVideo:
    """Llama a la API de Claude y devuelve los metadatos generados para el video.

    Lanza ErrorGeneracionIA con un mensaje claro si la llamada a la API falla
    o si la respuesta no se puede interpretar, en vez de propagar una
    excepción críptica de la librería anthropic.
    """
    prompt = construir_prompt(categoria, descripcion_usuario)
    cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    try:
        mensaje = cliente.messages.create(
            model=config.MODELO_CLAUDE,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as error:
        raise ErrorGeneracionIA(f"Error de conexión con la API de Claude: {error}") from error
    except anthropic.RateLimitError as error:
        raise ErrorGeneracionIA(
            "Se alcanzó el límite de peticiones de la API de Claude."
        ) from error
    except anthropic.APIStatusError as error:
        raise ErrorGeneracionIA(
            f"Error de la API de Claude ({error.status_code}): {error.message}"
        ) from error

    texto_respuesta = mensaje.content[0].text

    try:
        return _parsear_respuesta(texto_respuesta)
    except ValueError as error:
        raise ErrorGeneracionIA(f"Error al interpretar la respuesta de Claude: {error}") from error
