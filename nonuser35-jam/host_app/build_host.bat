@echo off
setlocal

cd /d "%~dp0\.."

set "FINAL_DIR=%CD%\host_app\final"
set "WORK_DIR=%CD%\host_app\build_temp"
set "APP_DIR_NAME=NONUSER35 JAM Host"
set "APP_EXE_NAME=NONUSER35 JAM.exe"
set "PYTHON_EXE="

if exist "%CD%\host_app\.buildvenv\Scripts\python.exe" set "PYTHON_EXE=%CD%\host_app\.buildvenv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe" set "PYTHON_EXE=C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE where python >nul 2>&1
if not defined PYTHON_EXE if not errorlevel 1 set "PYTHON_EXE=python"
if not defined PYTHON_EXE if exist "%CD%\venv311\Scripts\python.exe" set "PYTHON_EXE=%CD%\venv311\Scripts\python.exe"
if not defined PYTHON_EXE (
    echo Nenhum Python encontrado para o build.
    pause
    exit /b 1
)

echo.
echo ===================================
echo  BUILD NONUSER35 JAM HOST APP
echo ===================================
echo.
echo Usando Python: %PYTHON_EXE%
echo.
if exist "%CD%\host_app\.buildvenv\Scripts\python.exe" (
    echo Ambiente de build dedicado detectado.
    echo.
)

echo Verificando dependencias do host...
"%PYTHON_EXE%" -c "import flask, flask_cors, spotipy, googleapiclient, ytmusicapi, requests, bs4, PIL" >nul 2>&1
if errorlevel 1 (
    echo O Python escolhido nao tem todas as dependencias do projeto.
    echo Rode primeiro host_app\setup_build_env.bat para criar a venv limpa de build.
    pause
    exit /b 1
)

echo Verificando PyInstaller...
"%PYTHON_EXE%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller nao encontrado. Instalando...
    "%PYTHON_EXE%" -m pip install pyinstaller
    if errorlevel 1 (
        echo Falha ao instalar PyInstaller.
        pause
        exit /b 1
    )
)

"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --distpath "%FINAL_DIR%" --workpath "%WORK_DIR%" "host_app\nonuser35_host.spec"

if errorlevel 1 (
    echo Falha ao gerar o app.
    pause
    exit /b 1
)

set "DIST_DIR=%FINAL_DIR%\%APP_DIR_NAME%"

if exist "%DIST_DIR%" (
    if not exist "%DIST_DIR%\docs" mkdir "%DIST_DIR%\docs"
    if not exist "%DIST_DIR%\data" mkdir "%DIST_DIR%\data"
    if not exist "%DIST_DIR%\logs" mkdir "%DIST_DIR%\logs"

    > "%DIST_DIR%\Abrir NONUSER35 JAM.bat" echo @echo off
    >> "%DIST_DIR%\Abrir NONUSER35 JAM.bat" echo cd /d "%%~dp0"
    >> "%DIST_DIR%\Abrir NONUSER35 JAM.bat" echo start "" "%APP_EXE_NAME%"

    > "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo @echo off
    >> "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo setlocal
    >> "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo set "TARGET=%%~dp0%APP_EXE_NAME%"
    >> "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo set "ICON=%%~dp0_internal\host_app\app_icon.ico"
    >> "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo set "SHORTCUT=%%USERPROFILE%%\Desktop\NONUSER35 JAM.lnk"
    >> "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut($env:SHORTCUT); $s.TargetPath = $env:TARGET; $s.WorkingDirectory = '%%~dp0'; if (Test-Path $env:ICON) { $s.IconLocation = $env:ICON } else { $s.IconLocation = '$env:TARGET,0' }; $s.Save()"
    >> "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo echo Atalho criado em %%SHORTCUT%%
    >> "%DIST_DIR%\Criar atalho na area de trabalho.bat" echo pause

    > "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo NONUSER35 JAM HOST
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo.
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo 1. Abra "%APP_EXE_NAME%" ou "Abrir NONUSER35 JAM.bat".
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo 2. A janela do host mostra o estado da jam e das requests da API.
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo 3. O navegador abre em http://localhost:5000.
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo 4. Use "Criar atalho na area de trabalho.bat" se quiser um atalho final no desktop.
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo 5. A pasta "data" guarda configuracao, cache e perfis.
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo 6. A pasta "logs" guarda os logs do host.
    >> "%DIST_DIR%\LEIA-ME PRIMEIRO.txt" echo 7. A pasta "docs" traz guias curtos de uso e suporte.

    > "%DIST_DIR%\README FIRST.txt" echo NONUSER35 JAM HOST
    >> "%DIST_DIR%\README FIRST.txt" echo.
    >> "%DIST_DIR%\README FIRST.txt" echo 1. Open "%APP_EXE_NAME%" or "Abrir NONUSER35 JAM.bat".
    >> "%DIST_DIR%\README FIRST.txt" echo 2. The host window shows jam status and API request activity.
    >> "%DIST_DIR%\README FIRST.txt" echo 3. Your browser opens at http://localhost:5000.
    >> "%DIST_DIR%\README FIRST.txt" echo 4. Use "Criar atalho na area de trabalho.bat" if you want a desktop shortcut.
    >> "%DIST_DIR%\README FIRST.txt" echo 5. The "data" folder stores config, cache, and profiles.
    >> "%DIST_DIR%\README FIRST.txt" echo 6. The "logs" folder stores host logs.
    >> "%DIST_DIR%\README FIRST.txt" echo 7. The "docs" folder contains quick usage and troubleshooting notes.

    > "%DIST_DIR%\docs\QUICKSTART.txt" echo QUICKSTART
    >> "%DIST_DIR%\docs\QUICKSTART.txt" echo.
    >> "%DIST_DIR%\docs\QUICKSTART.txt" echo - Abra o app.
    >> "%DIST_DIR%\docs\QUICKSTART.txt" echo - Conecte Spotify e YouTube.
    >> "%DIST_DIR%\docs\QUICKSTART.txt" echo - Espere o navegador abrir a jam.
    >> "%DIST_DIR%\docs\QUICKSTART.txt" echo - Gere o link publico se quiser convidados externos.

    > "%DIST_DIR%\docs\APIS NECESSARIAS.txt" echo APIS NECESSARIAS
    >> "%DIST_DIR%\docs\APIS NECESSARIAS.txt" echo.
    >> "%DIST_DIR%\docs\APIS NECESSARIAS.txt" echo - Spotify Developer Dashboard
    >> "%DIST_DIR%\docs\APIS NECESSARIAS.txt" echo - YouTube Data API v3
    >> "%DIST_DIR%\docs\APIS NECESSARIAS.txt" echo - Cloudflare Tunnel opcional para link publico

    > "%DIST_DIR%\docs\TROUBLESHOOTING.txt" echo TROUBLESHOOTING
    >> "%DIST_DIR%\docs\TROUBLESHOOTING.txt" echo.
    >> "%DIST_DIR%\docs\TROUBLESHOOTING.txt" echo - Se a musica nao entrar, confira Spotify e YouTube.
    >> "%DIST_DIR%\docs\TROUBLESHOOTING.txt" echo - Se o link publico falhar, reinicie o tunnel.
    >> "%DIST_DIR%\docs\TROUBLESHOOTING.txt" echo - Logs do host ficam na pasta logs.
)

if exist "%WORK_DIR%" (
    rmdir /s /q "%WORK_DIR%"
)

echo.
echo Build finalizado.
echo Saida esperada: host_app\final\%APP_DIR_NAME%\
echo Nao mova o exe sozinho. Envie a pasta inteira pronta para uso.
echo.
pause
