import argparse
import logging
from typing import Dict, Union, Any, List

from .alkymi import compute_status_with_cache, Status
from .foreach_recipe import ForeachRecipe
from .logging import log
from .recipe import Recipe


class Lab:
    def __init__(self, name: str):
        self._name = name
        self._recipes = []  # type: List[Union[Recipe, ForeachRecipe]]

    def add_recipe(self, recipe: Union[Recipe, ForeachRecipe]) -> Union[Recipe, ForeachRecipe]:
        if recipe not in self._recipes:
            self._recipes.append(recipe)
        return recipe

    def add_recipes(self, *recipes: Union[Recipe, ForeachRecipe]) -> None:
        for recipe in recipes:
            self.add_recipe(recipe)

    def brew(self, target_recipe: Union[Recipe, str]) -> Any:
        if isinstance(target_recipe, str):
            # Try to match name
            for recipe in self._recipes:
                if recipe.name == target_recipe:
                    return recipe.brew()
            raise ValueError("Unknown recipe: {}".format(target_recipe))
        else:
            # Match recipe directly
            if target_recipe in self._recipes:
                return target_recipe.brew()
            raise ValueError("Unknown recipe: {}".format(target_recipe.name))

    @property
    def name(self) -> str:
        return self._name

    @property
    def recipes(self) -> List[Recipe]:
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
        # Create the top-level parser
        parser = argparse.ArgumentParser('CLI for {}'.format(self._name))
        parser.add_argument("-v", "--verbose", action="store_true", help="Turn on verbose logging")

        subparsers = parser.add_subparsers(help='sub-command help', dest='subparser_name')

        # Create the parser for the "status" command
        subparsers.add_parser('status', help='Prints the detailed status of the lab')

        # Create the parser for the "clean-cache" command
        subparsers.add_parser('clean-cache', help='Cleans the cache of the lab')

        # Create the parser for the "clean" command
        clean_parser = subparsers.add_parser('clean', help='Cleans the outputs of a provided recipe')
        clean_parser.add_argument('recipe', choices=[recipe.name for recipe in self._recipes],
                                  help='Recipe to clean')

        # Create the parser for the "brew" command
        brew_parser = subparsers.add_parser('brew', help='Brew the selected recipe')
        brew_parser.add_argument('recipe', choices=[recipe.name for recipe in self._recipes], nargs="+",
                                 help='Recipe(s) to brew')

        args = parser.parse_args()
        log.addHandler(logging.StreamHandler())
        if args.verbose:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)

        if args.subparser_name == 'status':
            print(self)
        elif args.subparser_name == 'clean':
            raise NotImplementedError("clean doesn't work yet!")
        elif args.subparser_name == 'clean-cache':
            raise NotImplementedError("clean-cache doesn't work yet!")
        elif args.subparser_name == 'brew':
            for recipe in args.recipe:
                self.brew(recipe)
