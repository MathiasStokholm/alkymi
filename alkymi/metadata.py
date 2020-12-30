from pathlib import Path
from typing import Any, Optional, Sequence, Dict, Callable
import hashlib
import inspect

# Load additional metadata generators based on available libs
additional_metadata_generators = {}  # type: Dict[Any, Callable]
try:
    import numpy as np  # NOQA


    def _handle_ndarray(array: np.ndarray) -> str:
        return hashlib.md5(array.data).hexdigest()


    additional_metadata_generators[np.ndarray] = _handle_ndarray
except ImportError:
    pass

try:
    import pandas as pd  # NOQA


    def _handle_dataframe(df: pd.DataFrame) -> str:
        return hashlib.md5(pd.util.hash_pandas_object(df).values).hexdigest()


    additional_metadata_generators[pd.DataFrame] = _handle_dataframe
except ImportError:
    pass


class Hasher(object):
    def __init__(self):
        self._md5 = hashlib.md5()

    def update(self, value):
        if value is None:
            return

        self._md5.update(str(type(value)).encode("utf-8"))
        if isinstance(value, str):
            self._md5.update(value.encode("utf-8"))
        elif isinstance(value, bytes):
            self._md5.update(value)
        elif isinstance(value, (int, float)):
            self.update(str(value))
        elif isinstance(value, Sequence):
            for e in value:
                self.update(e)
        elif isinstance(value, Dict):
            keys = value.keys()
            for k in sorted(keys):
                self.update(k)
                self.update(value[k])
        elif isinstance(value, Path):
            self.update_path(value)
        elif inspect.iscode(value):
            self.update(value.co_code)
        elif inspect.isroutine(value):
            self.update_func(value)
        else:
            # Check if any additional metadata generator will work
            generator = additional_metadata_generators.get(type(value), None)
            if generator is not None:
                self.update(generator(value))
            else:
                raise ValueError("Hash not supported for type: {}".format(type(value)))

    def update_func(self, fn) -> None:
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

    def update_path(self, path: Path) -> None:
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
        return str(self._md5.hexdigest())


def function_hash(fn: Callable) -> str:
    hasher = Hasher()
    hasher.update(fn)
    return hasher.digest()


def get_metadata(item: Any) -> Optional[str]:
    if item is None:
        return None

    hasher = Hasher()
    hasher.update(item)
    return hasher.digest()
