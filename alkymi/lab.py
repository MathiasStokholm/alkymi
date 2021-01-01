import argparse
import logging
from typing import Dict, Union, Any, List

from .alkymi import compute_status_with_cache, Status
from .logging import log
from .recipe import Recipe


class Lab:
    """
    Class used to define a collection of alkymi recipes and expose them as a command line interface (CLI)

    This can be used to create files that bear resemblance to Makefiles (see alkymi/lab.py as an example)
    """

    def __init__(self, name: str):
        """
        Creates a new Lab with the provided name

        :param name: The name of the Lab
        """
        self._name = name
        self._recipes = []  # type: List[Recipe]

    def add_recipe(self, recipe: Recipe) -> Recipe:
        """
        Add a new recipe to the Lab (this will make the recipe available through the CLI)

        :param recipe: The recipe to add
        :return: The input recipe (to allow chaining calls)
        """
        if recipe not in self._recipes:
            self._recipes.append(recipe)
        return recipe

    def add_recipes(self, *recipes: Recipe) -> None:
        """
        Add a set of recipes to the Lab (this will make the recipes available through the CLI)

        :param recipes: The recipes to add
        """
        for recipe in recipes:
            self.add_recipe(recipe)

    def brew(self, target_recipe: Union[Recipe, str]) -> Any:
        """
        Brew (evaluate) a target recipe defined by its reference or name, and return the results

        :param target_recipe: The recipe to evaluate, as a reference ot by name
        :return: The output of the evaluated recipe
        """
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
        """
        :return: The name of this Lab
        """
        return self._name

    @property
    def recipes(self) -> List[Recipe]:
        """
        :return: The list of recipes contained in this Lab
        """
        return self._recipes

    def _build_full_status(self) -> Dict[Recipe, Status]:
        """
        Compute statuses for all recipes (and dependent recipes) in this Lab

        :return: The statuses as a dictionary
        """
        status = {}  # type: Dict[Recipe, Status]
        for recipe in self._recipes:
            compute_status_with_cache(recipe, status)
        return status

    def __repr__(self) -> str:
        """
        :return: A string representation of this Lab with recipes and their statuses
        """
        status = self._build_full_status()
        state = ''
        for recipe in self._recipes:
            state += '\n\t{} - {}'.format(str(recipe), status[recipe])
        return '{} lab with recipes:{}'.format(self.name, state)

    def open(self) -> None:
        """
        Runs the command line interface for this Lab by parsing command line arguments and carrying out the designated
        command
        """
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
