# coding=utf-8
import copy
import json
import os
import argparse
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Iterable, Callable, Optional, List, Dict, Union
from .alkymi import Recipe, RepeatedRecipe


class Status(Enum):
    Ok = 0
    IngredientDirty = 1
    NotEvaluatedYet = 2
    Dirty = 3
    BoundFunctionChanged = 4


class Output:
    def __init__(self, function_name: str, function_hash: int, output: Optional[Union[Path, List[Path]]]):
        self.function_name = function_name
        self.function_hash = function_hash
        self.output = output

    @staticmethod
    def from_recipe(recipe: Recipe, output: Optional[Union[Path, List[Path]]]):
        return Output(recipe.name, recipe.function_hash, output)

    def to_dict(self):
        results = copy.copy(self.__dict__)

        if results['output'] is not None:
            if isinstance(results['output'], Iterable):
                results['output'] = [str(output) for output in results['output']]
            else:
                results['output'] = str(results['output'])
        return results

    @staticmethod
    def from_dict(json_data):
        paths = json_data['output']
        if paths is not None:
            if isinstance(paths, str):
                paths = Path(paths)
            else:
                paths = [Path(path) for path in paths]
        return Output(json_data['function_name'], json_data['function_hash'], paths)


class Lab:
    def __init__(self, name: str, disable_caching=False):
        self._name = name
        self.cache_path = Path('.alkymi/{}.json'.format(self.name))
        self._recipes = OrderedDict()  # type: OrderedDict[str, Recipe]
        self._outputs = dict()  # type: Dict[str, Output]

        # Try to load pre-existing state from cache file
        self._disable_caching = disable_caching
        self._try_load_state()

    def _try_load_state(self) -> None:
        if self._disable_caching or not self.cache_path.exists():
            return

        with self.cache_path.open('r') as f:
            json_items = json.loads(f.read())
            for name, item in json_items.items():
                self._outputs[name] = Output.from_dict(item)

    def _save_state(self) -> None:
        if self._disable_caching:
            return

        self.cache_path.parent.mkdir(exist_ok=True)
        with self.cache_path.open('w') as f:
            outputs = {key: output.to_dict() for key, output in self._outputs.items()}
            f.write(json.dumps(outputs, indent=4))

    def recipe(self, ingredients: Iterable[Recipe] = (), transient: bool = False) -> Callable[[Callable], Recipe]:
        def _decorator(func: Callable) -> Recipe:
            return self.add_recipe(Recipe(ingredients, func, func.__name__, transient))

        return _decorator

    def foreach(self, inputs: Recipe, ingredients: Iterable[Recipe] = (),
                transient: bool = False):
        def _decorator(func: Callable):
            return self.add_recipe(RepeatedRecipe(inputs, ingredients, func, func.__name__, transient))

        return _decorator

    def add_recipe(self, recipe: Union[Recipe, RepeatedRecipe]) -> Union[Recipe, RepeatedRecipe]:
        self._recipes[recipe.name] = recipe

        if recipe.name not in self._outputs:
            self._outputs[recipe.name] = Output.from_recipe(recipe, None)
        return recipe

    def brew(self, target_recipe: Union[Recipe, str]):
        recipe_name = target_recipe if isinstance(target_recipe, str) else target_recipe.name
        result = self.evaluate_recipe(self._recipes[recipe_name], self.build_status())
        self._save_state()
        return result

    @property
    def name(self) -> str:
        return self._name

    @property
    def recipes(self) -> 'OrderedDict[str, Recipe]':
        return self._recipes

    def output_timestamps(self, recipe) -> Optional[List[Optional[float]]]:
        """
        Find the timestamps representing when the output files of a recipe were last modified. If a file no longer
        exists (e.g. because of deletion by user), None is returned to represent the missing file/timestamp
        :param recipe: The recipe to find timetamps for
        :return: A list of last modified timestamps (or None for each missing file) or None if outputs are yet unknown
        """
        results = self._outputs[recipe.name].output
        if results is None:
            return None

        if isinstance(results, Path):
            return [os.path.getmtime(str(results))] if results.exists() else [None]

        # List of output files
        return [os.path.getmtime(str(path)) if path.exists() else None for path in results]

    def build_status(self) -> Dict[Recipe, Status]:
        status = {}  # type: Dict[Recipe, Status]
        for _, recipe in self._recipes.items():
            self.compute_status(recipe, status)
        return status

    def compute_status(self, recipe: Union[Recipe, RepeatedRecipe],
                       status: Dict[Union[Recipe, RepeatedRecipe], Status]) -> Status:
        # Early exit if status already determined
        if recipe in status:
            return status[recipe]

        # This recipe is dirty if:
        # 1. One or more ingredients are dirty and need to be reevaluated
        # 2. There's no cached output for this recipe
        # 3. The cached output for this recipe is older than the output of any ingredient
        # 3. The bound function has changed (later)
        if recipe.transient or self._outputs[recipe.name].output is None:
            status[recipe] = Status.NotEvaluatedYet
            return status[recipe]

        # Check if one or more outputs of this recipe has been deleted
        recipe_timestamps = self.output_timestamps(recipe)
        for stamp in recipe_timestamps:
            if stamp is None:
                status[recipe] = Status.Dirty
                return status[recipe]

        for ingredient in recipe.ingredients:
            if self.compute_status(ingredient, status) != Status.Ok:
                status[recipe] = Status.IngredientDirty
                return status[recipe]

            ingredient_timestamps = self.output_timestamps(ingredient)
            if recipe_timestamps is not None and len(recipe_timestamps) > 0:
                if ingredient_timestamps is not None:
                    for stamp in ingredient_timestamps:
                        if stamp is not None and stamp > recipe_timestamps[0]:
                            status[recipe] = Status.Dirty
                            return status[recipe]

        # Handle repeated inputs (not very elegant and must be changed)
        if isinstance(recipe, RepeatedRecipe):
            if self.compute_status(recipe.inputs, status) != Status.Ok:
                status[recipe] = Status.IngredientDirty
                return status[recipe]

            ingredient_timestamps = self.output_timestamps(recipe.inputs)
            if recipe_timestamps is not None and len(recipe_timestamps) > 0:
                if ingredient_timestamps is not None:
                    for stamp in ingredient_timestamps:
                        if stamp > recipe_timestamps[0]:
                            status[recipe] = Status.Dirty
                            return status[recipe]

        # TODO(mathias): Add handling of bound function hash change
        status[recipe] = Status.Ok
        return status[recipe]

    def evaluate_recipe(self, recipe: Union[Recipe, RepeatedRecipe],
                        status: Dict[Union[Recipe, RepeatedRecipe], Status]):
        print('Evaluating recipe: {}'.format(recipe.name))

        def _print_and_return():
            print('Finished evaluating {}'.format(recipe.name))
            return self._outputs[recipe.name].output

        if status[recipe] == Status.Ok and recipe.name in self._outputs:
            return _print_and_return()

        if len(recipe.ingredients) <= 0:
            self._outputs[recipe.name].output = recipe()
            return _print_and_return()

        # Load ingredient inputs
        ingredient_inputs = []
        for ingredient in recipe.ingredients:
            result = self.evaluate_recipe(ingredient, status)
            self._outputs[ingredient.name].output = result
            ingredient_inputs.append(result)

        # Process repeated inputs
        if isinstance(recipe, RepeatedRecipe):
            results = []
            recipe_inputs = recipe.inputs()
            self._outputs[recipe.inputs.name].output = recipe_inputs
            for item in recipe_inputs:
                if len(ingredient_inputs) > 0:
                    results.append(recipe(item, *ingredient_inputs))
                else:
                    results.append(recipe(item))
            self._outputs[recipe.name].output = results
            return _print_and_return()

        # Process non-repeated input
        self._outputs[recipe.name].output = recipe(*ingredient_inputs)
        return _print_and_return()

    def __repr__(self) -> str:
        status = self.build_status()
        state = ''
        for _, recipe in self._recipes.items():
            state += '\n\t{} - {} ({})'.format(str(recipe), status[recipe], self.output_timestamps(recipe))
        return '{} lab with recipes:{}'.format(self.name, state)

    def open(self) -> None:
        # Create the top-level parser
        parser = argparse.ArgumentParser('CLI for {}'.format(self._name))
        subparsers = parser.add_subparsers(help='sub-command help', dest='subparser_name')

        # Create the parser for the "status" command
        status_parser = subparsers.add_parser('status', help='Prints the detailed status of the lab')

        # Create the parser for the "command_b" command
        brew_parser = subparsers.add_parser('brew', help='Brew the selected recipe')
        brew_parser.add_argument('recipe', choices=[name for name, recipe in self._recipes.items()],
                                 help='Recipe to brew')

        args = parser.parse_args()
        if args.subparser_name == 'status':
            print(self)
        elif args.subparser_name == 'brew':
            self.brew(args.recipe)
