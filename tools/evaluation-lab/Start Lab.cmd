@echo off
setlocal
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(sys.version_info[:2] < (3,12))" >nul 2>nul
  if not errorlevel 1 goto usepy
)
where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; sys.exit(sys.version_info[:2] < (3,12))" >nul 2>nul
  if not errorlevel 1 goto usepython
)
echo Python 3.12 or later is required. Install from the official website and reopen:
echo https://www.python.org/downloads/windows/
pause
exit /b 2
:usepy
py -3 "%~dp0start-lab.py" %*
goto finished
:usepython
python "%~dp0start-lab.py" %*
:finished
set LAB_STATUS=%ERRORLEVEL%
if not "%LAB_STATUS%"=="0" pause
endlocal & exit /b %LAB_STATUS%
