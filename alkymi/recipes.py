from pathlib import Path
from typing import List, Tuple, Any, Dict, Iterable, Union, TypeVar, Type, Optional

from .config import CacheType
from .recipe import Recipe


def glob_files(name: str, directory: Path, pattern: str, recursive: bool, cache=CacheType.Auto) -> Recipe[List[Path]]:
    """
    Create a Recipe that will glob files in a directory and return them as a list. The created recipe will only be
    considered dirty if the file paths contained in the glob changes (not if the contents of any one file changes)

    :param name: The name to give the created Recipe
    :param directory: The directory in which to perform the glob
    :param pattern: The pattern to use for the glob, e.g. `*.py`
    :param recursive: Whether to glob recursively into subdirectories
    :param cache: The type of caching to use for this Recipe
    :return: The created Recipe
    """

    def _glob_recipe() -> List[Path]:
        """
        The bound function that performs the glob

        :return: The glob of files
        """
        if recursive:
            return list(directory.rglob(pattern))
        else:
            return list(directory.glob(pattern))

    def _check_clean(last_outputs: List[Path]) -> bool:
        """
        If rerunning glob produces the same list of files, then the recipe is clean

        :param last_outputs: The last set of outputs created by this Recipe
        :return: True if clean
        """
        if last_outputs is None:
            return False
        return _glob_recipe() == last_outputs

    return Recipe(_glob_recipe, [], name, transient=False, cache=cache, cleanliness_func=_check_clean)


def file(name: str, path: Path, cache=CacheType.Auto) -> Recipe[Path]:
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

    return Recipe(_file_recipe, [], name, transient=False, cache=cache)


def zip_results(name: str, recipes: Iterable[Recipe], cache=CacheType.Auto) \
        -> Recipe[Union[List[Tuple[Any, ...]], Dict[Any, Tuple[Any, ...]]]]:
    """
    Create a Recipe that zips the outputs from a number of recipes into elements, similar to Python's built-in zip().
    Notably, dictionaries are handled a bit differently, in that a dictionary is returned with keys mapping to tuples
    from the different inputs, i.e.::

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

    return Recipe(_zip_results, recipes, name, transient=False, cache=cache)


T = TypeVar('T')


class Arg(Recipe[T]):
    """
    Class providing a stateful argument

    To use, create an Arg instance with the initial value for your argument, e.g. ``Arg(0)``, then provide as a
    recipe to downstream recipes. To change the input arguments, call ``set()`` again - this will mark the recipe as
    dirty and cause reevaluation of downstream recipe(s)
    """

    def __init__(self, arg: T, name: str, cache=CacheType.Auto):
        """
        Create a new Arg instance with initial argument value

        :param arg: The initial argument value
        :param name: The name to give the created Recipe
        :param cache: The type of caching to use for this Recipe
        """
        self._arg = arg
        self._type = type(arg)
        self._subtype = next((type(val) for val in arg), None) if isinstance(arg, Iterable) else None
        super().__init__(self._produce_arg, [], name, transient=False, cache=cache, cleanliness_func=self._clean)

    @property
    def type(self) -> Type[T]:
        """
        :return: The type of the argument
        """
        return self._type

    @property
    def subtype(self) -> Optional[Any]:
        """
        :return: The subtype of the argument (e.g. the type of items contained in a list). Will be None for non-iterable
                 types
        """
        return self._subtype

    def _produce_arg(self) -> T:
        """
        :return: The current argument
        """
        return self._arg

    def _clean(self, last_outputs: Any) -> bool:
        """
        Checks whether the argument has changed since the last evaluation

        :param last_outputs: The last set of outputs (argument)
        :return: True if the argument remain the same
        """
        return self._arg == last_outputs

    def set(self, _arg: T) -> None:
        """
        Change the argument, causing the recipe to need reevaluation

        :param _arg: The new argument
        """
        if not isinstance(_arg, self._type):
            raise TypeError("Type of argument ({}) not {}".format(type(_arg), self._type))
        self._arg = _arg


def arg(_arg: T, name: str, cache=CacheType.Auto) -> Arg[T]:
    """
    Shorthand for creating an ``Arg`` instance

    :param _arg: The initial argument to use
    :param name: The name to give the created Recipe
    :param cache: The type of caching to use for this Recipe
    :return: The created ``Arg`` instance
    """
    return Arg(_arg, name=name, cache=cache)
