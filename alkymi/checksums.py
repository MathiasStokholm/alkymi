from pathlib import Path
from typing import Any, Optional, Sequence, Dict, Callable
import pickle
import hashlib
import inspect

# Load additional metadata generators based on available libs
additional_metadata_generators = {}  # type: Dict[Any, Callable]
try:
    import numpy as np  # NOQA


    def _handle_ndarray(array: np.ndarray) -> str:
        """
        Computes a checksum for the provided numpy array

        :param array: The numpy array to compute a checksum for
        :return: The computed checksum as a string
        """
        return hashlib.md5(array.data).hexdigest()


    additional_metadata_generators[np.ndarray] = _handle_ndarray
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
        return hashlib.md5(pd.util.hash_pandas_object(df).values).hexdigest()


    additional_metadata_generators[pd.DataFrame] = _handle_dataframe
except ImportError:
    pass


class Checksummer(object):
    """
    Class used to compute a stable hash/checksum of an object recursively. Currently uses MD5.
    """

    def __init__(self):
        self._md5 = hashlib.md5()

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
        self._md5.update(str(type(obj)).encode("utf-8"))

        if isinstance(obj, str):
            self._md5.update(obj.encode("utf-8"))
        elif isinstance(obj, bytes):
            self._md5.update(obj)
        elif isinstance(obj, (int, float)):
            self.update(str(obj))
        elif isinstance(obj, Sequence):
            for e in obj:
                self.update(e)
        elif isinstance(obj, Dict):
            keys = obj.keys()
            for k in sorted(keys):
                self.update(k)
                self.update(obj[k])
        elif isinstance(obj, Path):
            self._update_path(obj)
        elif inspect.iscode(obj):
            self.update(obj.co_code)
        elif inspect.isroutine(obj):
            self._update_func(obj)
        else:
            # Check if any additional metadata generator will work
            generator = additional_metadata_generators.get(type(obj))
            if generator is not None:
                self.update(generator(obj))
            else:
                # As a last resort, try to pickle the object to get bytes for hashing
                try:
                    pickled_bytes = pickle.dumps(obj)
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
        # Ignore non-existent path
        if not path.exists():
            return

        # For directories, we just care about the path itself
        if path.is_dir():
            self.update(str(path))
            return

        # For files, we care about the file contents too
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(128 * self._md5.block_size), b''):
                self.update(chunk)

    def digest(self) -> str:
        """
        :return: The checksum as a string
        """
        return self._md5.hexdigest()


def function_hash(fn: Callable) -> str:
    """
    Computes the hash/checksum of a function

    :param fn: The function to hash
    :return: The checksum as a string
    """
    hasher = Checksummer()
    hasher.update(fn)
    return hasher.digest()


def get_metadata(obj: Any) -> Optional[str]:
    """
    Computes the hash/checksum of the provided input

    :param obj: The object to compute a hash/checksum for
    :return: The checksum as a string
    """
    if obj is None:
        return None

    hasher = Checksummer()
    hasher.update(obj)
    return hasher.digest()
