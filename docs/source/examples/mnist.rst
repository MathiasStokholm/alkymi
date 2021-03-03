.. _mnist:

MNIST
=====

Downloading and parsing the `MNIST <http://yann.lecun.com/exdb/mnist/>`_ dataset using an alkymi pipeline. See
``examples/mnist/mnist.py`` for the full code sample.

First we define a recipe that returns the URLs of MNIST data (training and test images and labels). Note that we return
the URLs in a list, allowing us to use the ``alk.foreach`` function to process each URL by itself (see
:ref:`sequences`):

.. code-block:: python

    import alkymi as alk
    # Imports left out for brevity

    @alk.recipe()
    def urls() -> List[str]:
        # Return URLs of various parts of the dataset - alkymi will cache these as a list of strings
        train_images_url = "http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz"
        train_labels_url = "http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz"
        test_images_url = "http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz"
        test_labels_url = "http://yann.lecun.com/exdb/mnist/t10k-labels-idx1-ubyte.gz"
        return [train_images_url, train_labels_url, test_images_url, test_labels_url]


Next, we use the standard library to download the raw bytes for each URL - note that ``alk.foreach`` acts as a ``map``
call, in that each entry in the input (``urls``) has the function applied to it, thus resulting in a new list of the
same length and ordering:

.. code-block:: python

    @alk.foreach(urls)
    def download_gzips(url: str) -> bytes:
        # Download each gzip file as raw bytes - alkymi will cache these to binary files
        # This will run once per URL, and only if the URL has changed since the last evaluation
        return urllib.request.urlopen(url).read()


Finally, we use another ``alk.foreach`` decorator to create a new recipe that parses each set of downloaded bytes into
its corresponding numpy representation:

.. code-block:: python

    @alk.foreach(download_gzips)
    def parse_gzip_to_arrays(data: bytes) -> np.ndarray:
        # Unzip binary data and parse into numpy arrays - alkymi will cache the numpy arrays
        # This will run once per blob of input data, and only if the binary data has changed since the last evaluation
        with io.BytesIO(data) as f:
            with gzip.open(f) as gzip_file:
                return parse_idx(gzip_file)  # parse_idx definition left out for brevity (see examples/mnist)


The full pipeline is now defined - all that's left is to run it. Call ``.brew()`` on the final recipe to evaluate it and
all dependencies:

.. code-block:: python

    # Evaluate 'parse_gzip_to_arrays' and all dependencies
    # On subsequent evaluations, the final numpy arrays will be read from the cache and returned immediately - unless one of
    # the recipes is marked dirty (if inputs have changed, or the recipe function itself has changed) - in that case, alkymi
    # will do the minimum amount of work to bring the pipeline up-to-date, and then return the final numpy arrays
    train_images, train_labels, test_images, test_labels = parse_gzip_to_arrays.brew()

Note that alkymi is capable of caching the URLs (strings), binary data (bytes) and final images and labels (numpy
arrays) to disk (see :ref:`caching`). On subsequent evaluations, alkymi will use the cached data instead of downloading
and parsing the data again (unless something has changed, resulting in the need for re-evaluation, see
:ref:`execution`)