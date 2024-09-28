echo Setting up virtual environment ...
python -m venv venv

echo "Install requirements ..."
.\venv\bin\pip install -r requirements.txt

echo "Update submodule ..."
git submodule update --init --recursive

echo "Compile proto files"
cd seekers-api
bash compile.bat
cp -r api ../seekers
