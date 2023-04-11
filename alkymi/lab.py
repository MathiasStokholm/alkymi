import argparse
import logging
import sys
from typing import Dict, Union, Any, List, Optional
from typing import Iterable, TextIO

from rich import console

from .core import Status, compute_recipe_status, create_graph
from .logging import log
from .recipe import Recipe
from .recipes import Arg
from .types import ProgressType


class Lab:
    """
    Class used to define a collection of alkymi recipes and expose them as a command line interface (CLI)

    This can be used to create files that bear resemblance to Makefiles (see alkymi/labfile.py as an example)
    """

    def __init__(self, name: str):
        """
        Creates a new Lab with the provided name

        :param name: The name of the Lab
        """
        self._name = name
        self._recipes: List[Recipe] = []
        self._args: Dict[str, Arg] = {}
        self._console = console.Console(stderr=False)  # Default to using stdout for output

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

    def register_arg(self, arg: Arg) -> None:
        """
        Register an argument with the Lab (this will make the argument settable through the CLI)

        :param arg: The argument to register
        """
        self._args[arg.name] = arg

    def brew(self, target_recipe: Union[Recipe, str], *, jobs=1,
             progress_type: Optional[ProgressType] = ProgressType.Fancy) -> Any:
        """
        Brew (evaluate) a target recipe defined by its reference or name, and return the results

        :param target_recipe: The recipe to evaluate, as a reference ot by name
        :param jobs: The number of jobs to use for evaluating this recipe in parallel, defaults to 1 (no parallelism),
                     zero or negative values will cause alkymi to use the system's default number of jobs
        :param progress_type: The method to use for showing progress, if None will default to setting in alkymi's config
        :return: The output of the evaluated recipe
        """

        # Helper function to call brew on the matched recipe with CTRL-C handling
        def _call_brew(_recipe: Recipe) -> Any:
            try:
                return _recipe.brew(jobs=jobs, progress_type=progress_type)
            except KeyboardInterrupt:
                self._console.print("[bold red]Interrupted by user")
                sys.exit(1)

        if isinstance(target_recipe, str):
            # Try to match name
            for recipe in self._recipes:
                if recipe.name == target_recipe:
                    return _call_brew(recipe)
            raise ValueError("Unknown recipe: {}".format(target_recipe))
        else:
            # Match recipe directly
            if target_recipe in self._recipes:
                return _call_brew(target_recipe)
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

    @property
    def args(self) -> Dict[str, Arg]:
        """
        :return: The list of args registered with this Lab
        """
        return self._args

    def _build_full_status(self) -> Dict[Recipe, Status]:
        """
        Compute statuses for all recipes (and dependent recipes) in this Lab

        :return: The statuses as a dictionary
        """
        status: Dict[Recipe, Status] = {}
        for recipe in self._recipes:
            graph = create_graph(recipe)
            status.update(compute_recipe_status(recipe, graph))
        return status

    def _add_user_args_(self, parser: argparse.ArgumentParser) -> None:
        """
        Adds user provided arguments to an ArgumentParser instance

        :param parser: The parser to add the user-provided arguments to
        """
        for arg_name, arg in self._args.items():
            # For iterables (e.g. lists), the "type" keyword is actually the type of elements in the iterable
            if issubclass(arg.type, Iterable) and not arg.type == str:
                subtype = arg.subtype if arg.subtype is not None else str
                parser.add_argument("--{}".format(arg_name), type=subtype, nargs="*", dest=arg_name)
            else:
                parser.add_argument("--{}".format(arg_name), type=arg.type, dest=arg_name)

    def __repr__(self) -> str:
        """
        :return: A string representation of this Lab with recipes and their statuses
        """
        status = self._build_full_status()
        state = ''
        for recipe in self._recipes:
            state += '\n\t{} - {}'.format(recipe.name, status[recipe])
        return '{} lab with recipes:{}'.format(self.name, state)

    def print_status(self) -> None:
        colors = {
            Status.Ok: "green",
            Status.NotEvaluatedYet: "red",
            Status.CustomDirty: "yellow",
            Status.BoundFunctionChanged: "yellow",
            Status.IngredientDirty: "yellow",
            Status.InputsChanged: "yellow",
            Status.OutputsInvalid: "yellow",
        }

        status = self._build_full_status()
        state = ''
        for recipe in self._recipes:
            color = colors[status[recipe]]
            status_string = status[recipe].name.replace("Status.", "")
            state += '\n\t[cyan]{} - [{}]{}'.format(recipe.name, color, status_string)
        self._console.print('[bold]{} lab with recipes:[/bold]{}'.format(self.name, state))

    def open(self, args: Optional[List[str]] = None, stream: TextIO = sys.stdout) -> None:
        """
        Runs the command line interface for this Lab by parsing command line arguments and carrying out the designated
        command

        :param args: The input arguments to use - will default to system args
        :param stream: The stream to print output to
        """
        if len(self.recipes) == 0:
            raise RuntimeError("No recipes added to lab - CLI is useless")

        # Use system args if nothing has been provided
        if args is None:
            args = sys.argv[1:]

        # Create the top-level parser
        parser = argparse.ArgumentParser('CLI for {}'.format(self._name))
        parser.add_argument("-v", "--verbose", action="store_true", help="Turn on verbose logging")

        subparsers = parser.add_subparsers(help='sub-command help', dest='subparser_name')

        # Create the parser for the "status" command
        status_parser = subparsers.add_parser('status', help='Prints the detailed status of the lab')
        self._add_user_args_(status_parser)

        # Create the parser for the "brew" command
        brew_parser = subparsers.add_parser('brew', help='Brew the selected recipe')
        brew_parser.add_argument('recipe', choices=[recipe.name for recipe in self._recipes], nargs="+",
                                 help='Recipe(s) to brew')
        brew_parser.add_argument("-j", "--jobs", type=int, default=1,
                                 help="Use N jobs to evaluate the recipe, more than 1 job will parallelize evaluation")
        brew_parser.add_argument("--progress", type=ProgressType, default=ProgressType.Fancy,
                                 choices=list(ProgressType), help="The type of progress indication to use")
        self._add_user_args_(brew_parser)

        parsed_args = parser.parse_args(args)
        log.addHandler(logging.StreamHandler(stream))
        if parsed_args.verbose:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)

        # Create a new console object if output needs to go elsewhere
        if self._console.file != stream:
            self._console = console.Console(file=stream)

        # Set arguments if supplied
        for arg_name, arg in self._args.items():
            provided_val = getattr(parsed_args, arg_name, None)
            if provided_val is not None:
                arg.set(provided_val)

        if parsed_args.subparser_name == 'status':
            self.print_status()
        elif parsed_args.subparser_name == 'brew':
            for recipe in parsed_args.recipe:
                self.brew(recipe, jobs=parsed_args.jobs, progress_type=parsed_args.progress)
        else:
            # No recognized command provided - print help
            parser.print_help(file=stream)
