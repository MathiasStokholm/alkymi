# coding=utf-8
import os
import subprocess
from inspect import signature
from pathlib import Path
from typing import Iterable, Callable, List, Optional, Any

from .metadata import get_metadata


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

    def is_clean(self, last_inputs: Optional[List[Path]], input_metadata, new_inputs: Optional[List[Path]],
                 last_outputs: Optional[List[Path]]) -> bool:
        # Assume that function is pure by default
        if self._cleanliness_func is None:
            print('Last/new: {}/{} - metadata: {}'.format(last_inputs, new_inputs, input_metadata))
            if last_outputs is None:
                return False

            # Check if all outputs still exist
            all_outputs_exists = [output.exists() for output in last_outputs] if isinstance(last_outputs,
                                                                                            Iterable) else last_outputs.exists()
            if not all_outputs_exists:
                return False

            if last_inputs is None:
                return last_inputs == new_inputs

            all_new_inputs_exists = [inp.exists() for inp in new_inputs] if isinstance(new_inputs,
                                                                                       Iterable) else new_inputs.exists()
            if not all_new_inputs_exists:
                return False

            new_input_metadata = []
            for inp in new_inputs:
                new_input_metadata.append(get_metadata(inp))

            print('Metadata check: {} == {}'.format(input_metadata, new_input_metadata))
            return input_metadata == new_input_metadata

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
