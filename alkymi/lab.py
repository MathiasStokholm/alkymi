# coding=utf-8
import copy
import json
import argparse
import shutil
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Iterable, Callable, Optional, List, Dict, Union, Tuple, Any

from .metadata import get_metadata
from .alkymi import Recipe, RepeatedRecipe
from .serialization import load_outputs


class Status(Enum):
    Ok = 0
    IngredientDirty = 1
    NotEvaluatedYet = 2
    Dirty = 3
    BoundFunctionChanged = 4


class RecipeState:
    def __init__(self, function_name: str, function_hash: int, inputs: Optional[Tuple[Path]],
                 outputs: Optional[Tuple[Path]], input_metadata=None, output_metadata=None):
        self.function_name = function_name
        self.function_hash = function_hash

        if output_metadata is None:
            self._outputs = None
            self._output_metadata = None
            self.outputs = outputs
        else:
            self._outputs = outputs
            self._output_metadata = output_metadata

        if input_metadata is None:
            self._inputs = None
            self._input_metadata = None
            self.inputs = inputs
        else:
            self._inputs = inputs
            self._input_metadata = input_metadata

    @staticmethod
    def from_recipe(recipe: Recipe, inputs: Optional[List[Path]],
                    outputs: Optional[List[Path]]):
        return RecipeState(recipe.name, recipe.function_hash, inputs, outputs)

    @property
    def inputs(self):
        return self._inputs

    @inputs.setter
    def inputs(self, inputs: Optional[List[Path]]):
        if inputs is None:
            return

        self._input_metadata = []
        for inp in inputs:
            self._input_metadata.append(get_metadata(inp))
        self._inputs = inputs

    @property
    def input_metadata(self):
        return self._input_metadata

    @property
    def outputs(self):
        return self._outputs

    @outputs.setter
    def outputs(self, outputs: Optional[Tuple[Path]]):
        if outputs is None:
            return

        self._output_metadata = []
        for out in outputs:
            self._output_metadata.append(get_metadata(out))
        self._outputs = outputs

    @property
    def output_metadata(self):
        return self._output_metadata

    def to_dict(self):
        results = copy.copy(self.__dict__)

        if results['_inputs'] is not None:
            inputs = list(results['_inputs'])
            for i, inp in enumerate(inputs):
                if isinstance(inp, Iterable):
                    inputs[i] = [str(item) for item in inp]
                else:
                    inputs[i] = str(inp)
            results['_inputs'] = tuple(inputs)

        if results['_outputs'] is not None:
            outputs = list(results['_outputs'])
            for i, out in enumerate(outputs):
                if isinstance(out, Iterable):
                    outputs[i] = [str(item) for item in out]
                else:
                    outputs[i] = str(out)
            results['_outputs'] = tuple(outputs)
        return results

    @staticmethod
    def from_dict(json_data):
        inputs = load_outputs(json_data['_inputs'])
        input_metadata = json_data["_input_metadata"]
        outputs = load_outputs(json_data['_outputs'])
        output_metadata = json_data["_output_metadata"]
        return RecipeState(json_data['function_name'], json_data['function_hash'], inputs, outputs, input_metadata,
                           output_metadata)


class Lab:
    def __init__(self, name: str, disable_caching=False):
        self._name = name
        self.cache_path = Path('.alkymi/{}.json'.format(self.name))
        self._recipes = OrderedDict()  # type: OrderedDict[str, Recipe]
        self._recipe_states = dict()  # type: Dict[str, RecipeState]

        # Try to load pre-existing state from cache file
        self._disable_caching = disable_caching
        self._try_load_state()

    def _try_load_state(self) -> None:
        if self._disable_caching or not self.cache_path.exists():
            return

        with self.cache_path.open('r') as f:
            json_items = json.loads(f.read())
            for name, item in json_items.items():
                self._recipe_states[name] = RecipeState.from_dict(item)

    def _save_state(self) -> None:
        if self._disable_caching:
            return

        self.cache_path.parent.mkdir(exist_ok=True)
        with self.cache_path.open('w') as f:
            states = {key: state.to_dict() for key, state in self._recipe_states.items()}
            f.write(json.dumps(states, indent=4))

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

        if recipe.name not in self._recipe_states:
            self._recipe_states[recipe.name] = RecipeState.from_recipe(recipe, None, None)
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
        if recipe.transient or self._recipe_states[recipe.name].outputs is None:
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
            ingredient_outputs.extend(self._recipe_states[ingredient.name].outputs)

        if not recipe.is_clean(self._recipe_states[recipe.name].inputs,
                               self._recipe_states[recipe.name].input_metadata,
                               self._recipe_states[recipe.name].outputs,
                               self._recipe_states[recipe.name].output_metadata,
                               ingredient_outputs if len(ingredient_outputs) > 0 else None):
            status[recipe] = Status.Dirty
            return status[recipe]

        # TODO: Handle repeated inputs (not very elegant and must be changed)
        # if isinstance(recipe, RepeatedRecipe):
        #     if self.compute_status(recipe.inputs, status) != Status.Ok:
        #         status[recipe] = Status.IngredientDirty
        #         return status[recipe]
        #
        #     ingredient_timestamps = self.output_timestamps(recipe.inputs)
        #     if recipe_timestamps is not None and len(recipe_timestamps) > 0:
        #         if ingredient_timestamps is not None:
        #             for stamp in ingredient_timestamps:
        #                 if stamp is not None and stamp > min(recipe_timestamps):
        #                     status[recipe] = Status.Dirty
        #                     return status[recipe]

        # TODO(mathias): Add handling of bound function hash change
        status[recipe] = Status.Ok
        return status[recipe]

    @staticmethod
    def _canonical(outputs: Optional[Union[Tuple, Any]]) -> Optional[Tuple[Any]]:
        if outputs is None:
            return None
        if isinstance(outputs, tuple):
            return outputs
        return outputs,

    def evaluate_recipe(self, recipe: Union[Recipe, RepeatedRecipe],
                        status: Dict[Union[Recipe, RepeatedRecipe], Status]) -> Optional[Tuple[Any]]:
        print('Evaluating recipe: {}'.format(recipe.name))

        def _print_and_return():
            print('Finished evaluating {}'.format(recipe.name))
            return self._recipe_states[recipe.name].outputs

        if status[recipe] == Status.Ok and recipe.name in self._recipe_states:
            return _print_and_return()

        if len(recipe.ingredients) <= 0:
            self._recipe_states[recipe.name].outputs = self._canonical(recipe())
            return _print_and_return()

        # Load ingredient inputs
        ingredient_inputs = []
        for ingredient in recipe.ingredients:
            result = self.evaluate_recipe(ingredient, status)
            self._recipe_states[ingredient.name].outputs = result
            ingredient_inputs.extend(result)
        ingredient_inputs = tuple(ingredient_inputs)

        # Process repeated inputs
        if isinstance(recipe, RepeatedRecipe):
            results = []
            # Evaluate inputs (which is a recipe) and assign outputs and combined inputs
            recipe_inputs = self._canonical(recipe.inputs())
            if recipe_inputs is None or len(recipe_inputs) != 1 or not isinstance(recipe_inputs[0], Iterable):
                raise ValueError("Inputs to a RepeatedRecipe must have exactly one Iterable output")

            self._recipe_states[recipe.inputs.name].outputs = recipe_inputs
            self._recipe_states[recipe.name].inputs = recipe_inputs + ingredient_inputs
            for item in recipe_inputs[0]:
                if len(ingredient_inputs) > 0:
                    results.append(recipe(item, *ingredient_inputs))
                else:
                    results.append(recipe(item))
            self._recipe_states[recipe.name].outputs = self._canonical(results)
            return _print_and_return()

        # Process non-repeated input
        self._recipe_states[recipe.name].inputs = ingredient_inputs
        self._recipe_states[recipe.name].outputs = self._canonical(recipe(*ingredient_inputs))
        return _print_and_return()

    def __repr__(self) -> str:
        status = self.build_status()
        state = ''
        for _, recipe in self._recipes.items():
            state += '\n\t{} - {}'.format(str(recipe), status[recipe])
        return '{} lab with recipes:{}'.format(self.name, state)

    def open(self) -> None:
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
            for output in self._recipe_states[args.recipe].outputs:
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
