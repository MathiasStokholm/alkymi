import inspect
from typing import Callable, TypeVar, List

from .config import CacheType
from .foreach_recipe import ForeachRecipe
from .recipe import Recipe

R = TypeVar("R")  # The return type of the bound function


def recipe(transient: bool = False, cache: CacheType = CacheType.Auto) -> Callable[[Callable[..., R]], Recipe[R]]:
    """
    Convert a function into an alkymi Recipe to enable caching and conditional evaluation

    :param transient: Whether to always (re)evaluate the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: A callable that will yield the Recipe created from the bound function
    """
    # Capture locals of calling scope to allow lookup of dependent Recipes in decorator
    outer_locals = inspect.stack(0)[1].frame.f_locals

    def _decorator(func: Callable[..., R]) -> Recipe[R]:
        """
        Closure to capture arguments from decorator

        :param func: The bound function to wrap in a Recipe
        :return: The created Recipe
        """
        # Find all the required arguments in the stored locals
        required_args = inspect.getfullargspec(func).args
        ingredients = []  # type: List[Recipe]
        for arg_name in required_args:
            arg = outer_locals.get(arg_name, None)
            if arg is None:
                raise RuntimeError("Unable to find Recipe with name {} in enclosing scope".format(arg_name))
            if not isinstance(arg, Recipe):
                raise RuntimeError("Found argument with name {}, but not a Recipe".format(arg_name))
            ingredients.append(arg)
        return Recipe(func, ingredients, func.__name__, transient, cache)

    return _decorator


def foreach(mapped_inputs: Recipe, transient: bool = False, cache: CacheType = CacheType.Auto) -> \
        Callable[[Callable[..., R]], ForeachRecipe[R]]:
    """
    Convert a function into an alkymi Recipe to enable caching and conditional evaluation

    :param mapped_inputs: A single Recipe to whose output (a list or dictionary) the bound function will be applied to
                          generate the new outputs (similar to Python's built-in map() function)
    :param transient: Whether to always (re)evaluate the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: A callable that will yield the Recipe created from the bound function
    """
    # Capture locals of calling scope to allow lookup of dependent Recipes in decorator
    outer_locals = inspect.stack(0)[1].frame.f_locals

    def _decorator(func: Callable[..., R]) -> ForeachRecipe[R]:
        """
        Closure to capture arguments from decorator

        :param func: The bound function to wrap in a ForeachRecipe
        :return: The created ForeachRecipe
        """
        # Find all the required arguments in the stored locals - ignore the first arg since that is the mapped arg
        required_args = inspect.getfullargspec(func).args[1:]
        ingredients = []  # type: List[Recipe]
        for arg_name in required_args:
            arg = outer_locals.get(arg_name, None)
            if arg is None:
                raise RuntimeError("Unable to find Recipe with name {} in enclosing scope".format(arg_name))
            if not isinstance(arg, Recipe):
                raise RuntimeError("Found argument with name {}, but not a Recipe".format(arg_name))
            ingredients.append(arg)
        return ForeachRecipe(mapped_inputs, ingredients, func, func.__name__, transient, cache)

    return _decorator
