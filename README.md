# Nxslib
![master workflow](https://github.com/railab/nxslib/actions/workflows/master.yml/badge.svg)

Nxslib is a Python client library for the [Apache NuttX](https://nuttx.apache.org/)
NxScope real-time logging module.

Compatible with Python 3.10+.

## Features

* built-in simulated NxScope device that allows application development without 
connecting a real NuttX device
* support for the NxScope serial protocol
* user-specific stream data decoding (user-defined types)
* support for custom protocols

## Instalation

Nxslib can be installed by running `pip install nxslib`.

To install latest development version, use:

`pip install git+https://github.com/railab/nxslib.git`

## Contributing

All contributions are welcome to this project.

To get started with developing Nxslib, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Usage

Look at [docs/usage](docs/usage.rst).

## Tools
* [Nxscli](https://github.com/railab/nxscli/) - a command-line interface based on Nxslib
