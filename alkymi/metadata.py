# coding=utf-8

from pathlib import Path
from typing import Any, Optional, Iterable, Union
from hashlib import md5
import os.path


def _handle_str(item: str) -> str:
    return md5(item.encode('utf-8')).hexdigest()


def _handle_number(item: Union[int, float]) -> Union[int, float]:
    return item


def _handle_path(path: Path) -> Optional[float]:
    # Return None if output doesn't exist
    if not path.exists():
        return None

    # For directories, we care about creation timestamp
    if path.is_dir():
        return os.path.getctime(str(path))

    # For files, we care about modification timestamp
    return os.path.getmtime(str(path))


def get_metadata(item: Any):
    if item is None:
        return None

    if isinstance(item, Path):
        return _handle_path(item)

    if isinstance(item, str):
        return _handle_str(item)

    if isinstance(item, int) or isinstance(item, float):
        return _handle_number(item)

    if isinstance(item, Iterable):
        # FIXME(mathias): Find a better way to collapse metadata from multiple items into a single metadata point
        # This is used if a function returns a list of paths or similar
        if all(isinstance(subitem, Path) for subitem in item):
            return max(get_metadata(subitem) for subitem in item)

        if all(subitem is None for subitem in item):
            return None

    raise NotImplementedError('Metadata not supported for type: {}'.format(item))
