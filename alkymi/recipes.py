# coding=utf-8

from pathlib import Path
from typing import List

from .alkymi import Recipe


def glob_files(directory: Path, pattern: str) -> Recipe:
    def _glob_recipe() -> List[Path]:
        return list(directory.glob(pattern))

    def _check_clean(last_outputs: List[Path]) -> bool:
        # If rerunning glob produces the same list of files, then the recipe is clean
        return _glob_recipe() == last_outputs

    return Recipe([], _glob_recipe, 'glob_files', transient=False, cleanliness_func=_check_clean)
