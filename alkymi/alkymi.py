# coding=utf-8
from enum import Enum
from typing import Dict, List, Any, Tuple, Optional

from .recipe import Recipe
from .logging import log
from .foreach_recipe import ForeachRecipe


class Status(Enum):
    Ok = 0
    IngredientDirty = 1
    NotEvaluatedYet = 2
    Dirty = 3
    MappedInputsDirty = 4
    BoundFunctionChanged = 5


def compute_recipe_status(recipe: Recipe) -> Dict[Recipe, Status]:
    status = {}  # type: Dict[Recipe, Status]
    compute_status_with_cache(recipe, status)
    return status


def compute_status_with_cache(recipe: Recipe, status: Dict[Recipe, Status]) -> Status:
    # FIXME(mathias): Find a neater way to cache without early exits
    # Force caching of mapped recipe and ingredients
    if isinstance(recipe, ForeachRecipe):
        compute_status_with_cache(recipe.mapped_recipe, status)
    for ingredient in recipe.ingredients:
        compute_status_with_cache(ingredient, status)

    # Early exit if status already determined
    if recipe in status:
        return status[recipe]

    # Check if recipe hasn't been evaluated yet
    if recipe.transient or recipe.outputs is None:
        status[recipe] = Status.NotEvaluatedYet
        return status[recipe]

    # Check if one or more children are dirty
    ingredient_outputs = []  # type: List[Any]
    for ingredient in recipe.ingredients:
        if compute_status_with_cache(ingredient, status) != Status.Ok:
            status[recipe] = Status.IngredientDirty
            return status[recipe]
        if ingredient.outputs is not None:  # This will never happen, but this satisfies the type checker
            ingredient_outputs.extend(ingredient.outputs)
    ingredient_outputs_tuple = tuple(ingredient_outputs)  # type: Tuple[Any, ...]

    if isinstance(recipe, ForeachRecipe):
        # Check cleanliness of mapped inputs, inputs and outputs
        if compute_status_with_cache(recipe.mapped_recipe, status) != Status.Ok:
            status[recipe] = Status.MappedInputsDirty
            return status[recipe]
        if recipe.mapped_recipe.outputs is None:
            raise Exception("Input to mapped recipe {} is None".format(recipe.name))
        if len(recipe.mapped_recipe.outputs) != 1:
            raise Exception("Input to mapped recipe {} must be a list".format(recipe.name))
        if not recipe.is_mapped_clean(recipe.mapped_recipe.outputs[0]):
            status[recipe] = Status.MappedInputsDirty
            return status[recipe]

    # Check cleanliness of inputs and outputs
    if not recipe.is_clean(ingredient_outputs_tuple):
        status[recipe] = Status.Dirty
        return status[recipe]

    status[recipe] = Status.Ok
    return status[recipe]


def evaluate_recipe(recipe: Recipe, status: Dict[Recipe, Status]) -> Optional[Tuple[Any]]:
    log.debug('Evaluating recipe: {}'.format(recipe.name))

    def _print_and_return():
        log.debug('Finished evaluating {}'.format(recipe.name))
        return recipe.outputs

    if status[recipe] == Status.Ok:
        return _print_and_return()

    if len(recipe.ingredients) <= 0 and not isinstance(recipe, ForeachRecipe):
        recipe.invoke()
        return _print_and_return()

    # Load ingredient inputs
    ingredient_inputs = []  # type: List[Any]
    for ingredient in recipe.ingredients:
        result = evaluate_recipe(ingredient, status)
        if result is not None:
            ingredient_inputs.extend(result)
    ingredient_inputs_tuple = tuple(ingredient_inputs)  # type: Tuple[Any, ...]

    # Process inputs
    if isinstance(recipe, ForeachRecipe):
        # Process mapped inputs
        mapped_inputs = evaluate_recipe(recipe.mapped_recipe, status)
        if mapped_inputs is None:
            raise Exception("Input to mapped recipe {} is None".format(recipe.name))
        if len(mapped_inputs) != 1 and not isinstance(mapped_inputs[0], list):
            raise Exception("Input to mapped recipe {} must be a list".format(recipe.name))
        recipe.invoke(mapped_inputs[0], *ingredient_inputs_tuple)
    else:
        # Regular Recipe
        recipe.invoke(*ingredient_inputs_tuple)
    return _print_and_return()
