"""
Excepciones propias del proyecto.

Se usan en vez de sys.exit() dentro de los módulos de lógica (config,
ai_generator, uploader, thumbnail) para que tanto la interfaz de terminal
(main.py) como la interfaz gráfica (gui.py) puedan capturarlas y mostrar
el error de la forma que corresponda a cada una, sin que un error cierre
todo el proceso de golpe.
"""


class ErrorConfiguracion(Exception):
    """Falta una variable de entorno o un archivo de configuración requerido."""


class ErrorGeneracionIA(Exception):
    """Falló la llamada a la API de Claude o el parseo de su respuesta."""


class ErrorSubidaYouTube(Exception):
    """Falló la autenticación o la subida a la YouTube Data API."""


class ErrorArchivoNoEncontrado(Exception):
    """La ruta de un archivo requerido (video, miniatura) no existe."""
