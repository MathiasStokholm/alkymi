# alkymi
Pythonic task automation

![Python package](https://github.com/MathiasStokholm/alkymi/workflows/Python%20package/badge.svg?branch=master)

alkymi uses Python's basic building blocks to describe a directed-acyclic-graph (DAG) of computation, and adds a layer
of caching to only evaluate functions when inputs have changed.

The key idea behind alkymi is to have your data or validation pipeline defined in the same language as the actual
pipeline steps, allowing you to use standard Python tools (unit testing, linting, type checkers) to check the
correctness of your full pipeline. No more `make dataset`!

All alkymi tasks (recipes) are created using references to other alkymi recipes. There's no magic tying together inputs
and outputs based on file names, regexes, etc. - only function calls where alkymi provides the input arguments based on
outputs further up the DAG.

NOTE: alkymi is very much in the experimental alpha stage, and probably shouldn't be used for anything critical.
Performance optimizations are still TODO, and only single-threaded evaluation is possible at this point.

## Sample Code
Downloading and parsing the MNIST handwritten character dataset w/ caching (see `examples/mnist` for full code)
```python
import alkymi as alk

@alk.recipe()
def urls() -> List[str]:
    # Return URLs of various parts of the dataset
    train_images_url = "http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz"
    train_labels_url = "http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz"
    test_images_url = "http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz"
    test_labels_url = "http://yann.lecun.com/exdb/mnist/t10k-labels-idx1-ubyte.gz"
    return [train_images_url, train_labels_url, test_images_url, test_labels_url]


@alk.foreach(urls)
def download_gzips(url: str) -> bytes:
    # Download gzip files as raw bytes
    return urllib.request.urlopen(url).read()


@alk.foreach(download_gzips)
def parse_gzip_to_arrays(data: bytes) -> np.ndarray:
    # Unzip data and parse into numpy arrays
    with io.BytesIO(data) as f:
        with gzip.open(f) as gzip_file:
            return parse_idx(gzip_file)  # parse_idx definition left out for brevity


@alk.recipe(ingredients=[parse_gzip_to_arrays])
def prepare_data(arrays: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # Unpack from list into tuple
    train_images, train_labels, test_images, test_labels = arrays
    return train_images, train_labels, test_images, test_labels


# Evaluate 'prepare_data' and all dependencies - intermediate results will be cached automatically by alkymi
train_images, train_labels, test_images, test_labels = prepare_data.brew()
```
Or, if you need to wrap existing functions, you can simply do:
```python
import alkymi as alk

download_archives = alk.foreach(urls)(download_gzips)
parse_arrays = alk.foreach(download_archives)(parse_gzip_to_arrays)
prepared_data = alk.recipe(ingredients=[parse_arrays])(prepare_data)
train_images, train_labels, test_images, test_labels = prepared_data.brew()
```

## Documentation
TODO(mathias): Add a readthedocs.org page

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
```
pip install --user git+https://github.com/MathiasStokholm/alkymi.git
```

### Testing
After installing, you can run the test suite:
```shell script
python3 -m pytest .
```

## License
alkymi is licensed under The MIT License as found in the LICENSE.md file
