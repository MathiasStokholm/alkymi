from pathlib import Path
from typing import List, Tuple, Optional, Any

from .config import CacheType
from .recipe import Recipe


def glob_files(directory: Path, pattern: str, cache=CacheType.Auto) -> Recipe:
    def _glob_recipe() -> Tuple[List[Path]]:
        return list(directory.glob(pattern)),

    def _check_clean(last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        # This is actually of type Optional[Tuple[List[Path]]] (same as _glob_recipe)
        # If rerunning glob produces the same list of files, then the recipe is clean
        return _glob_recipe() == last_outputs

    return Recipe([], _glob_recipe, 'glob_files', transient=False, cache=cache, cleanliness_func=_check_clean)


def file(path: Path, cache=CacheType.Auto) -> Recipe:
    def _file_recipe() -> Path:
        return path

    return Recipe([], _file_recipe, 'file', transient=False, cache=cache)


class NamedArgs:
    def __init__(self, cache=CacheType.Auto, **_kwargs):
        self._kwargs = _kwargs
        self._recipe = Recipe([], self._produce_kwargs, "kwargs", transient=False, cache=cache,
                              cleanliness_func=self._clean)

    def _produce_kwargs(self):
        return self._kwargs

    def _clean(self, last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        if last_outputs is None:
            return self._kwargs is None
        return self._kwargs == last_outputs[0]

    @property
    def recipe(self):
        return self._recipe

    def set_args(self, **_kwargs):
        self._kwargs = _kwargs


class Args:
    def __init__(self, *_args, cache=CacheType.Auto):
        self._args = _args
        self._recipe = Recipe([], self._produce_args, "args", transient=False, cache=cache,
                              cleanliness_func=self._clean)

    def _produce_args(self):
        return self._args

    def _clean(self, last_outputs: Optional[Tuple[Any, ...]]) -> bool:
        return self._args == last_outputs

    @property
    def recipe(self) -> Recipe:
        return self._recipe

    def set_args(self, *_args) -> None:
        self._args = _args


def kwargs(cache=CacheType.Auto, **_kwargs) -> NamedArgs:
    return NamedArgs(cache, **_kwargs)


def args(*_args, cache=CacheType.Auto) -> Args:
    return Args(*_args, cache=cache)
