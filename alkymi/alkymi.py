import functools
import subprocess
import logging
from pathlib import Path
import glob
from typing import List, Callable, Iterable

from alkymi.execution_graph import Recipe, RepeatedRecipe

_logger = logging.getLogger('alkymi')
_logger.setLevel(logging.DEBUG)


def recipe(ingredients=()):
    def _decorator(func):
        return Recipe(ingredients, func, func.__name__)

    return _decorator


def repeat_recipe(inputs: Iterable[Callable], ingredients: Iterable[Recipe] = ()):
    def _decorator(func):
        return RepeatedRecipe(inputs, ingredients, func, func.__name__)

    return _decorator


def call(command_line, results):
    subprocess.call(command_line)
    return results


def brew(_recipe: Recipe):
    return _recipe.brew()


def glob_files(directory: Path, pattern: str) -> Callable[[], List[Path]]:
    def _glob_recipe() -> List[Path]:
        matched_files = glob.glob(str(directory / pattern))
        return [Path(f) for f in matched_files]

    return Recipe([], _glob_recipe, 'glob_files')
