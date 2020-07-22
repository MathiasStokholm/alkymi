import subprocess
import logging
from pathlib import Path
import glob
from typing import List, Callable, Iterable

from alkymi.execution_graph import Recipe, RepeatedRecipe

_logger = logging.getLogger('alkymi')
_logger.setLevel(logging.DEBUG)


def recipe(ingredients: Iterable[Recipe] = (), transient: bool = False):
    def _decorator(func: Callable):
        return Recipe(ingredients, func, func.__name__, transient)

    return _decorator


def repeat_recipe(inputs: Iterable[Callable], ingredients: Iterable[Recipe] = (), transient: bool = False):
    def _decorator(func: Callable):
        return RepeatedRecipe(inputs, ingredients, func, func.__name__, transient)

    return _decorator


def call(command_line, results):
    subprocess.call(command_line)
    return results


def brew(_recipe: Recipe):
    return _recipe.brew()


def glob_files(directory: Path, pattern: str) -> Recipe:
    def _glob_recipe() -> List[Path]:
        return list(directory.glob(pattern))
    return Recipe([], _glob_recipe, 'glob_files', transient=False)
