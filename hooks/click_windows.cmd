@echo off
setlocal

"%ComSpec%" /d /c py -3 -c "import sys; raise SystemExit(sys.version_info.major != 3)" >nul 2>&1
if not errorlevel 1 goto run_py

"%ComSpec%" /d /c python -c "import sys; raise SystemExit(sys.version_info.major != 3)" >nul 2>&1
if not errorlevel 1 goto run_python

"%ComSpec%" /d /c python3 -c "import sys; raise SystemExit(sys.version_info.major != 3)" >nul 2>&1
if not errorlevel 1 goto run_python3

goto no_python

:run_py
py -3 "%~dp0click_windows.py" %*
exit /b %errorlevel%

:run_python
python "%~dp0click_windows.py" %*
exit /b %errorlevel%

:run_python3
python3 "%~dp0click_windows.py" %*
exit /b %errorlevel%

:no_python
>&2 echo Click requires Python 3. The Windows launcher tried py -3, python, and python3 but none could run Python 3.
exit /b 9009
