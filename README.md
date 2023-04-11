# alkymi ⚗️

[![build](https://github.com/MathiasStokholm/alkymi/workflows/build/badge.svg?branch=master)](https://github.com/MathiasStokholm/alkymi/actions?query=workflow%3Abuild)
[![docs](https://readthedocs.org/projects/alkymi/badge/?version=latest)](https://alkymi.readthedocs.io/en/latest/?badge=latest)
[![coverage](https://codecov.io/gh/MathiasStokholm/alkymi/branch/develop/graph/badge.svg?token=L0DTW805NL)](https://codecov.io/gh/MathiasStokholm/alkymi)
[![pypi](https://img.shields.io/pypi/v/alkymi.svg)](https://pypi.org/project/alkymi)
[![versions](https://img.shields.io/pypi/pyversions/alkymi.svg)](https://pypi.org/project/alkymi)

Alkymi is a pure Python (3.7+) library for describing and executing tasks and pipelines with built-in caching and
conditional evaluation based on checksums.

Alkymi is easy to install, simple to use, and has very few dependencies outside of Python's standard library. The code
is cross-platform, and allows you to write your pipelines once and deploy to multiple operating systems (tested on
Linux, Windows and Mac).

Documentation, including a quickstart guide, is provided [here](https://alkymi.readthedocs.io/en/latest/).

## Features
* Easily define complex data pipelines as decorated Python functions
  * This allows you to run linting, type checking, etc. on your data pipelines
* Return values are automatically cached to disk, regardless of type
* Efficiently checks if pipeline is up-to-date
  * Checks if external files have changed, bound functions have changed or if pipeline dependencies have changed
* No domain specific language (DSL) or CLI tool, just regular Python
  * Supports caching and conditional evaluation in Jupyter Notebooks
* Cross-platform - works on Linux, Windows and Mac
* Expose recipes as a command-line interface (CLI) using alkymi's
[Lab](https://alkymi.readthedocs.io/en/latest/examples/command_line.html) type

## Sample Usage
For examples of how to use alkymi, see the
[quickstart guide](https://alkymi.readthedocs.io/en/latest/getting_started/quick_start.html).

Example code:
```python
import numpy as np
import alkymi as alk

@alk.recipe()
def long_running_task() -> np.ndarray:
    # Perform expensive computation here ...
    hard_to_compute_result = np.array([42])
    # Return value will be automatically cached to disk
    return hard_to_compute_result

result = long_running_task.brew()  # == np.ndarray([42])
```

Or one of the examples, e.g. [MNIST](https://alkymi.readthedocs.io/en/latest/examples/mnist.html).

## Installation
Install via pip:
```shell script
pip install --user alkymi
```

Or see the [Installation page](https://alkymi.readthedocs.io/en/latest/getting_started/installation.html).

### Testing
After installing, you can run the test suite (use the `lint`, `coverage` and `type_check` recipes to perform those
actions):
```shell script
python3 labfile.py brew test
```

## License
alkymi is licensed under The MIT License as found in the LICENSE.md file

## Upcoming Features
The following features are being considered for future implementation:
* Type annotations propagated from bound functions to recipes
* Support for call/type checking all recipes (e.g. by adding a `check` command to `Lab`)
* Cache maintenance functionality

## Known Issues
* alkymi currently doesn't check custom objects for altered external files when computing cleanliness (e.g. `MyClass`
has a `self._some_path` that points to a file somewhere outside alkymi's internal cache)
* `alk.foreach()` currently only supports enumerable inputs of type `List` or `Dict`
* Recipes marked `transient` will always be dirty, and thus always require reevaluation. This functionality should be
replaced by a proper means of creating recipes that don't cache outputs, but only run when needed to provide inputs for
downstream recipes
