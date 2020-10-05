# coding=utf-8
import argparse
import json
import shutil
from pathlib import Path
from typing import Iterable, Callable, Dict, Union, Set

from .alkymi import compute_status_with_cache, Status, evaluate_recipe, compute_recipe_status
from .foreach_recipe import ForeachRecipe
from .recipe import Recipe


class Lab:
    CACHE_DIRECTORY_NAME = ".alkymi_cache"

    def __init__(self, name: str, disable_caching=False):
        self._name = name
        self.cache_path = Path(Lab.CACHE_DIRECTORY_NAME) / '{}.json'.format(self.name)
        self._recipes = set()  # type: Set[Union[Recipe, ForeachRecipe]]

        # Try to load pre-existing state from cache file
        self._disable_caching = disable_caching

    def _try_load_state(self) -> None:
        if self._disable_caching or not self.cache_path.exists():
            return

        with self.cache_path.open('r') as f:
            json_items = json.loads(f.read())
            for recipe in self._recipes:
                if recipe.function_hash in json_items:
                    recipe.restore_from_dict(json_items[recipe.function_hash])

    def _save_state(self) -> None:
        if self._disable_caching:
            return

        self.cache_path.parent.mkdir(exist_ok=True)
        with self.cache_path.open('w') as f:
            states = {recipe.function_hash: recipe.to_dict() for recipe in self._recipes}
            f.write(json.dumps(states, indent=4))

    def recipe(self, ingredients: Iterable[Recipe] = (), transient: bool = False) -> Callable[[Callable], Recipe]:
        def _decorator(func: Callable) -> Recipe:
            return self.add_recipe(Recipe(ingredients, func, func.__name__, transient))

        return _decorator

    def map_recipe(self, mapped_inputs: Recipe, ingredients: Iterable[Recipe] = (), transient: bool = False) -> \
            Callable[[Callable], ForeachRecipe]:
        def _decorator(func: Callable) -> ForeachRecipe:
            return self.add_recipe(ForeachRecipe(mapped_inputs, ingredients, func, func.__name__, transient))

        return _decorator

    def add_recipe(self, recipe: Union[Recipe, ForeachRecipe]) -> Union[Recipe, ForeachRecipe]:
        self._recipes.add(recipe)
        return recipe

    def brew(self, target_recipe: Union[Recipe, str]):
        if isinstance(target_recipe, str):
            # Try to match name
            for recipe in self._recipes:
                if recipe.name == target_recipe:
                    result = evaluate_recipe(recipe, compute_recipe_status(recipe))
                    self._save_state()
                    return result
            raise ValueError("Unknown recipe: {}".format(target_recipe))
        else:
            # Match recipe directly
            if target_recipe in self._recipes:
                result = evaluate_recipe(target_recipe, compute_recipe_status(target_recipe))
                self._save_state()
                return result
            raise ValueError("Unknown recipe: {}".format(target_recipe.name))

    @property
    def name(self) -> str:
        return self._name

    @property
    def recipes(self) -> 'Set[Recipe]':
        return self._recipes

    def build_full_status(self) -> Dict[Recipe, Status]:
        status = {}  # type: Dict[Recipe, Status]
        for recipe in self._recipes:
            compute_status_with_cache(recipe, status)
        return status

    def __repr__(self) -> str:
        status = self.build_full_status()
        state = ''
        for recipe in self._recipes:
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
        clean_parser.add_argument('recipe', choices=[recipe.name for recipe in self._recipes],
                                  help='Recipe to clean')

        # Create the parser for the "command_b" command
        brew_parser = subparsers.add_parser('brew', help='Brew the selected recipe')
        brew_parser.add_argument('recipe', choices=[recipe.name for recipe in self._recipes],
                                 help='Recipe to brew')

        args = parser.parse_args()
        if args.subparser_name == 'status':
            print(self)
        elif args.subparser_name == 'clean-cache':
            shutil.rmtree(self.cache_path.parent)
        elif args.subparser_name == 'clean':
            print('Cleaning outputs for {}'.format(args.recipe))
            raise NotImplementedError("Clean doesn't work yet!")
        elif args.subparser_name == 'brew':
            return self.brew(args.recipe)
