setlocal EnableDelayedExpansion

rem Initialize git submodules
git submodule update --init --recursive

rem Remove the 'stubs' directory if it exists, and create a new one
if exist stubs (
    rd /s /q stubs
)
mkdir stubs

rem Base directory to start the search
set baseDir=proto\src\main\proto

rem Find all .proto files in the specified directory and subdirectories
set "protoFiles="
for /r %baseDir% %%f in (*.proto) do (
    rem Get the relative path from the base directory
    set "relativePath=%%f"
    set "relativePath=!relativePath:%CD%\=!"
    set "protoFiles=!protoFiles! !relativePath!"
)

rem Run the grpc_tools.protoc command
python -m grpc_tools.protoc ^
   --python_out=stubs ^
   --grpc_python_out=stubs ^
   --proto_path=%baseDir% ^
   --mypy_out=stubs ^
   --experimental_allow_proto3_optional ^
   !protoFiles!

rem Invoke protol to fix broken imports
protol ^
  --create-package ^
  --in-place ^
  --python-out stubs ^
  protoc --proto-path=%baseDir% !protoFiles! --experimental_allow_proto3_optional

endlocal
