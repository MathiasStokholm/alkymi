# coding=utf-8
from pathlib import Path
from typing import Any, Optional, Sequence, Dict
import hashlib
import os.path

# Load additional metadata generators based on available libs
additional_metadata_generators = {}
try:
    import numpy as np


    def _handle_ndarray(array: np.ndarray) -> str:
        return hashlib.md5(array.data).hexdigest()


    additional_metadata_generators[np.ndarray] = _handle_ndarray
except ImportError:
    pass


def _handle_path(path: Path) -> Optional[str]:
    # Return None if output doesn't exist
    if not path.exists():
        return None

    # For directories, we just care about the path itself
    if path.is_dir():
        return "{}".format(path)

    # For files, we care about modification timestamp
    return "{}#{}".format(str(path), os.path.getmtime(str(path)))


class Hasher(object):
    def __init__(self):
        self.md5 = hashlib.md5()

    def update(self, value):
        if value is None:
            return

        self.md5.update(str(type(value)).encode("utf-8"))
        if isinstance(value, str):
            self.md5.update(value.encode("utf-8"))
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
            # TODO(mathias): Replace with md5 sum (will break tests that rely on modification timestamps)
            self.update(_handle_path(value))
        else:
            # Check if any additional metadata generator will work
            generator = additional_metadata_generators.get(type(value), None)
            if generator is not None:
                self.update(generator(value))
            else:
                raise ValueError("Hash not supported for type: {}".format(type(value)))

    def digest(self) -> str:
        return self.md5.hexdigest()


def get_metadata(item: Any) -> Optional[str]:
    if item is None:
        return None

    hasher = Hasher()
    hasher.update(item)
    return hasher.digest()
