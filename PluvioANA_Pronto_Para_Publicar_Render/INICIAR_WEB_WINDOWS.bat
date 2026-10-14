@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  echo Abrindo o PluvioANA Web...
  py -3 servidor.py
  goto :fim
)
where python >nul 2>&1
if not errorlevel 1 (
  echo Abrindo o PluvioANA Web...
  python servidor.py
  goto :fim
)
echo O Python 3.10 ou superior nao foi encontrado.
echo Instale o Python em https://www.python.org/downloads/windows/
:fim
if errorlevel 1 pause
