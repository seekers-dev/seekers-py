echo Setting up virtual environment ...
python -m venv venv

echo "Install requirements ..."
.\venv\Scripts\pip install -r requirements.txt

echo "Update submodule ..."
git submodule update --init --recursive --remote

echo "Compile proto files"
cd seekers-api
.\compile.bat
cp -r api ../seekers
