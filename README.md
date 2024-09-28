<div align=center>
    <h1 align=center>Seekers Py</h1>
    <!-- Badges -->
    <div>
        <img src="https://github.com/seekers-dev/seekers-py/actions/workflows/python-app.yml/badge.svg" alt="Python Version 3.9/3.10">
        <img src="https://github.com/seekers-dev/seekers-py/actions/workflows/github-code-scanning/codeql/badge.svg" alt="CodeQL">
        <img src="https://github.com/seekers-dev/seekers/actions/workflows/python-app.yml/badge.svg" alt="pre-release">
    </div>
    <i>Learn to code with games.</i>
</div>

<table>
    <tr>
    <td width="40%">
    <img alt="Game Preview" src=https://user-images.githubusercontent.com/37810842/226148194-e5b55d57-ed84-4e71-869b-d062b101b345.png>
    </td>
    <td>
    <ul>
        <li>Artificial intelligence programming challenge, hopefully suited for school students.</li>
        <li>AIs compete by controlling bouncy little circles ("seekers") trying to collect the most goals.</li>
        <li>Based on Python 3 and pygame.</li>
    </ul>
    </td>
    </tr>
</table>

## Getting started

### Setup

You can install seekers by downloading prebuild wrapped binaries from Sourceforge or GitHub
or by building it on your own.
The prebuilt wrapped binaries do not require python but are only available for windows and linux.
If you are looking for darwin/macOS, you still need to build it on your own.

[![Download seekers-py](https://a.fsdn.com/con/app/sf-download-button)](https://sourceforge.net/projects/seekers-py/files/latest/download)

For building it on your own:
1. Clone this repository or download the latest release: `git clone https://github.com/seekers-dev/seekers-py.git`
2. Run the setup script: `bash setup.py` (linux) or `.\setup.bat` (win32)

### Run seekers

If you want to run the seekers game with the AI files, you should run the following command: 

```shell
python seekers.py <AI files>
```

This script has the following options on the command line:

```log
options:
  -h, --help            show this help message and exit
  --no-grpc             Don't host a gRPC server.
  --no-kill             Don't kill the process after the game is over.
  --debug               Enable debug mode. This will enable debug drawing.
  --address ADDRESS, -a ADDRESS
                        Address of the server. (default: localhost:7777)
  --config CONFIG, -c CONFIG
                        Path to the config file. (default: config.ini)
  --config-override CONFIG_OVERRIDE, --override CONFIG_OVERRIDE, -o CONFIG_OVERRIDE
                        Override a config option. Use the form option=value,
                        e.g. global.seed=43.
  --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL},
  --log {DEBUG,INFO,WARNING,ERROR,CRITICAL},
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}
```

### Run a client

> [!NOTE]
> You will need a separate server running. This can be the server above, or, for example, [the Java implementation](https://github.com/seekers-dev/seekers-api).

```shell
python client.py <AI file>
```

This script has the following options on the command line:

```
options:
  -h, --help            show this help message and exit
  --address ADDRESS, -a ADDRESS
                        Address of the Seekers game. (default: localhost:7777)
  --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL},
  --log {DEBUG,INFO,WARNING,ERROR,CRITICAL},
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}
  --careful             Enable careful mode for the gRPC clients. This will
                        raise an exception and stop the client when errors
                        occur that otherwise would be ignored.
```


## License

You can, and are invited to, use, redistribute and modify seekers under the terms
of the GNU General Public License (GPL), version 3 or (at your option) any
later version published by the Free Software Foundation.
