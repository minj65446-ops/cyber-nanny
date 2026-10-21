@echo off
rem Start the Cyber Nanny desktop pet with no console window.
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "nanny_pet.py"
  exit /b
)

where py >nul 2>nul
if %errorlevel%==0 (
  start "" py -w "nanny_pet.py"
  exit /b
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if exist "%%D\pythonw.exe" (
    start "" "%%D\pythonw.exe" "nanny_pet.py"
    exit /b
  )
)

echo Python 3.9+ was not found.
echo Install Python from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
pause
