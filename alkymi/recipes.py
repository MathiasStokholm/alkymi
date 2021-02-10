from pathlib import Path
from typing import List, Tuple, Optional, Any, Dict, Iterable, Union

from .config import CacheType
from .recipe import Recipe


def glob_files(name: str, directory: Path, pattern: str, recursive: bool, cache=CacheType.Auto) -> Recipe:
    """
    Create a Recipe that will glob files in a directory and return them as a list. The created recipe will only be
    considered dirty if the file paths contained in the glob changes (not if the contents of any one file changes)

    :param name: The name to give the created Recipe
    :param directory: The directory in which to perform the glob
    :param pattern: The pattern to use for the glob, e.g. '*.py'
    :param recursive: Whether to glob recursively into subdirectories
    :param cache: The type of caching to use for this Recipe
    :return: The created Recipe
    """

    def _glob_recipe() -> Tuple[List[Path]]:
        """
        The bound function that performs the glob

        :return: The glob of files
        """
        if recursive:
            return list(directory.rglob(pattern)),
        else:
            return list(directory.glob(pattern)),

    def _check_clean(last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        """
        If rerunning glob produces the same list of files, then the recipe is clean

        :param last_outputs: The last set of outputs created by this Recipe
        :return: True if clean
        """
        return _glob_recipe() == last_outputs

    return Recipe([], _glob_recipe, name, transient=False, cache=cache, cleanliness_func=_check_clean)


def file(name: str, path: Path, cache=CacheType.Auto) -> Recipe:
    """
    Create a Recipe that outputs a single file

    :param name: The name to give the created Recipe
    :param path: The path to the file to output
    :param cache: The type of caching to use for this Recipe
    :return: The created Recipe
    """
    # Reference the path as a string to avoid changes to the Path object to change the checksum of the function
    path_as_str = str(path)

    def _file_recipe() -> Path:
        return Path(path_as_str)

    return Recipe([], _file_recipe, name, transient=False, cache=cache)


def zip_results(name: str, recipes: Iterable[Recipe], cache=CacheType.Auto) -> Recipe:
    """
    Create a Recipe that zips the outputs from a number of recipes into elements, similar to Python's built-in zip().
    Notably, dictionaries are handled a bit differently, in that a dictionary is returned with keys mapping to tuples
    from the different inputs, i.e.:
        {"1": 1} zip {"1", "one"} -> {"1", (1, "one")}

    :param name: The name to give the created Recipe
    :param recipes: The recipes to zip. These must return lists or dictionaries
    :param cache: The type of caching to use for this Recipe
    :return: The created Recipe
    """

    def _zip_results(*iterables: Union[List, Dict]) \
            -> Union[List[Tuple[Any, ...]], Dict[Any, Tuple[Any, ...]]]:
        # Sanity checks
        if not iterables or len(iterables) == 0:
            return []

        if any(not isinstance(iterable, Iterable) for iterable in iterables):
            raise ValueError("Cannot zip non-iterable inputs")

        first_iterable = iterables[0]
        if any(not isinstance(iterable, type(first_iterable)) for iterable in iterables):
            raise ValueError("Cannot zip inputs of different types")

        num_items = len(first_iterable)
        if any(len(iterable) != num_items for iterable in iterables):
            raise ValueError("Cannot zip inputs of different length")

        # Handle the actual zipping operation
        if isinstance(first_iterable, list):
            return list(zip(*iterables))
        elif isinstance(first_iterable, dict):
            return {
                key: tuple(iterable[key] for iterable in iterables)
                for key in first_iterable.keys()
            }
        else:
            raise ValueError("Type: {} not supported in _zip_results()".format(type(first_iterable)))

    return Recipe(recipes, _zip_results, name, transient=False, cache=cache)


class NamedArgs:
    """
    Class providing stateful keyword argument(s)

    To use, create a NamedArgsArgs instance with the initial value for your arguments, e.g. Args(val0=0, val1=1,
    val2=2), then provide the 'recipe' property to downstream recipes. To change the input arguments, call 'set_args()'
    again - this will mark the contained recipe as dirty and cause reevaluation of downstream recipes
    """

    def __init__(self, name: str, cache=CacheType.Auto, **_kwargs: Any):
        """
        Create a new NamedArgs instance with initial argument value(s)

        :param name: The name to give the created Recipe
        :param cache: The type of caching to use for this Recipe
        :param _kwargs: The initial keyword argument value(s)
        """
        self._kwargs = _kwargs  # type: Dict[Any, Any]
        self._recipe = Recipe([], self._produce_kwargs, name, transient=False, cache=cache,
                              cleanliness_func=self._clean)

    def _produce_kwargs(self) -> Dict[Any, Any]:
        """
        :return: The current set of keyword arguments
        """
        return self._kwargs

    def _clean(self, last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        """
        Checks whether the arguments have changed since the last evaluation

        :param last_outputs: The last set of outputs (arguments)
        :return: True if the arguments remain the same
        """
        if last_outputs is None:
            return self._kwargs is None
        return bool(self._kwargs == last_outputs[0])

    @property
    def recipe(self) -> Recipe:
        """
        :return: The recipe that produces the keyword arguments
        """
        return self._recipe

    def set_args(self, **_kwargs) -> None:
        """
        Change the arguments, causing the recipe to need reevaluation

        :param _kwargs: The new set of keyword arguments
        """
        # TODO(mathias): Consider enforcing argument count and types here
        self._kwargs = _kwargs


class Args:
    """
    Class providing stateful non-keyword argument(s)

    To use, create an Args instance with the initial value for your arguments, e.g. Args(0, 1, 2), then provide the
    'recipe' property to downstream recipes. To change the input arguments, call 'set_args()' again - this will mark the
    contained recipe as dirty and cause reevaluation of downstream recipes
    """

    def __init__(self, *_args: Any, name: str, cache=CacheType.Auto):
        """
        Create a new Args instance with initial argument value(s)

        :param _args: The initial argument value(s)
        :param name: The name to give the created Recipe
        :param cache: The type of caching to use for this Recipe
        """
        self._args = _args  # type: Tuple[Any, ...]
        self._recipe = Recipe([], self._produce_args, name, transient=False, cache=cache,
                              cleanliness_func=self._clean)

    def _produce_args(self) -> Tuple[Any, ...]:
        """
        :return: The current set of arguments
        """
        return self._args

    def _clean(self, last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        """
        Checks whether the arguments have changed since the last evaluation

        :param last_outputs: The last set of outputs (arguments)
        :return: True if the arguments remain the same
        """
        return self._args == last_outputs

    @property
    def recipe(self) -> Recipe:
        """
        :return: The recipe that produces the arguments
        """
        return self._recipe

    def set_args(self, *_args) -> None:
        """
        Change the arguments, causing the recipe to need reevaluation

        :param _args: The new set of arguments
        """
        # TODO(mathias): Consider enforcing argument count and types here
        self._args = _args


def kwargs(name: str, cache=CacheType.Auto, **_kwargs: Any) -> NamedArgs:
    """
    Shorthand for creating an 'NamedArgs' instance

    :param name: The name to give the created Recipe
    :param cache: The type of caching to use for this Recipe
    :param _kwargs: The initial keyword arguments to use
    :return: The created 'NamedArgs' instance
    """
    return NamedArgs(name, cache, **_kwargs)


def args(*_args: Any, name: str, cache=CacheType.Auto) -> Args:
    """
    Shorthand for creating an 'Args' instance

    :param _args: The initial arguments to use
    :param name: The name to give the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: The created 'Args' instance
    """
    return Args(*_args, name=name, cache=cache)
