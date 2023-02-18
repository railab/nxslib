# Nxslib
![master workflow](https://github.com/railab/nxslib/actions/workflows/master.yml/badge.svg)

_Nxslib_ is a Python client library to the [Apache NuttX](https://nuttx.apache.org/) 
_NxScope_ real-time logging module.

Compatible with Python 3.10+.

## Features

* built-in simulated _NxScope_ device that allows application development without 
connecting a real NuttX device
* support for the _NxScope_ serial protocol
* user-specific stream data decoding (user-defined types)
* support for custom protocols

## Instalation

For now, only installation from sources is available.

To install _Nxslib_ locally from this repository use:

`pip install --user git+https://github.com/railab/nxslib.git`

## Contributing

All contributions are welcome to this project. 

To get started with developing _Nxslib_, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Usage

Look at [docs/usage](docs/usage.rst).

## Tools
* [Nxscli](https://github.com/railab/nxscli/) - the command-line interface based on _Nxslib_
