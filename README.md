# alkymi ⚗️
Pythonic task automation

![build](https://github.com/MathiasStokholm/alkymi/workflows/build/badge.svg?branch=master)

alkymi uses Python's basic building blocks to describe a directed-acyclic-graph (DAG) of computation, and adds a layer
of caching to only evaluate functions when inputs have changed.

The key idea behind alkymi is to have your data or validation pipeline defined in the same language as the actual
pipeline steps, allowing you to use standard Python tools (unit testing, linting, type checkers) to check the
correctness of your full pipeline. No more `make dataset`!

All alkymi tasks (recipes) are created using references to other alkymi recipes. There's no magic tying together inputs
and outputs based on file names, regexes, etc. - only function calls where alkymi provides the input arguments based on
outputs further up the DAG.

*NOTE: alkymi is still in the experimental alpha stage, and probably shouldn't be used for anything critical. You should
count on most APIs changing with future development*

## Sample Code
Downloading and parsing the MNIST handwritten character dataset w/ caching (see `examples/mnist` for full code)
```python
import alkymi as alk

@alk.recipe()
def urls() -> List[str]:
    # Return URLs of various parts of the dataset - alkymi will cache these as a list of strings
    train_images_url = "http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz"
    train_labels_url = "http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz"
    test_images_url = "http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz"
    test_labels_url = "http://yann.lecun.com/exdb/mnist/t10k-labels-idx1-ubyte.gz"
    return [train_images_url, train_labels_url, test_images_url, test_labels_url]


@alk.foreach(urls)
def download_gzips(url: str) -> bytes:
    # Download each gzip file as raw bytes - alkymi will cache these to binary files
    # This will run once per URL, and only if the URL has changed since the last evaluation
    return urllib.request.urlopen(url).read()


@alk.foreach(download_gzips)
def parse_gzip_to_arrays(data: bytes) -> np.ndarray:
    # Unzip binary data and parse into numpy arrays - alkymi will cache the numpy arrays
    # This will run once per blob of input data, and only if the binary data has changed since the last evaluation
    with io.BytesIO(data) as f:
        with gzip.open(f) as gzip_file:
            return parse_idx(gzip_file)  # parse_idx definition left out for brevity (see examples/mnist)


# Evaluate 'parse_gzip_to_arrays' and all dependencies
# On subsequent evaluations, the final numpy arrays will be read from the cache and returned immediately - unless one of
# the recipes is marked dirty (if inputs have changed, or the recipe function itself has changed) - in that case, alkymi
# will do the minimum amount of work to bring the pipeline up-to-date, and then return the final numpy arrays 
train_images, train_labels, test_images, test_labels = parse_gzip_to_arrays.brew()
```
Or, if you need to wrap existing functions, you can simply do:
```python
import alkymi as alk

download_archives = alk.foreach(urls)(download_gzips)
parse_arrays = alk.foreach(download_archives)(parse_gzip_to_arrays)
train_images, train_labels, test_images, test_labels = parse_arrays.brew()
```

## Command Line Usage
In some scenarios, you may need to automate multiple tasks, and writing a Python script script for each might be a bit
tedious - a common example of this is a Makefile that has rules for "style" (style checking), "install" (fetch
dependencies), etc. In this case, you can use alkymi's `Lab` functionality:
```python
from pathlib import Path
import alkymi as alk
import pytest

# 'glob_files()' is a built-in recipe generator that globs and returns a list of files
glob_test_files = alk.recipes.glob_files(Path("tests"), "test_*.py", recursive=True)

@alk.recipe(ingredients=[glob_test_files])
def test(test_files: List[Path]) -> None:
    # Convert Path objects to str
    result = pytest.main(args=[str(file) for file in test_files])
    if result != pytest.ExitCode.OK:
        raise Exception("Unit tests failed: {}".format(result))

lab = alk.Lab("my_lab")
lab.add_recipes(test)
lab.open()
```
The above code will cause the script to present the user with a command-line interface (CLI) with the following options:
* `status`: Prints detailed status of all recipes contained in the lab (cached, needs reevaluation etc.)
* `brew`: Runs one or more recipes with the provided names (in the above, running `python labfile.py brew test` would 
          run the unit tests)

alkymi uses a labfile (`labfile.py` in the root of the repo) to automate tasks such as linting using flake8, static type
checking using mypy, running unit tests using pytest, as well as creating and uploading distributions to PyPI.

## Documentation
Upcoming: readthedocs.org page

## Upcoming Features
The following features are being considered for future implementation:
* Lazy loading of outputs from cache (loading checksums should be sufficient for checking status of recipes - outputs
can then be loaded as needed for actual evaluation)
* Arguments to recipes when calling `brew` in `Lab` CLI
* Type annotations propagated from bound functions to recipes
* Support for call/type checking all recipes (e.g. by adding a `check` command to `Lab`)
* Code coverage for tests

## Known Issues
* alkymi currently doesn't check nested structures for altered external files when computing cleanliness (e.g. `MyClass`
has a `self._some_path` that points to a file somewhere outside of alkymi's internal cache)
* Recipes created with `alk.foreach()` only save their state after fully evaluating all inputs - ideally we'd want to
save the state after every item, to avoid having to redo work if the program exits with an exception
* `alk.foreach()` currently only supports enumerable inputs of type `List` or `Dict`
* Recipes marked `transient` will always be dirty, and thus always require reevaluation. This functionality should be
replaced by a proper means of creating recipes that don't cache outputs, but only run when needed to provide inputs for
downstream recipes

## Installation
Install via pip:
```shell script
pip install --user alkymi
```

Or clone and install directly from source
```shell script
git clone https://github.com/MathiasStokholm/alkymi.git
cd alkymi
pip install --user .
```

Or install using pip and github
```shell script
pip install --user git+https://github.com/MathiasStokholm/alkymi.git
```

### Testing
After installing, you can run the test suite (use the `lint` and `type_check` recipes to perform those actions):
```shell script
python3 labfile.py brew test
```

## License
alkymi is licensed under The MIT License as found in the LICENSE.md file
