<h1 align=center>Seekers</h1>

<p align=center>
  <a href="https://github.com/seekers-dev/seekers/actions/workflows/python-app.yml">
    <img src="https://github.com/seekers-dev/seekers-py/actions/workflows/python-app.yml/badge.svg" alt="Python Version 3.9/3.10">
  </a>
  <a href="https://github.com/seekers-dev/seekers-py/actions/workflows/github-code-scanning/codeql">
    <img src="https://github.com/seekers-dev/seekers-py/actions/workflows/github-code-scanning/codeql/badge.svg" alt="CodeQL">
  </a>
  <a href="https://github.com/seekers-dev/seekers-py/actions/workflows/pre-release.yml">
    <img src="https://github.com/seekers-dev/seekers/actions/workflows/python-app.yml/badge.svg" alt="pre-release">
  </a>
</p>

* An artificial intelligence programming challenge targeted at students.
* AIs compete by controlling bouncy little circles ("seekers") trying to collect the most goals.
* Based on Python 3.9 and pygame.

![image](https://user-images.githubusercontent.com/37810842/226148194-e5b55d57-ed84-4e71-869b-d062b101b345.png)

## This repository contains

- 🎮 A classic Python implementation of the Seekers game
- 🌐 A server and client implementation of the [Seekers gRPC API](https://github.com/seekers-dev/seekers-grpc)

Players can join the Seekers Game in two ways:
1. as gRPC clients (new and safe way)
2. as a local file whose `decide`-function is called directly from within the game (old and unsafe way)
   * This is discouraged as it allows players to access the game's internals and cheat. See [this issue](https://github.com/seekers-dev/seekers/issues/1).
   * useful for debugging/AI-developement

## Getting started

### Installation

* Python 3.9 or higher is required (make sure it's in your PATH)
1. Download the latest release and unpack it.
2. Install the packages in [`requirements.txt`](requirements.txt). 
   - We recommend using a [virtual environment](https://docs.python.org/3/library/venv.html) (venv). Whenever opening a new terminal, you will have to activate the virtual environment again.
   - To create: `python -m venv venv`
   - To activate: `source venv/bin/activate` (Linux) or `venv\Scripts\activate` (Windows)

```shell
python -m pip install -r requirements.txt
```

alternatively:

```shell
pip install -r requirements.txt
```

Depending on how you installed python, you might have to use `py` or `python3` instead of `python`.

3. Done!

### Create server and run clients

This will:
* start a Seekers Game
* run a gRPC server by default

```shell
python run_seekers.py <AI files>
```


### Run one single client

⚠ You will need a separate server running. This can be the server above, or, for example, [the Java implementation](https://github.com/seekers-dev/seekers-api).

```shell
python run_client.py <AI file>
```

## Development
### Generating gRPC stubs 
After cloning, you need to compile the gRPC stubs manually.

```shell
cd seekers/grpc
pip install -r requirements-dev.txt
./compile_protos.sh
```

## License

You can, and are invited to, use, redistribute and modify seekers under the terms
of the GNU General Public License (GPL), version 3 or (at your option) any
later version published by the Free Software Foundation.
