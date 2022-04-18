import inspect
from typing import Callable, TypeVar, Optional

from .config import CacheType
from .foreach_recipe import ForeachRecipe
from .recipe import Recipe

R = TypeVar("R")  # The return type of the bound function


def recipe(ingredients=(), name: Optional[str] = None, transient: bool = False, cache: CacheType = CacheType.Auto) -> \
        Callable[[Callable[..., R]], Recipe[R]]:
    """
    Convert a function into an alkymi Recipe to enable caching and conditional evaluation

    :param ingredients: The dependencies of this Recipe - the outputs of these Recipes will be provided as arguments to
                        the bound function when called in the order that they were provided. If not all arguments are
                        provided directly, alkymi will look up recipes that match the name of arguments automatically
    :param name: The name to assign to the created recipe - if not provided, the bound function's name will be used
    :param transient: Whether to always (re)evaluate the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: A callable that will yield the Recipe created from the bound function
    """
    ingredients = list(ingredients)
    num_provided_ingredients = len(ingredients)

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
        for arg_name in required_args[num_provided_ingredients:]:
            arg = outer_locals.get(arg_name, None)
            if arg is None:
                raise RuntimeError("Unable to find Recipe with name {} in enclosing scope".format(arg_name))
            if not isinstance(arg, Recipe):
                raise RuntimeError("Found argument with name {}, but not a Recipe".format(arg_name))
            ingredients.append(arg)

        recipe_name = func.__name__ if name is None else name
        return Recipe(func, ingredients, recipe_name, transient, cache)

    return _decorator


def foreach(mapped_inputs: Recipe, ingredients=(), name: Optional[str] = None, transient: bool = False,
            cache: CacheType = CacheType.Auto) -> \
        Callable[[Callable[..., R]], ForeachRecipe[R]]:
    """
    Convert a function into an alkymi Recipe to enable caching and conditional evaluation

    :param mapped_inputs: A single Recipe to whose output (a list or dictionary) the bound function will be applied to
                          generate the new outputs (similar to Python's built-in map() function)
    :param ingredients: The dependencies of this Recipe - the outputs of these Recipes will be provided as arguments to
                        the bound function when called in the order that they were provided. If not all arguments are
                        provided directly, alkymi will look up recipes that match the name of arguments automatically
    :param name: The name to assign to the created recipe - if not provided, the bound function's name will be used
    :param transient: Whether to always (re)evaluate the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: A callable that will yield the Recipe created from the bound function
    """
    ingredients = list(ingredients)
    num_provided_ingredients = len(ingredients)

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
        for arg_name in required_args[num_provided_ingredients:]:
            arg = outer_locals.get(arg_name, None)
            if arg is None:
                raise RuntimeError("Unable to find Recipe with name {} in enclosing scope".format(arg_name))
            if not isinstance(arg, Recipe):
                raise RuntimeError("Found argument with name {}, but not a Recipe".format(arg_name))
            ingredients.append(arg)

        recipe_name = func.__name__ if name is None else name
        return ForeachRecipe(mapped_inputs, ingredients, func, recipe_name, transient, cache)

    return _decorator
