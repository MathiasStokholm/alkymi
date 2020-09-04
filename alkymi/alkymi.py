# coding=utf-8
import os
import subprocess
from inspect import signature
from pathlib import Path
from typing import Iterable, Callable, List, Optional, Any

from .metadata import get_metadata
from .serialization import check_output


class Recipe(object):
    def __init__(self, ingredients: Iterable['Recipe'], func: Callable, name: str, transient: bool,
                 cleanliness_func: Optional[Callable] = None):
        self._ingredients = list(ingredients)
        self._func = func
        self._name = name
        self._transient = transient
        self._cleanliness_func = cleanliness_func
        # print('Func {} signature: {}'.format(name, signature(func)))

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def is_clean(self, last_inputs: Optional[List[Path]], input_metadata,
                 last_outputs: Optional[List[Path]], output_metadata, new_inputs: Optional[List[Path]]) -> bool:
        if self._cleanliness_func is not None:
            # Non-pure function may have been changed by external circumstances, use custom check
            return self._cleanliness_func(last_outputs)

        # Handle default pure function
        print('{} -> Last/new inputs: {}/{} - metadata: {}'.format(self._name, last_inputs, new_inputs,
                                                                   input_metadata))

        # Not clean if outputs were never generated
        if last_outputs is None:
            return False

        # Not clean if any output is no longer valid
        if not all(check_output(output) for output in last_outputs):
            return False

        # Compute output metadata and perform equality check
        current_output_metadata = []
        for out in last_outputs:
            current_output_metadata.append(get_metadata(out))

        print('{} -> Output metadata check: {} == {}'.format(self._name, output_metadata, current_output_metadata))
        if output_metadata != current_output_metadata:
            return False

        # If last inputs were non-existent, new inputs have to be non-existent too for equality
        if last_inputs is None or new_inputs is None:
            return last_inputs == new_inputs

        # Compute input metadata and perform equality check
        new_input_metadata = []
        for inp in new_inputs:
            new_input_metadata.append(get_metadata(inp))

        print('Input metadata check: {} == {}'.format(input_metadata, new_input_metadata))
        if input_metadata != new_input_metadata:
            return False

        # All checks passed
        return True

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
