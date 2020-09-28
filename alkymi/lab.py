# coding=utf-8
import argparse
import json
import shutil
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Iterable, Callable, Optional, Dict, Union, Tuple, Any

from .alkymi import Recipe


class Status(Enum):
    Ok = 0
    IngredientDirty = 1
    NotEvaluatedYet = 2
    Dirty = 3
    BoundFunctionChanged = 4


class Lab:
    def __init__(self, name: str, disable_caching=False):
        self._name = name
        self.cache_path = Path('.alkymi/{}.json'.format(self.name))
        self._recipes = OrderedDict()  # type: OrderedDict[str, Recipe]

        # Try to load pre-existing state from cache file
        self._disable_caching = disable_caching

    def _try_load_state(self) -> None:
        if self._disable_caching or not self.cache_path.exists():
            return

        with self.cache_path.open('r') as f:
            json_items = json.loads(f.read())
            for name, recipe in self._recipes.items():
                recipe.restore_from_dict(json_items[name])

    def _save_state(self) -> None:
        if self._disable_caching:
            return

        self.cache_path.parent.mkdir(exist_ok=True)
        with self.cache_path.open('w') as f:
            states = {name: recipe.to_dict() for name, recipe in self._recipes.items()}
            f.write(json.dumps(states, indent=4))

    def recipe(self, ingredients: Iterable[Recipe] = (), transient: bool = False) -> Callable[[Callable], Recipe]:
        def _decorator(func: Callable) -> Recipe:
            return self.add_recipe(Recipe(ingredients, func, func.__name__, transient))

        return _decorator

    def add_recipe(self, recipe: Recipe) -> Recipe:
        self._recipes[recipe.name] = recipe
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

    def build_status(self) -> Dict[Recipe, Status]:
        status = {}  # type: Dict[Recipe, Status]
        for _, recipe in self._recipes.items():
            self.compute_status(recipe, status)
        return status

    def compute_status(self, recipe: Recipe, status: Dict[Recipe, Status]) -> Status:
        # Early exit if status already determined
        if recipe in status:
            return status[recipe]

        # This recipe is dirty if:
        # 1. One or more ingredients are dirty and need to be reevaluated
        # 2. There's no cached output for this recipe
        # 3. The cached output for this recipe is older than the output of any ingredient
        # 3. The bound function has changed (later)
        if recipe.transient or self._recipes[recipe.name].outputs is None:
            status[recipe] = Status.NotEvaluatedYet
            return status[recipe]

        # # Run custom cleanliness check if necessary
        # if not recipe.is_clean(self._recipe_states[recipe.name].output):
        #     status[recipe] = Status.Dirty
        #     return status[recipe]

        ingredient_outputs = []
        for ingredient in recipe.ingredients:
            if self.compute_status(ingredient, status) != Status.Ok:
                status[recipe] = Status.IngredientDirty
                return status[recipe]
            ingredient_outputs.extend(self._recipes[ingredient.name].outputs)

        if not recipe.is_clean(ingredient_outputs):
            status[recipe] = Status.Dirty
            return status[recipe]

        # TODO(mathias): Add handling of bound function hash change
        status[recipe] = Status.Ok
        return status[recipe]

    def evaluate_recipe(self, recipe: Recipe, status: Dict[Recipe, Status]) -> Optional[Tuple[Any]]:
        print('Evaluating recipe: {}'.format(recipe.name))

        def _print_and_return():
            print('Finished evaluating {}'.format(recipe.name))
            return self._recipes[recipe.name].outputs

        if status[recipe] == Status.Ok and recipe.name in self._recipes:
            return _print_and_return()

        if len(recipe.ingredients) <= 0:
            recipe.invoke()
            return _print_and_return()

        # Load ingredient inputs
        ingredient_inputs = []
        for ingredient in recipe.ingredients:
            result = self.evaluate_recipe(ingredient, status)
            ingredient_inputs.extend(result)
        ingredient_inputs = tuple(ingredient_inputs)

        # Process inputs
        recipe.invoke(*ingredient_inputs)
        return _print_and_return()

    def __repr__(self) -> str:
        status = self.build_status()
        state = ''
        for _, recipe in self._recipes.items():
            state += '\n\t{} - {}'.format(str(recipe), status[recipe])
        return '{} lab with recipes:{}'.format(self.name, state)

    def open(self) -> None:
        self._try_load_state()

        # Create the top-level parser
        parser = argparse.ArgumentParser('CLI for {}'.format(self._name))
        subparsers = parser.add_subparsers(help='sub-command help', dest='subparser_name')

        # Create the parser for the "status" command
        subparsers.add_parser('status', help='Prints the detailed status of the lab')

        # Create the parser for the "clean-cache" command
        subparsers.add_parser('clean-cache', help='Cleans the cache of the lab')

        # Create the parser for the "clean" command
        clean_parser = subparsers.add_parser('clean', help='Cleans the outputs of a provided recipe')
        clean_parser.add_argument('recipe', choices=[name for name, recipe in self._recipes.items()],
                                  help='Recipe to clean')

        # Create the parser for the "command_b" command
        brew_parser = subparsers.add_parser('brew', help='Brew the selected recipe')
        brew_parser.add_argument('recipe', choices=[name for name, recipe in self._recipes.items()],
                                 help='Recipe to brew')

        args = parser.parse_args()
        if args.subparser_name == 'status':
            print(self)
        elif args.subparser_name == 'clean-cache':
            shutil.rmtree(self.cache_path.parent)
        elif args.subparser_name == 'clean':
            print('Cleaning outputs for {}'.format(args.recipe))
            for output in self._recipes[args.recipe].outputs:
                if isinstance(output, Path) and output.exists():
                    output.unlink()
                    print('Removed {}'.format(output))
                else:
                    for path in output:
                        if path.exists():
                            path.unlink(missing_ok=True)
                            print('Removed {}'.format(output))
        elif args.subparser_name == 'brew':
            return self.brew(args.recipe)
