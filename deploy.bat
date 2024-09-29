@echo off

echo Creating python archives ...
powershell Compress-Archive ".\*" "seekers-win32.zip"
powershell Compress-Archive ".\seekers\api\*" "seekers-win32-stubs.zip"

echo Install additional build requirements ...
.\venv\Scripts\pip install -r requirements.txt cx_Freeze

echo Building binaries ...
.\venv\Scripts\python setup.py build

echo Compress artifacts ...
for /d %%a in (build\*) do (powershell Compress-Archive ".\%%a\*" "seekers-win32-bin.zip")
echo Finished!
