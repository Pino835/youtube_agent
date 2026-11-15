"""
Interfaz gráfica de YouTube Automation Suite (PySide6/Qt).

Reutiliza toda la lógica de modules/ y prompts/ tal cual la usa main.py
(terminal); esta ventana solo reemplaza la capa de interacción.

La generación de metadatos y la subida a YouTube se ejecutan en hilos
aparte (QThread) para no congelar la ventana durante llamadas largas
(la subida de un video de varios GB puede tardar horas).
"""

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from modules import config, thumbnail, uploader
from modules.ai_generator import MetadatosVideo, generar_metadatos
from modules.errores import (
    ErrorArchivoNoEncontrado,
    ErrorConfiguracion,
    ErrorGeneracionIA,
    ErrorSubidaYouTube,
)

FILTRO_VIDEOS = "Videos (*.mp4 *.mov *.mkv *.avi *.wmv);;Todos los archivos (*.*)"
FILTRO_IMAGENES = "Imágenes (*.jpg *.jpeg *.png);;Todos los archivos (*.*)"


class HiloGeneracion(QThread):
    """Ejecuta la llamada a la API de Claude sin bloquear la ventana."""

    exito = Signal(object)
    error = Signal(str)

    def __init__(self, categoria: str, descripcion: str):
        super().__init__()
        self._categoria = categoria
        self._descripcion = descripcion

    def run(self) -> None:
        try:
            metadatos = generar_metadatos(self._categoria, self._descripcion)
        except ErrorGeneracionIA as error:
            self.error.emit(str(error))
            return
        self.exito.emit(metadatos)


class HiloSubida(QThread):
    """Ejecuta la subida de video (y miniatura opcional) sin bloquear la ventana."""

    progreso = Signal(float, float)
    reintento = Signal(str)
    video_subido = Signal(str)
    exito = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        ruta_video: Path,
        titulo: str,
        descripcion: str,
        etiquetas: list[str],
        ruta_miniatura: Path | None,
    ):
        super().__init__()
        self._ruta_video = ruta_video
        self._titulo = titulo
        self._descripcion = descripcion
        self._etiquetas = etiquetas
        self._ruta_miniatura = ruta_miniatura

    def run(self) -> None:
        try:
            video_id = uploader.subir_video(
                ruta_video=self._ruta_video,
                titulo=self._titulo,
                descripcion=self._descripcion,
                etiquetas=self._etiquetas,
                on_progreso=lambda subido, total: self.progreso.emit(subido / (1024**3), total / (1024**3)),
                on_reintento=lambda mensaje: self.reintento.emit(mensaje),
            )
            self.video_subido.emit(video_id)

            if self._ruta_miniatura is not None:
                uploader.subir_miniatura(video_id, self._ruta_miniatura)

        except (ErrorConfiguracion, ErrorSubidaYouTube, ErrorArchivoNoEncontrado) as error:
            self.error.emit(str(error))
            return

        self.exito.emit(f"https://youtu.be/{video_id}")


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Automation Suite")
        self.resize(720, 800)

        self._metadatos: MetadatosVideo | None = None
        self._ruta_video: Path | None = None
        self._ruta_miniatura: Path | None = None
        self._hilo_generacion: HiloGeneracion | None = None
        self._hilo_subida: HiloSubida | None = None

        self._construir_interfaz()

    def _construir_interfaz(self) -> None:
        contenedor = QWidget()
        layout_principal = QVBoxLayout(contenedor)

        layout_principal.addWidget(self._crear_grupo_entrada())
        layout_principal.addWidget(self._crear_grupo_archivos())
        layout_principal.addWidget(self._crear_grupo_metadatos())
        layout_principal.addWidget(self._crear_grupo_subida())

        area_scroll = QScrollArea()
        area_scroll.setWidgetResizable(True)
        area_scroll.setWidget(contenedor)
        self.setCentralWidget(area_scroll)

    def _crear_grupo_entrada(self) -> QGroupBox:
        grupo = QGroupBox("1. Describe tu video")
        layout = QFormLayout(grupo)

        self.campo_descripcion = QPlainTextEdit()
        self.campo_descripcion.setPlaceholderText(
            "De qué trata el video, momentos clave, etc."
        )
        self.campo_descripcion.setFixedHeight(80)
        layout.addRow("Descripción:", self.campo_descripcion)

        self.combo_categoria = QComboBox()
        for clave, nombre in config.CATEGORIAS.items():
            self.combo_categoria.addItem(f"{clave} — {nombre}", userData=clave)
        layout.addRow("Categoría:", self.combo_categoria)

        self.boton_generar = QPushButton("Generar título, descripción y etiquetas")
        self.boton_generar.clicked.connect(self._on_generar_metadatos)
        layout.addRow(self.boton_generar)

        self.etiqueta_estado_generacion = QLabel("")
        layout.addRow(self.etiqueta_estado_generacion)

        return grupo

    def _crear_grupo_archivos(self) -> QGroupBox:
        grupo = QGroupBox("2. Adjunta tus archivos")
        layout = QFormLayout(grupo)

        self.campo_ruta_video = QLineEdit()
        self.campo_ruta_video.setReadOnly(True)
        boton_video = QPushButton("Seleccionar video...")
        boton_video.clicked.connect(self._on_seleccionar_video)
        layout.addRow(boton_video, self.campo_ruta_video)

        self.campo_ruta_miniatura = QLineEdit()
        self.campo_ruta_miniatura.setReadOnly(True)
        boton_miniatura = QPushButton("Seleccionar miniatura (opcional)...")
        boton_miniatura.clicked.connect(self._on_seleccionar_miniatura)
        layout.addRow(boton_miniatura, self.campo_ruta_miniatura)

        return grupo

    def _crear_grupo_metadatos(self) -> QGroupBox:
        grupo = QGroupBox("3. Revisa y edita")
        layout = QFormLayout(grupo)

        self.campo_titulo = QLineEdit()
        layout.addRow("Título:", self.campo_titulo)

        self.campo_descripcion_generada = QPlainTextEdit()
        self.campo_descripcion_generada.setFixedHeight(120)
        layout.addRow("Descripción:", self.campo_descripcion_generada)

        self.campo_etiquetas = QLineEdit()
        layout.addRow("Etiquetas (separadas por comas):", self.campo_etiquetas)

        self.campo_brief_miniatura = QPlainTextEdit()
        self.campo_brief_miniatura.setFixedHeight(80)
        self.campo_brief_miniatura.setReadOnly(True)
        layout.addRow("Sugerencia de miniatura:", self.campo_brief_miniatura)

        return grupo

    def _crear_grupo_subida(self) -> QGroupBox:
        grupo = QGroupBox("4. Subir a YouTube")
        layout = QVBoxLayout(grupo)

        self.boton_subir = QPushButton("Subir video a YouTube (privado)")
        self.boton_subir.clicked.connect(self._on_subir_video)
        layout.addWidget(self.boton_subir)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 100)
        layout.addWidget(self.barra_progreso)

        self.etiqueta_estado_subida = QLabel("")
        self.etiqueta_estado_subida.setWordWrap(True)
        layout.addWidget(self.etiqueta_estado_subida)

        return grupo

    # --- Selección de archivos ---

    def _on_seleccionar_video(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Selecciona el video", "", FILTRO_VIDEOS)
        if ruta:
            self._ruta_video = Path(ruta)
            self.campo_ruta_video.setText(ruta)

    def _on_seleccionar_miniatura(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Selecciona la miniatura", "", FILTRO_IMAGENES
        )
        if ruta:
            self._ruta_miniatura = Path(ruta)
            self.campo_ruta_miniatura.setText(ruta)

    # --- Generación de metadatos ---

    def _on_generar_metadatos(self) -> None:
        try:
            config.validar_configuracion_ia()
        except ErrorConfiguracion as error:
            QMessageBox.critical(self, "Falta configuración", str(error))
            return

        descripcion = self.campo_descripcion.toPlainText().strip()
        if not descripcion:
            QMessageBox.warning(self, "Falta información", "Describe tu video antes de generar.")
            return

        categoria = self.combo_categoria.currentData()

        self.boton_generar.setEnabled(False)
        self.etiqueta_estado_generacion.setText("Generando con Claude...")

        self._hilo_generacion = HiloGeneracion(categoria, descripcion)
        self._hilo_generacion.exito.connect(self._on_generacion_exitosa)
        self._hilo_generacion.error.connect(self._on_generacion_fallida)
        self._hilo_generacion.start()

    def _on_generacion_exitosa(self, metadatos: MetadatosVideo) -> None:
        self._metadatos = metadatos
        self.campo_titulo.setText(metadatos.titulo)
        self.campo_descripcion_generada.setPlainText(metadatos.descripcion)
        self.campo_etiquetas.setText(", ".join(metadatos.etiquetas))
        self.campo_brief_miniatura.setPlainText(metadatos.brief_miniatura)

        self.boton_generar.setEnabled(True)
        self.etiqueta_estado_generacion.setText("Listo. Puedes editar los campos antes de subir.")

    def _on_generacion_fallida(self, mensaje: str) -> None:
        self.boton_generar.setEnabled(True)
        self.etiqueta_estado_generacion.setText("")
        QMessageBox.critical(self, "Error al generar metadatos", mensaje)

    # --- Subida a YouTube ---

    def _on_subir_video(self) -> None:
        if self._metadatos is None:
            QMessageBox.warning(
                self, "Faltan metadatos", "Primero genera el título y la descripción."
            )
            return

        if self._ruta_video is None:
            QMessageBox.warning(self, "Falta el video", "Selecciona el archivo de video a subir.")
            return

        try:
            config.validar_configuracion_youtube()
        except ErrorConfiguracion as error:
            QMessageBox.critical(self, "Falta configuración", str(error))
            return

        titulo = self.campo_titulo.text().strip()
        descripcion = self.campo_descripcion_generada.toPlainText().strip()
        etiquetas = [e.strip() for e in self.campo_etiquetas.text().split(",") if e.strip()]

        if not titulo:
            QMessageBox.warning(self, "Falta el título", "El título no puede estar vacío.")
            return

        self._metadatos.titulo = titulo
        self._metadatos.descripcion = descripcion
        self._metadatos.etiquetas = etiquetas

        try:
            ruta_guardado = thumbnail.guardar_metadatos(self._metadatos)
            self.etiqueta_estado_subida.setText(f"Metadatos guardados en: {ruta_guardado}")
        except ErrorConfiguracion as error:
            QMessageBox.critical(self, "Error al guardar metadatos", str(error))
            return

        self.boton_subir.setEnabled(False)
        self.barra_progreso.setValue(0)

        self._hilo_subida = HiloSubida(
            ruta_video=self._ruta_video,
            titulo=titulo,
            descripcion=descripcion,
            etiquetas=etiquetas,
            ruta_miniatura=self._ruta_miniatura,
        )
        self._hilo_subida.progreso.connect(self._on_progreso_subida)
        self._hilo_subida.reintento.connect(self._on_reintento_subida)
        self._hilo_subida.video_subido.connect(self._on_video_subido)
        self._hilo_subida.exito.connect(self._on_subida_exitosa)
        self._hilo_subida.error.connect(self._on_subida_fallida)
        self._hilo_subida.start()

    def _on_progreso_subida(self, gb_subido: float, gb_total: float) -> None:
        porcentaje = int((gb_subido / gb_total) * 100) if gb_total else 0
        self.barra_progreso.setValue(porcentaje)
        self.etiqueta_estado_subida.setText(
            f"Subiendo video... {gb_subido:.2f} / {gb_total:.2f} GB"
        )

    def _on_reintento_subida(self, mensaje: str) -> None:
        self.etiqueta_estado_subida.setText(mensaje)

    def _on_video_subido(self, video_id: str) -> None:
        if self._ruta_miniatura is not None:
            self.etiqueta_estado_subida.setText(
                f"Video subido (ID: {video_id}). Subiendo miniatura..."
            )

    def _on_subida_exitosa(self, url_video: str) -> None:
        self.boton_subir.setEnabled(True)
        self.barra_progreso.setValue(100)
        self.etiqueta_estado_subida.setText(f"Subida completada: {url_video}")
        QMessageBox.information(
            self,
            "Subida completada",
            f"El video se subió como privado.\n\nURL: {url_video}",
        )

    def _on_subida_fallida(self, mensaje: str) -> None:
        self.boton_subir.setEnabled(True)
        QMessageBox.critical(self, "Error al subir el video", mensaje)


def main() -> None:
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
