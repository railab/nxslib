# Nxslib
![master workflow](https://github.com/railab/nxslib/actions/workflows/master.yml/badge.svg)

_Nxslib_ is a Python client library to the [Apache NuttX](https://nuttx.apache.org/) 
_NxScope_ real-time logging module.

Compatible with Python 3.10+.

## Features

* built-in simulated _NxScope_ device that allows application development without 
connecting a real NuttX device
* support for the _NxScope_ serial protocol

## Features Planned
* run-time channels configuration

## Instalation

To install _Nxslib_ locally from this repository use:

`pip install --user git+https://github.com/railab/nxslib.git`

## Contributing

#### Setting up for development

1. Clone the repository.

2. Create a new venv and activate it

```
virtualenv venv
. venv/bin/activate
```

3. Install _Nxslib_ in editable mode

`pip install -e .`

and now you are ready to modify the code.

#### CI

Please run `tox` before submitting a patch to be sure your changes will pass CI.

## Used by
* [Nxscli](https://github.com/railab/nxscli/)
