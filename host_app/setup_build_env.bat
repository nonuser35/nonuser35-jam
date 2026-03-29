@echo off
setlocal

cd /d "%~dp0\.."

set "BASE_PYTHON=C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%BASE_PYTHON%" (
    echo Python base nao encontrado em:
    echo %BASE_PYTHON%
    echo.
    echo Ajuste o caminho dentro deste arquivo se necessario.
    pause
    exit /b 1
)

set "BUILD_VENV=%CD%\host_app\.buildvenv"

echo.
echo ===================================
echo  PREPARAR AMBIENTE DE BUILD
echo ===================================
echo.

if not exist "%BUILD_VENV%\Scripts\python.exe" (
    echo Criando venv limpa para o host app...
    "%BASE_PYTHON%" -m venv "%BUILD_VENV%"
    if errorlevel 1 (
        echo Falha ao criar a venv de build.
        pause
        exit /b 1
    )
)

echo Atualizando pip...
"%BUILD_VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Falha ao atualizar o pip.
    pause
    exit /b 1
)

echo Instalando dependencias do host app...
"%BUILD_VENV%\Scripts\python.exe" -m pip install -r "%CD%\host_app\requirements-build.txt"
if errorlevel 1 (
    echo Falha ao instalar as dependencias do host app.
    pause
    exit /b 1
)

echo.
echo Ambiente de build pronto.
echo Python da build:
echo %BUILD_VENV%\Scripts\python.exe
echo.
pause
