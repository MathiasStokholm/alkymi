from typing import Iterable, Callable

from .config import CacheType
from .foreach_recipe import ForeachRecipe
from .recipe import Recipe


def recipe(ingredients: Iterable[Recipe] = (), transient: bool = False, cache: CacheType = CacheType.Auto) -> \
        Callable[[Callable], Recipe]:
    def _decorator(func: Callable) -> Recipe:
        return Recipe(ingredients, func, func.__name__, transient, cache)

    return _decorator


def foreach(mapped_inputs: Recipe, ingredients: Iterable[Recipe] = (), transient: bool = False,
            cache: CacheType = CacheType.Auto) -> \
        Callable[[Callable], ForeachRecipe]:
    def _decorator(func: Callable) -> ForeachRecipe:
        return ForeachRecipe(mapped_inputs, ingredients, func, func.__name__, transient, cache)

    return _decorator
