# coding=utf-8

from pathlib import Path
from typing import List, Tuple

from .recipe import Recipe


def glob_files(directory: Path, pattern: str) -> Recipe:
    def _glob_recipe() -> Tuple[List[Path]]:
        return list(directory.glob(pattern)),

    def _check_clean(last_outputs: Tuple[List[Path]]) -> bool:
        # If rerunning glob produces the same list of files, then the recipe is clean
        return _glob_recipe() == last_outputs

    return Recipe([], _glob_recipe, 'glob_files', transient=False, cleanliness_func=_check_clean)


def file(path: Path) -> Recipe:
    def _file_recipe() -> Path:
        return path

    return Recipe([], _file_recipe, 'file', transient=False)


class NamedArgs:
    def __init__(self, **_kwargs):
        self._kwargs = _kwargs
        self._recipe = Recipe([], self._produce_args, "kwargs", transient=False, cleanliness_func=self._clean)

    def _produce_args(self):
        return self._kwargs

    def _clean(self, last_outputs: Tuple[List[Path]]):
        return self._kwargs == last_outputs[0]

    @property
    def recipe(self):
        return self._recipe

    def set_args(self, **_kwargs):
        self._kwargs = _kwargs


class Args:
    def __init__(self, *_args):
        self._args = _args
        self._recipe = Recipe([], self._produce_args, "args", transient=False, cleanliness_func=self._clean)

    def _produce_args(self):
        return self._args

    def _clean(self, last_outputs: Tuple[List[Path]]):
        return self._args == last_outputs

    @property
    def recipe(self):
        return self._recipe

    def set_args(self, *_args):
        self._args = _args


def kwargs(**_kwargs) -> NamedArgs:
    return NamedArgs(**_kwargs)


def args(*_args) -> Args:
    return Args(*_args)
