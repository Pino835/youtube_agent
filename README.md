# YouTube Automation Suite

Herramienta que genera título, descripción, etiquetas y sugerencia de miniatura para tus videos usando Claude, y los sube directamente a YouTube. Tiene una interfaz gráfica de escritorio (recomendada) y una de terminal.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Configuración

### 1. API de Claude

1. Crea una cuenta en [console.anthropic.com](https://console.anthropic.com/) si no tienes una.
2. Genera una API key.
3. Copia `.env.example` como `.env` y pega tu clave en `ANTHROPIC_API_KEY`.

### 2. YouTube Data API v3 (OAuth)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto nuevo (o usa uno existente).
3. Ve a **APIs y servicios → Biblioteca**, busca "YouTube Data API v3" y actívala.
4. Ve a **APIs y servicios → Pantalla de consentimiento OAuth**:
   - Tipo de usuario: Externo.
   - Completa los campos obligatorios (nombre de la app, email de soporte).
   - En "Scopes", no hace falta agregar nada manualmente.
   - En "Usuarios de prueba", agrega tu propia cuenta de Gmail/YouTube.
5. Ve a **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Tipo de aplicación: **Aplicación de escritorio**.
   - Descarga el archivo JSON generado.
6. Guarda ese archivo en la raíz del proyecto como `client_secret.json` (o el nombre que prefieras, ajustando `YOUTUBE_CLIENT_SECRETS_FILE` en `.env`).

La primera vez que subas un video, se abrirá el navegador para que autorices la app con tu cuenta de YouTube. Después de eso, el token se guarda en `token.json` y no vuelve a pedir autorización mientras siga siendo válido.

## Uso — interfaz gráfica (recomendado)

Doble clic en **`ejecutar_gui.bat`**, o:

```bash
python gui.py
```

En la ventana:
1. Describe tu video y elige la categoría.
2. Clic en "Generar título, descripción y etiquetas".
3. Adjunta el archivo de video (y, si ya la tienes diseñada, la miniatura) con los botones de selección de archivo.
4. Revisa y edita título, descripción y etiquetas en los campos.
5. Clic en "Subir video a YouTube". Verás una barra de progreso real durante toda la subida.

La primera vez que subas un video se abrirá tu navegador para autorizar la app con tu cuenta de YouTube (ver sección de configuración arriba).

Los videos siempre se suben como **privados**; puedes cambiar la visibilidad después desde YouTube Studio.

## Uso — terminal

Doble clic en **`ejecutar.bat`**, o:

```bash
python main.py
```

Mismo flujo que la interfaz gráfica, pero guiado por preguntas en la terminal (solo el título es editable; descripción y etiquetas se usan tal cual las genera Claude).

## Notas

- `.env`, `client_secret.json` y `token.json` nunca deben subirse a un repositorio público — ya están en `.gitignore`.
- Todos los metadatos generados (título, descripción, etiquetas, brief de miniatura) se guardan en `salidas/` antes de intentar subir el video, así nunca se pierden si la subida falla.
- Para más detalle técnico de la arquitectura, ver [CLAUDE.md](CLAUDE.md).
