# coding=utf-8

from pathlib import Path
from typing import List

from .alkymi import Recipe


def glob_files(directory: Path, pattern: str) -> Recipe:
    def _glob_recipe() -> List[Path]:
        return list(directory.glob(pattern))

    return Recipe([], _glob_recipe, 'glob_files', transient=False)
