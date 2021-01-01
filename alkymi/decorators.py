from typing import Iterable, Callable

from .config import CacheType
from .foreach_recipe import ForeachRecipe
from .recipe import Recipe


def recipe(ingredients: Iterable[Recipe] = (), transient: bool = False, cache: CacheType = CacheType.Auto) -> \
        Callable[[Callable], Recipe]:
    """
    Convert a function into an alkymi Recipe to enable caching and conditional evaluation

    :param ingredients: The dependencies of this Recipe - the outputs of these Recipes will be provided as arguments to
                        the bound function when called
    :param transient: Whether to always (re)evaluate the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: A callable that will yield the Recipe created from the bound function
    """

    def _decorator(func: Callable) -> Recipe:
        """
        Closure to capture arguments from decorator

        :param func: The bound function to wrap in a Recipe
        :return: The created Recipe
        """
        return Recipe(ingredients, func, func.__name__, transient, cache)

    return _decorator


def foreach(mapped_inputs: Recipe, ingredients: Iterable[Recipe] = (), transient: bool = False,
            cache: CacheType = CacheType.Auto) -> \
        Callable[[Callable], ForeachRecipe]:
    """
    Convert a function into an alkymi Recipe to enable caching and conditional evaluation

    :param mapped_inputs: A single Recipe to whose output (a list or dictionary) the bound function will be applied to
                          generate the new outputs (similar to Python's built-in map() function)
    :param ingredients: The dependencies of this Recipe - the outputs of these Recipes will be provided as arguments to
                        the bound function when called (following the item from the mapped_inputs sequence)
    :param transient: Whether to always (re)evaluate the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: A callable that will yield the Recipe created from the bound function
    """

    def _decorator(func: Callable) -> ForeachRecipe:
        """
        Closure to capture arguments from decorator

        :param func: The bound function to wrap in a ForeachRecipe
        :return: The created ForeachRecipe
        """
        return ForeachRecipe(mapped_inputs, ingredients, func, func.__name__, transient, cache)

    return _decorator
