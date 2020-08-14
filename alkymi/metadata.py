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

    if isinstance(item, Path):
        return _handle_path(item)

    if isinstance(item, Iterable):
        return sum(get_metadata(subitem) for subitem in item)

    raise NotImplementedError(f'Metadata not supported for type: {item}')
