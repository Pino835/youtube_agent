@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv
    echo Ejecuta primero: py -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo No se encontro el archivo .env
    echo Copia .env.example como .env y completa tu ANTHROPIC_API_KEY
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py

pause
