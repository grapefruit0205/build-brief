@echo off
setlocal

if /I "%~1"=="--python" goto exact_python

py -3 -c "import sys; raise SystemExit(sys.version_info.major != 3)" >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0click_windows.py" %*
  exit /b %errorlevel%
)

python -c "import sys; raise SystemExit(sys.version_info.major != 3)" >nul 2>&1
if not errorlevel 1 (
  python "%~dp0click_windows.py" %*
  exit /b %errorlevel%
)

python3 -c "import sys; raise SystemExit(sys.version_info.major != 3)" >nul 2>&1
if not errorlevel 1 (
  python3 "%~dp0click_windows.py" %*
  exit /b %errorlevel%
)

goto no_python

:exact_python
if "%~2"=="" goto no_python
if /I not "%~3"=="--encoded-runner" goto invalid_exact
if "%~4"=="" goto invalid_exact
"%~2" "%~dp0click_windows.py" --encoded-runner "%~4"
exit /b %errorlevel%

:invalid_exact
>&2 echo Click Windows runner transport was malformed.
exit /b 2

:no_python
>&2 echo Click requires Python 3. The Windows launcher tried py -3, python, and python3 but none could run Python 3.
exit /b 9009
