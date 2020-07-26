# coding=utf-8
import subprocess
from inspect import signature
from pathlib import Path
from typing import Iterable, Callable, List, Optional


class Recipe(object):
    def __init__(self, ingredients: Iterable['Recipe'], func: Callable, name: str, transient: bool,
                 cleanliness_func: Callable[[Optional[List[Path]]], bool] = None):
        self._ingredients = list(ingredients)
        self._func = func
        self._name = name
        self._transient = transient
        self._cleanliness_func = cleanliness_func
        # print('Func {} signature: {}'.format(name, signature(func)))

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def is_clean(self, last_outputs: Optional[List[Path]]) -> bool:
        # Assume that function is pure by default
        if self._cleanliness_func is None:
            return True

        # Non-pure function may have been changed by external circumstances, use custom check
        return self._cleanliness_func(last_outputs)

    @property
    def name(self) -> str:
        return self._name

    @property
    def ingredients(self) -> List['Recipe']:
        return self._ingredients

    @property
    def transient(self) -> bool:
        return self._transient

    @property
    def function_hash(self) -> int:
        return hash(self._func)

    def __str__(self):
        return self.name


class RepeatedRecipe(Recipe):
    def __init__(self, inputs: Recipe, ingredients: Iterable[Recipe], func: Callable, name: str,
                 transient: bool):
        super().__init__(ingredients, func, name, transient)
        self._inputs = inputs

    @property
    def inputs(self) -> Recipe:
        return self._inputs


def call(command_line, results):
    subprocess.call(command_line)
    return results
