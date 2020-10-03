# coding=utf-8

from pathlib import Path
from typing import Any, Optional, Iterable
import os.path


def get_metadata(item: Any):
    def _handle_path(path: Path) -> Optional[float]:
        # Return None if output doesn't exist
        if not path.exists():
            return None

        # For directories, we care about creation timestamp
        if path.is_dir():
            return os.path.getctime(str(path))

        # For files, we care about modification timestamp
        return os.path.getmtime(str(path))

    if item is None:
        return None

    if isinstance(item, Path):
        return _handle_path(item)

    # FIXME(mathias): Find a better way to collapse metadata from multiple items into a single metadata point
    # This is used if a function returns a list of paths or similar
    if isinstance(item, Iterable):
        return max(get_metadata(subitem) for subitem in item)

    raise NotImplementedError('Metadata not supported for type: {}'.format(item))
