"""
CLI principal de YouTube Automation Suite.

Flujo:
1. El usuario describe su video y elige una categoría.
2. Se generan título, descripción, etiquetas y brief de miniatura con Claude.
3. Se muestra el resultado en la terminal y se permite editar el título.
4. Se guardan todos los metadatos (título, descripción, etiquetas, brief) en salidas/.
5. Se sube el video a YouTube como privado (o el usuario cancela la subida).
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

from modules import config, thumbnail, uploader
from modules.ai_generator import generar_metadatos
from modules.errores import (
    ErrorArchivoNoEncontrado,
    ErrorConfiguracion,
    ErrorGeneracionIA,
    ErrorSubidaYouTube,
)

consola = Console()


def elegir_categoria() -> str:
    """Pide al usuario que elija una categoría de video de la lista soportada."""
    claves_categorias = list(config.CATEGORIAS.keys())

    consola.print("\n[bold cyan]Categorías disponibles:[/bold cyan]")
    for indice, clave in enumerate(claves_categorias, start=1):
        consola.print(f"  {indice}. [bold]{clave}[/bold] — {config.CATEGORIAS[clave]}")

    indice_elegido = IntPrompt.ask(
        "\nElige el número de categoría",
        choices=[str(i) for i in range(1, len(claves_categorias) + 1)],
        show_choices=False,
    )
    return claves_categorias[indice_elegido - 1]


def mostrar_metadatos(metadatos) -> None:
    """Muestra el resultado generado por la IA con formato visual."""
    consola.print(Panel(metadatos.titulo, title="Título", border_style="green"))
    consola.print(Panel(metadatos.descripcion, title="Descripción", border_style="blue"))
    consola.print(
        Panel(", ".join(metadatos.etiquetas), title="Etiquetas", border_style="magenta")
    )
    consola.print(
        Panel(metadatos.brief_miniatura, title="Sugerencia de miniatura", border_style="yellow")
    )


def confirmar_o_editar_titulo(titulo: str) -> str:
    """Permite al usuario aceptar el título generado o escribir uno propio."""
    if Confirm.ask("\n¿Quieres editar el título antes de continuar?", default=False):
        return Prompt.ask("Nuevo título", default=titulo)
    return titulo


def _limpiar_ruta(texto: str) -> Path:
    """Convierte texto pegado por el usuario en una ruta válida.

    Quita comillas envolventes (dobles o simples) y espacios extra, ya que
    es común que al copiar una ruta desde el Explorador de Windows se
    incluyan comillas, lo que hace que Path() no encuentre el archivo
    aunque la ruta sea correcta.
    """
    texto_limpio = texto.strip().strip('"').strip("'").strip()
    return Path(texto_limpio)


def pedir_ruta_existente(mensaje: str, permitir_vacio: bool = False) -> Path | None:
    """Pide una ruta de archivo al usuario, reintentando si no existe.

    Evita que un solo error de tipeo (o comillas pegadas de más) obligue a
    reiniciar todo el programa desde cero, ya que llegar hasta este punto
    implica haber generado los metadatos con Claude.
    """
    while True:
        texto = Prompt.ask(mensaje, default="" if permitir_vacio else ...)
        if permitir_vacio and not texto:
            return None

        ruta = _limpiar_ruta(texto)
        if ruta.exists():
            return ruta

        consola.print(
            f"[red]No se encontró ningún archivo en:[/red] {ruta}\n"
            "[dim]Revisa que la ruta esté completa (incluyendo el nombre del archivo y su extensión) "
            "y que el archivo siga existiendo ahí.[/dim]"
        )


def main() -> None:
    consola.rule("[bold]YouTube Automation Suite[/bold]")

    config.validar_configuracion_ia()

    descripcion_usuario = Prompt.ask(
        "\n[bold]Describe tu video[/bold] (de qué trata, momentos clave, etc.)"
    )
    categoria = elegir_categoria()

    with consola.status("[bold green]Generando título, descripción y etiquetas con Claude..."):
        metadatos = generar_metadatos(categoria, descripcion_usuario)

    mostrar_metadatos(metadatos)
    metadatos.titulo = confirmar_o_editar_titulo(metadatos.titulo)

    ruta_metadatos = thumbnail.guardar_metadatos(metadatos)
    consola.print(f"\n[dim]Metadatos guardados en: {ruta_metadatos}[/dim]")

    if not Confirm.ask("\n¿Quieres subir el video a YouTube ahora?", default=False):
        consola.print("[yellow]Subida cancelada. Puedes subir el video manualmente cuando quieras.[/yellow]")
        return

    ruta_video = pedir_ruta_existente("Ruta del archivo de video a subir")

    config.validar_configuracion_youtube()

    consola.print("\n[bold green]Subiendo video a YouTube...[/bold green]")
    video_id = uploader.subir_video(
        ruta_video=ruta_video,
        titulo=metadatos.titulo,
        descripcion=metadatos.descripcion,
        etiquetas=metadatos.etiquetas,
    )

    url_video = f"https://youtu.be/{video_id}"
    consola.print(
        Panel(
            f"Video subido como privado.\nID: {video_id}\nURL: {url_video}",
            title="Subida completada",
            border_style="green",
        )
    )

    ruta_miniatura = pedir_ruta_existente(
        "\nRuta de la imagen de miniatura ya diseñada (Enter para saltar)",
        permitir_vacio=True,
    )
    if ruta_miniatura:
        with consola.status("[bold green]Subiendo miniatura..."):
            uploader.subir_miniatura(video_id, ruta_miniatura)
        consola.print("[green]Miniatura subida correctamente.[/green]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        sys.exit(0)
    except (
        ErrorConfiguracion,
        ErrorGeneracionIA,
        ErrorSubidaYouTube,
        ErrorArchivoNoEncontrado,
    ) as error:
        print(f"\nError: {error}", file=sys.stderr)
        sys.exit(1)
