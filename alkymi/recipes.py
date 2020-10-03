# coding=utf-8

from pathlib import Path
from typing import List, Tuple

from .recipe import Recipe


def glob_files(directory: Path, pattern: str) -> Recipe:
    def _glob_recipe() -> Tuple[List[Path]]:
        return list(directory.glob(pattern)),

    def _check_clean(last_outputs: Tuple[List[Path]]) -> bool:
        # If rerunning glob produces the same list of files, then the recipe is clean
        return _glob_recipe() == last_outputs

    return Recipe([], _glob_recipe, 'glob_files', transient=False, cleanliness_func=_check_clean)


def file(path: Path) -> Recipe:
    def _file_recipe() -> Path:
        return path

    return Recipe([], _file_recipe, 'file', transient=False)
