from pathlib import Path
from typing import List, Tuple, Optional, Any, Dict

from .config import CacheType
from .recipe import Recipe


def glob_files(directory: Path, pattern: str, recursive: bool, cache=CacheType.Auto) -> Recipe:
    """
    Create a Recipe that will glob files in a directory and return them as a list. The created recipe will only be
    considered dirty if the file paths contained in the glob changes (not if the contents of any one file changes)

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

    return Recipe([], _glob_recipe, 'glob_files', transient=False, cache=cache, cleanliness_func=_check_clean)


def file(path: Path, cache=CacheType.Auto) -> Recipe:
    """
    Create a Recipe that outputs a single file

    :param path: The path to the file to output
    :param cache: The type of caching to use for this Recipe
    :return: The created Recipe
    """
    def _file_recipe() -> Path:
        return path

    return Recipe([], _file_recipe, 'file', transient=False, cache=cache)


class NamedArgs:
    def __init__(self, cache=CacheType.Auto, **_kwargs: Any):
        self._kwargs = _kwargs  # type: Dict[Any, Any]
        self._recipe = Recipe([], self._produce_kwargs, "kwargs", transient=False, cache=cache,
                              cleanliness_func=self._clean)

    def _produce_kwargs(self) -> Dict[Any, Any]:
        return self._kwargs

    def _clean(self, last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        if last_outputs is None:
            return self._kwargs is None
        return bool(self._kwargs == last_outputs[0])

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    def set_args(self, **_kwargs) -> None:
        self._kwargs = _kwargs


class Args:
    """
    Helper class used for the 'args' built-in recipe
    """
    def __init__(self, *_args: Any, cache=CacheType.Auto):
        self._args = _args  # type: Tuple[Any, ...]
        self._recipe = Recipe([], self._produce_args, "args", transient=False, cache=cache,
                              cleanliness_func=self._clean)

    def _produce_args(self) -> Tuple[Any, ...]:
        return self._args

    def _clean(self, last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        return self._args == last_outputs

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    def set_args(self, *_args) -> None:
        self._args = _args


def kwargs(cache=CacheType.Auto, **_kwargs: Any) -> NamedArgs:
    """
    Shorthand for creating an 'NamedArgs' instance

    :param cache: The type of caching to use for this Recipe
    :param _kwargs: The initial keyword arguments to use
    :return: The created 'NamedArgs' instance
    """
    return NamedArgs(cache, **_kwargs)


def args(*_args: Any, cache=CacheType.Auto) -> Args:
    """
    Shorthand for creating an 'Args' instance

    :param _args: The initial arguments to use
    :param cache: The type of caching to use for this Recipe
    :return: The created 'Args' instance
    """
    return Args(*_args, cache=cache)
