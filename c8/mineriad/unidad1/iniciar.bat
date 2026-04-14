@echo off
title WebScraper Pro - Iniciando...
echo.
echo  =============================================
echo   WebScraper Pro - Instalando dependencias
echo  =============================================
echo.

pip install -r requirements.txt

echo.
echo  =============================================
echo   Abre tu navegador en: http://127.0.0.1:5000
echo  =============================================
echo.

python app.py
pause
