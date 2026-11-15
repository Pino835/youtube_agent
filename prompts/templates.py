"""
Plantillas de prompts para la generación de metadatos con Claude,
separadas por categoría de video.

Cada plantilla recibe la descripción del video escrita por el usuario
y debe devolver un prompt completo listo para enviar a la API.
El formato de salida esperado es idéntico en todas las categorías
para que ai_generator.py pueda parsear la respuesta de forma genérica.
"""

FORMATO_SALIDA = """
Responde ÚNICAMENTE en este formato exacto, sin texto adicional antes o después:

## TITULO
(un solo título optimizado para SEO y CTR, máximo 100 caracteres)

## DESCRIPCION
(descripción completa de 3-5 párrafos cortos, que enganche desde la primera línea,
incluya palabras clave relevantes de forma natural y no spoilee todo el contenido)

## ETIQUETAS
(exactamente 15 etiquetas separadas por comas, sin el símbolo #, ordenadas de más a menos relevante)

## MINIATURA
(sugerencia breve de qué mostrar en la miniatura: composición, texto sugerido, emoción a transmitir)
"""

INSTRUCCION_BASE = """Eres un experto en optimización de contenido para YouTube (SEO, CTR y retención de audiencia).

Categoría del video: {categoria_nombre}
Descripción del video (dada por el creador): {descripcion}

{contexto_categoria}
""" + FORMATO_SALIDA


def _prompt_gaming(descripcion: str) -> str:
    contexto = (
        "Este es un video de gaming/gameplay. El título debe generar curiosidad o "
        "hype sin caer en clickbait engañoso. Usa términos que los jugadores buscarían "
        "en YouTube (nombre del juego, mecánica, boss, modo de juego, etc.)."
    )
    return INSTRUCCION_BASE.format(
        categoria_nombre="Gaming / Gameplay",
        descripcion=descripcion,
        contexto_categoria=contexto,
    )


def _prompt_vlog(descripcion: str) -> str:
    contexto = (
        "Este es un vlog personal. El título y la descripción deben sonar cercanos y "
        "auténticos, en primera persona, transmitiendo la emoción o anécdota central del video."
    )
    return INSTRUCCION_BASE.format(
        categoria_nombre="Vlog personal",
        descripcion=descripcion,
        contexto_categoria=contexto,
    )


def _prompt_futbol(descripcion: str) -> str:
    contexto = (
        "Este es un video de análisis o reacción de fútbol. Incluye nombres de equipos, "
        "jugadores o competiciones relevantes si se mencionan en la descripción, ya que "
        "son términos clave de búsqueda. El tono debe transmitir pasión futbolera."
    )
    return INSTRUCCION_BASE.format(
        categoria_nombre="Fútbol (análisis/reacción)",
        descripcion=descripcion,
        contexto_categoria=contexto,
    )


def _prompt_reaccion(descripcion: str) -> str:
    contexto = (
        "Este es un video de reacción. El título debe dejar claro a qué se está "
        "reaccionando (sin violar derechos de autor en la descripción) y transmitir "
        "la reacción emocional del creador para generar curiosidad."
    )
    return INSTRUCCION_BASE.format(
        categoria_nombre="Videoreacción",
        descripcion=descripcion,
        contexto_categoria=contexto,
    )


def _prompt_general(descripcion: str) -> str:
    contexto = (
        "Aplica buenas prácticas generales de SEO para YouTube: palabras clave "
        "relevantes en el título y primeras líneas de la descripción, y un tono "
        "acorde al contenido descrito."
    )
    return INSTRUCCION_BASE.format(
        categoria_nombre="General",
        descripcion=descripcion,
        contexto_categoria=contexto,
    )


CONSTRUCTORES_POR_CATEGORIA = {
    "gaming": _prompt_gaming,
    "vlog": _prompt_vlog,
    "futbol": _prompt_futbol,
    "reaccion": _prompt_reaccion,
    "general": _prompt_general,
}


def construir_prompt(categoria: str, descripcion: str) -> str:
    """Construye el prompt final según la categoría del video.

    Si la categoría no está registrada, cae en la plantilla general
    en vez de fallar, ya que 'general' está pensada como categoría comodín.
    """
    constructor = CONSTRUCTORES_POR_CATEGORIA.get(categoria, _prompt_general)
    return constructor(descripcion)
