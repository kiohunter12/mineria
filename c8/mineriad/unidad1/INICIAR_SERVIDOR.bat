@echo off
title WebScraper Pro v2
echo =====================================================
echo   WebScraper Pro v2 - Iniciando servidor...
echo =====================================================

:: Liberar puerto 5000 si hay proceso zombie colgado
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    echo Liberando PID %%a del puerto 5000...
    taskkill /F /PID %%a >nul 2>&1
)

cd /d D:\c8\mineriad\unidad1
echo.
echo El servidor elegira automaticamente el puerto 5000 o 5001...
echo Abre tu navegador en la URL que aparezca abajo.
echo.
python app.py
pause
