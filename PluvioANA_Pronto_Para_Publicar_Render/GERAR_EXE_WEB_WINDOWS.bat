@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================
echo   PluvioANA Web - Criador de executavel Windows
echo ===============================================
where py >nul 2>&1
if not errorlevel 1 (
  set "PY=py -3"
) else (
  set "PY=python"
)
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.10 ou superior.
  pause
  exit /b 1
)
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo Nao foi possivel instalar o empacotador.
  pause
  exit /b 1
)
%PY% -m PyInstaller --noconfirm --clean --onefile --name PluvioANA_Web --add-data "static;static" servidor.py
if errorlevel 1 (
  echo Falha ao gerar o executavel.
  pause
  exit /b 1
)
echo.
echo SUCESSO: executavel gerado em dist\PluvioANA_Web.exe
echo Copie este arquivo para computadores Windows sem Python.
pause
