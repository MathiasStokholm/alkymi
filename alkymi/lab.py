# coding=utf-8

import os
import argparse
import collections
from enum import Enum
from typing import Iterable, Callable, OrderedDict, Optional, List, Dict, Union
from alkymi import Recipe, RepeatedRecipe


class Status(Enum):
    Ok = 0
    IngredientDirty = 1
    NotEvaluatedYet = 2
    Dirty = 3
    BoundFunctionChanged = 4


class Lab:
    def __init__(self, name: str):
        self._name = name
        self._recipes = collections.OrderedDict()
        self._outputs = dict()

    def recipe(self, ingredients: Iterable[Recipe] = (), transient: bool = False) -> Callable[[Callable], Recipe]:
        def _decorator(func: Callable) -> Recipe:
            recipe = Recipe(ingredients, func, func.__name__, transient)
            self._recipes[recipe.name] = recipe
            return recipe

        return _decorator

    def add_recipe(self, recipe: Recipe) -> Recipe:
        self._recipes[recipe.name] = recipe
        return recipe

    def foreach(self, inputs: Callable[[], Iterable[Recipe]], ingredients: Iterable[Recipe] = (),
                transient: bool = False):
        def _decorator(func: Callable):
            recipe = RepeatedRecipe(inputs, ingredients, func, func.__name__, transient)
            self._recipes[recipe.name] = recipe
            return recipe

        return _decorator

    def brew(self, target_recipe: Union[Recipe, str]):
        recipe_name = target_recipe if isinstance(target_recipe, str) else target_recipe.name
        self.evaluate_recipe(self._recipes[recipe_name], self.build_status())

    @property
    def name(self) -> str:
        return self._name

    @property
    def recipes(self) -> OrderedDict[str, Recipe]:
        return self._recipes

    def output_timestamps(self, recipe) -> Optional[List[float]]:
        results = self._outputs.get(recipe, None)
        if results is None:
            return None

        if isinstance(results, Iterable):
            return [os.path.getmtime(str(path)) for path in results]
        return [os.path.getmtime(str(results))]

    def build_status(self) -> Dict[Recipe, Status]:
        status = {}
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
        if recipe.transient or recipe not in self._outputs:
            status[recipe] = Status.NotEvaluatedYet
            return status[recipe]

        recipe_timestamps = self.output_timestamps(recipe)
        for ingredient in recipe.ingredients:
            if self.compute_status(ingredient, status) != Status.Ok:
                status[recipe] = Status.IngredientDirty
                return status[recipe]

            ingredient_timestamps = self.output_timestamps(ingredient)
            if recipe_timestamps is not None and len(recipe_timestamps) > 0:
                if ingredient_timestamps is not None:
                    for stamp in ingredient_timestamps:
                        if stamp > recipe_timestamps[0]:
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
            return self._outputs[recipe]

        if status[recipe] == Status.Ok and recipe in self._outputs:
            return _print_and_return()

        if len(recipe.ingredients) <= 0:
            self._outputs[recipe] = recipe()
            return _print_and_return()

        # Load ingredient inputs
        ingredient_inputs = []
        for ingredient in recipe.ingredients:
            self._outputs[ingredient] = self.evaluate_recipe(ingredient, status)
            ingredient_inputs.append(self._outputs[ingredient])

        # Process repeated inputs
        if isinstance(recipe, RepeatedRecipe):
            results = []
            recipe_inputs = recipe.inputs()
            for item in recipe_inputs:
                if len(ingredient_inputs) > 0:
                    results.append(recipe(item, *ingredient_inputs))
                else:
                    results.append(recipe(item))
            self._outputs[recipe] = results
            return _print_and_return()

        # Process non-repeated input
        self._outputs[recipe] = recipe(*ingredient_inputs)
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
