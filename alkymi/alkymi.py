# coding=utf-8
import subprocess
from inspect import signature
from typing import Iterable, Callable, List


class Recipe(object):
    def __init__(self, ingredients: Iterable['Recipe'], func: Callable, name: str, transient: bool):
        self._ingredients = list(ingredients)
        self._func = func
        self._name = name
        self._transient = transient
        # print('Func {} signature: {}'.format(name, signature(func)))

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    @property
    def name(self) -> str:
        return self._name

    @property
    def ingredients(self) -> List['Recipe']:
        return self._ingredients

    @property
    def transient(self) -> bool:
        return self._transient

    def __str__(self):
        return self.name


class RepeatedRecipe(Recipe):
    def __init__(self, inputs: Callable[[], Iterable[Recipe]], ingredients: Iterable[Recipe], func: Callable, name: str,
                 transient: bool):
        super().__init__(ingredients, func, name, transient)
        self._inputs = inputs

    @property
    def inputs(self):
        return self._inputs


def call(command_line, results):
    subprocess.call(command_line)
    return results
