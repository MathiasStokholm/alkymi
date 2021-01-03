import array
import functools
import gzip
import io
import logging
import operator
import struct
import urllib.request
from typing import List, BinaryIO

import matplotlib.pyplot as plt
import numpy as np

import alkymi as alk

# Print alkymi logging to stderr
alk.log.addHandler(logging.StreamHandler())
alk.log.setLevel(logging.DEBUG)


def parse_idx(fd: BinaryIO) -> np.ndarray:
    """
    Parse an IDX data file
    See: https://github.com/datapythonista/mnist/blob/208174c19a36d6325ea4140ff0182ec591273b67/mnist/__init__.py#L64
    """
    DATA_TYPES = {0x08: 'B',  # unsigned byte
                  0x09: 'b',  # signed byte
                  0x0b: 'h',  # short (2 bytes)
                  0x0c: 'i',  # int (4 bytes)
                  0x0d: 'f',  # float (4 bytes)
                  0x0e: 'd'}  # double (8 bytes)

    header = fd.read(4)
    if len(header) != 4:
        raise RuntimeError('Invalid IDX file, '
                           'file empty or does not contain a full header.')

    zeros, data_type, num_dimensions = struct.unpack('>HBB', header)

    if zeros != 0:
        raise RuntimeError('Invalid IDX file, '
                           'file must start with two zero bytes. '
                           'Found 0x%02x' % zeros)

    try:
        data_type = DATA_TYPES[data_type]
    except KeyError:
        raise RuntimeError('Unknown data type '
                           '0x%02x in IDX file' % data_type)

    dimension_sizes = struct.unpack('>' + 'I' * num_dimensions,
                                    fd.read(4 * num_dimensions))

    data = array.array(data_type, fd.read())
    data.byteswap()  # looks like array.array reads data as little endian

    expected_items = functools.reduce(operator.mul, dimension_sizes)
    if len(data) != expected_items:
        raise RuntimeError('IDX file has wrong number of items. '
                           'Expected: %d. Found: %d' % (expected_items,
                                                        len(data)))

    return np.array(data).reshape(dimension_sizes)


@alk.recipe()
def urls() -> List[str]:
    train_images_url = "http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz"
    train_labels_url = "http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz"
    test_images_url = "http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz"
    test_labels_url = "http://yann.lecun.com/exdb/mnist/t10k-labels-idx1-ubyte.gz"
    return [train_images_url, train_labels_url, test_images_url, test_labels_url]


@alk.foreach(urls)
def download_gzips(url: str) -> bytes:
    return urllib.request.urlopen(url).read()


@alk.foreach(download_gzips)
def parse_gzip_to_arrays(data: bytes) -> np.ndarray:
    with io.BytesIO(data) as f:
        with gzip.open(f) as gzip_file:
            return parse_idx(gzip_file)  # type: ignore


def main():
    train_images, train_labels, test_images, test_labels = parse_gzip_to_arrays.brew()
    plt.imshow(train_images[0], cmap="gray")
    plt.title("Digit: {}".format(train_labels[0]))
    plt.show()


if __name__ == "__main__":
    main()
