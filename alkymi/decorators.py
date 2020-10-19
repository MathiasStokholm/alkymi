from typing import Iterable, Callable

from .foreach_recipe import ForeachRecipe
from .recipe import Recipe


def recipe(ingredients: Iterable[Recipe] = (), transient: bool = False) -> Callable[[Callable], Recipe]:
    def _decorator(func: Callable) -> Recipe:
        return Recipe(ingredients, func, func.__name__, transient)

    return _decorator


def map_recipe(mapped_inputs: Recipe, ingredients: Iterable[Recipe] = (), transient: bool = False) -> \
        Callable[[Callable], ForeachRecipe]:
    def _decorator(func: Callable) -> ForeachRecipe:
        return ForeachRecipe(mapped_inputs, ingredients, func, func.__name__, transient)

    return _decorator
