from pathlib import Path
from typing import Any, Sequence, Dict, Callable
import pickle
import alkymi.config

# Try to use xxh3 from xxhash to speed up hashing significantly, otherwise fallback to built-in MD5
try:
    import xxhash

    HASHER = xxhash.xxh3_64
except ImportError:
    import hashlib

    HASHER = hashlib.md5

import inspect

# Load additional checksum generators based on available libs
from alkymi import AlkymiConfig

additional_checksum_generators: Dict[Any, Callable] = {}
try:
    import numpy as np  # NOQA


    def _handle_ndarray(array: np.ndarray) -> str:
        """
        Computes a checksum for the provided numpy array

        :param array: The numpy array to compute a checksum for
        :return: The computed checksum as a string
        """
        return HASHER(array.data).hexdigest()


    additional_checksum_generators[np.ndarray] = _handle_ndarray
except ImportError:
    pass

try:
    import pandas as pd  # NOQA


    def _handle_dataframe(df: pd.DataFrame) -> str:
        """
        Computes a checksum for the provided pandas DataFrame

        :param df: The pandas DataFrame to compute a checksum for
        :return: The computed checksum as a string
        """
        return HASHER(pd.util.hash_pandas_object(df).values).hexdigest()


    additional_checksum_generators[pd.DataFrame] = _handle_dataframe
except ImportError:
    pass


class Checksummer(object):
    """
    Class used to compute a stable hash/checksum of an object recursively. Currently uses MD5.
    """

    def __init__(self):
        self._hasher = HASHER()

    def update(self, obj: Any) -> None:
        """
        Update the current checksum with new information from the provided value. May call itself recursively if needed
        to hash complex inputs.

        :param obj: The object to update the checksum with
        """
        if obj is None:
            return

        # The type of the input object needs to be taken into consideration to avoid different types with the same value
        # resulting in the same checksum
        self._hasher.update(str(type(obj)).encode("utf-8"))

        if isinstance(obj, str):
            self._hasher.update(obj.encode("utf-8"))
        elif isinstance(obj, bytes):
            self._hasher.update(obj)
        elif isinstance(obj, (int, float)):
            self.update(str(obj))
        elif isinstance(obj, Sequence):
            for e in obj:
                self.update(e)
        elif isinstance(obj, Dict):
            keys = obj.keys()
            for k in keys:
                self.update(k)
                self.update(obj[k])
        elif isinstance(obj, Path):
            self._update_path(obj)
        elif inspect.iscode(obj):
            self.update(obj.co_code)
        elif inspect.isroutine(obj):
            self._update_func(obj)
        else:
            # Check if any additional checksum generator will work
            generator = additional_checksum_generators.get(type(obj))
            if generator is not None:
                self.update(generator(obj))
            else:
                # As a last resort, try to pickle the object to get bytes for hashing
                if not AlkymiConfig.get().allow_pickling:
                    raise RuntimeError("Pickling disabled - cannot checksum item: {}".format(type(obj)))

                try:
                    pickled_bytes = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
                    self.update(pickled_bytes)
                except pickle.PicklingError:
                    raise ValueError("Checksum not supported for type: {}".format(type(obj)))

    def _update_func(self, fn) -> None:
        """
        Update the current checksum with a function

        :param fn: The function to update the checksum with
        """
        code = fn.__code__

        # Hash the bytecode
        self.update(code.co_code)

        # Hash default arguments
        defaults = fn.__defaults__
        if defaults is not None:
            default_values = dict(zip(code.co_varnames[-len(defaults):], defaults))
            self.update(default_values)

        # Hash constants that are referenced by the bytecode but ignore names of lambdas
        if code.co_consts:
            for const in code.co_consts:
                if not isinstance(const, str) or not const.endswith(".<lambda>"):
                    self.update(const)

        # Handle referenced functions
        if code.co_freevars:
            assert len(code.co_freevars) == len(fn.__closure__)
            referenced_func_names_and_closures = list(
                zip(code.co_freevars, (c.cell_contents for c in fn.__closure__)))
            self.update(referenced_func_names_and_closures)

    def _update_path(self, path: Path) -> None:
        """
        Update the current checksum with a Path

        :param path: The Path to update the checksum with
        """
        # For non-existent paths, we just care about the path itself
        if not path.exists():
            self.update(str(path))
            return

        # For directories, we care about the path and whether it exists
        if path.is_dir():
            self.update(str(path))
            self.update(path.exists())
            return

        # For files, we care about file name ...
        self.update(str(path))

        # ... and either the file hash
        file_checksum_method = alkymi.config.AlkymiConfig.get().file_checksum_method
        if file_checksum_method == alkymi.config.FileChecksumMethod.HashContents:
            with path.open('rb') as f:
                size = 1024 * self._hasher.block_size
                b = f.read(size)
                while len(b) > 0:
                    self._hasher.update(b)
                    b = f.read(size)

        # ... or the file modification timestamp
        elif file_checksum_method == alkymi.config.FileChecksumMethod.ModificationTimestamp:
            last_modification_timestamp = path.stat().st_mtime_ns
            self.update(last_modification_timestamp)

    def digest(self) -> str:
        """
        :return: The checksum as a string
        """
        return self._hasher.hexdigest()


def function_hash(fn: Callable) -> str:
    """
    Computes the hash/checksum of a function

    :param fn: The function to hash
    :return: The checksum as a string
    """
    hasher = Checksummer()
    hasher.update(fn)
    return hasher.digest()


def checksum(obj: Any) -> str:
    """
    Computes the hash/checksum of the provided input

    :param obj: The object to compute a hash/checksum for
    :return: The checksum as a string
    """
    # Fake the hash of None as just "None"
    if obj is None:
        return "None"

    hasher = Checksummer()
    hasher.update(obj)
    return hasher.digest()
