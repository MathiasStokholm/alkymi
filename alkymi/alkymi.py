import functools
import subprocess
import logging
from pathlib import Path
import glob
from typing import List, Callable


_logger = logging.getLogger('alkymi')
_logger.setLevel(logging.DEBUG)


def recipe(ingredients=()):
    def _decorator(func):
        functools.wraps(func)

        def _wrapper():
            if len(ingredients) <= 0:
                return func()

            # Massive hack: allow only first ingredient to be mapped

            # Load other (non-mapped) inputs
            other_inputs = []
            for ingredient in ingredients[1:]:
                _logger.debug('Brewing ingredient: {}'.format(ingredient))
                other_inputs.append(ingredient())

            # Load possible mapped first ingredient
            first_ingredient = ingredients[0]
            first_ingredient_input = first_ingredient()
            if not isinstance(first_ingredient, Map):
                _logger.debug('Brewing ingredient: {}'.format(func))
                if len(other_inputs) > 0:
                    return func(first_ingredient_input, *other_inputs)
                else:
                    return func(first_ingredient_input)

            results = []
            for item in first_ingredient_input:
                _logger.debug('Brewing mapped ingredient: {}'.format(func))
                if len(other_inputs) > 0:
                    results.append(func(item, *other_inputs))
                else:
                    results.append(func(item))
            return results
        return _wrapper
    return _decorator


def call(command_line, results):
    subprocess.call(command_line)
    return results


def brew(_recipe):
    return _recipe()


def glob_files(directory: Path, pattern: str) -> Callable[[], List[Path]]:
    def _glob_recipe() -> List[Path]:
        matched_files = glob.glob(str(directory / pattern))
        return [Path(f) for f in matched_files]
    return _glob_recipe


class Map(object):
    def __init__(self, iterable_callable):
        self._iterable_callable = iterable_callable

    def __call__(self, *args, **kwargs):
        return self._iterable_callable()

