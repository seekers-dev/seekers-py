# seekers
* An artificial intelligence programming challenge targeted at students.
* AIs compete by controlling bouncy little circles ("seekers") trying to collect the most goals.
* Based on Python 3 and pygame.

![Screenshot_20221213_193620](https://user-images.githubusercontent.com/37810842/207417325-30e82c8b-b53b-44e7-9d41-ca431dc579e2.png)

## This repository contains
1. Python implementation of the Seekers game
2. Seekers gRPC server
3. Seekers gRPC client

* Players can join the Seekers game in two ways:
  1. <a name="join-method-new"></a>as gRPC clients (new and safe way)
  2. <a name="join-method-old"></a>as a local file whose `decide`-function is called directly from within the game (old and unsafe way)
     * This is discouraged as it allows players to access the game's internals and cheat. See [this issue](https://github.com/seekers-dev/seekers/issues/1).
     * useful for debugging/AI-developement

## How to run
Install python3 and the packages in [`requirements.txt`](requirements.txt).

### Run a Python Seekers game (and a gRPC server)
This will:
* start a Seekers game
* run a gRPC server by default
* join the specified AIs (see [old join method](#join-method-old))
```bash
$ python3 run_seekers.py <AI files>
```

### Run a Python AI as a Seekers gRPC client
You will need a separate server running. This can be the server above, or, for example, [the Java implementation](https://github.com/seekers-dev/seekers-api).

```bash
$ python3 run_clients.py <AI files>
```

## License
You can, and are invited to, use, redistribute and modify seekers under the terms
of the GNU General Public License (GPL), version 3 or (at your option) any
later version published by the Free Software Foundation.
