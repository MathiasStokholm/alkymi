from typing import Dict, List, Any, Tuple, Optional

from .types import Status
from .recipe import Recipe
from .logging import log
from .foreach_recipe import ForeachRecipe

# TODO(mathias): Rename this file to something more fitting

OutputsAndChecksums = Tuple[Optional[Tuple[Any, ...]], Optional[Tuple[Optional[str], ...]]]


def compute_recipe_status(recipe: Recipe) -> Dict[Recipe, Status]:
    """
    Compute the Status for the provided recipe and all dependencies (ingredients or mapped inputs)

    :param recipe: The recipe for which status should be computed
    :return: The status of the provided recipe and all dependencies as a dictionary
    """
    status = {}  # type: Dict[Recipe, Status]
    compute_status_with_cache(recipe, status)
    return status


def compute_status_with_cache(recipe: Recipe, status: Dict[Recipe, Status]) -> Status:
    """
    Compute the Status for the provided recipe and all dependencies (ingredients or mapped inputs) and store the results
    in the provided status dictionary.

    This function will early-exit if the status for the provided recipe has already been computed, and will recursively
    compute statuses of dependencies (ingredients or mapped inputs)

    :param recipe: The recipe for which status should be computed
    :param status: The dictionary to add computed statuses to
    :return: The status of the input recipe
    """
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
    if recipe.transient or recipe.output_checksums is None:
        status[recipe] = Status.NotEvaluatedYet
        return status[recipe]

    # Check if one or more children are dirty
    ingredient_output_checksums = []  # type: List[Optional[str]]
    for ingredient in recipe.ingredients:
        if compute_status_with_cache(ingredient, status) != Status.Ok:
            status[recipe] = Status.IngredientDirty
            return status[recipe]
        if ingredient.output_checksums is not None:  # This will never happen, but this satisfies the type checker
            ingredient_output_checksums.extend(ingredient.output_checksums)
    ingredient_output_checksums_tuple = tuple(ingredient_output_checksums)  # type: Tuple[Optional[str], ...]

    if isinstance(recipe, ForeachRecipe):
        # Check cleanliness of mapped inputs, inputs and outputs
        if compute_status_with_cache(recipe.mapped_recipe, status) != Status.Ok:
            status[recipe] = Status.MappedInputsDirty
            return status[recipe]
        if recipe.mapped_recipe.output_checksums is None:
            raise Exception("Input checksum to mapped recipe {} is None".format(recipe.name))
        if len(recipe.mapped_recipe.output_checksums) != 1:
            raise Exception("Input checksum to mapped recipe {} must be a single element".format(recipe.name))
        if not recipe.is_foreach_clean(recipe.mapped_recipe.output_checksums[0]):
            status[recipe] = Status.MappedInputsDirty
            return status[recipe]

    # Check cleanliness of inputs and outputs
    status[recipe] = recipe.is_clean(ingredient_output_checksums_tuple)
    return status[recipe]


def evaluate_recipe(recipe: Recipe, status: Dict[Recipe, Status]) -> OutputsAndChecksums:
    """
    Evaluate a recipe using precomputed statuses

    :param recipe: The recipe to evaluate
    :param status: The dictionary of statuses computed using 'compute_recipe_status()' to use for targeted evaluation
    :return: The outputs and checksums of the provided recipe (wrapped in tuples if necessary)
    """
    log.debug('Evaluating recipe: {}'.format(recipe.name))

    def _print_and_return() -> OutputsAndChecksums:
        log.debug('Finished evaluating {}'.format(recipe.name))
        return recipe.outputs, recipe.output_checksums

    if status[recipe] == Status.Ok:
        return _print_and_return()

    if len(recipe.ingredients) <= 0 and not isinstance(recipe, ForeachRecipe):
        recipe.invoke(inputs=tuple(), input_checksums=tuple())
        return _print_and_return()

    # Load ingredient inputs
    ingredient_inputs = []  # type: List[Any]
    ingredient_input_checksums = []  # type: List[Optional[str]]
    for ingredient in recipe.ingredients:
        result, checksum = evaluate_recipe(ingredient, status)
        if result is not None:
            ingredient_inputs.extend(result)
        if checksum is not None:
            ingredient_input_checksums.extend(checksum)
    ingredient_inputs_tuple = tuple(ingredient_inputs)  # type: Tuple[Any, ...]
    ingredient_input_checksums_tuple = tuple(ingredient_input_checksums)  # type: Tuple[Optional[str], ...]

    # Process inputs
    if isinstance(recipe, ForeachRecipe):
        # Process mapped inputs
        mapped_inputs_tuple, mapped_inputs_checksum_tuple = evaluate_recipe(recipe.mapped_recipe, status)
        if mapped_inputs_tuple is None:
            raise Exception("Input to mapped recipe {} is None".format(recipe.name))
        if len(mapped_inputs_tuple) != 1:
            raise Exception("Input to mapped recipe {} must be a single list or dict".format(recipe.name))
        mapped_inputs = mapped_inputs_tuple[0]

        if mapped_inputs_checksum_tuple is None:
            raise Exception("Input checksums to mapped recipe {} is None".format(recipe.name))
        if len(mapped_inputs_checksum_tuple) != 1:
            raise Exception("Input checksums to mapped recipe {} must be a single list or dict".format(recipe.name))
        mapped_inputs_checksum = mapped_inputs_checksum_tuple[0]

        # Mapped inputs can either be a list or a dictionary
        if not isinstance(mapped_inputs, list) and not isinstance(mapped_inputs, dict):
            raise Exception("Input to mapped recipe {} must be a list or a dict".format(recipe.name))
        recipe.invoke_mapped(mapped_inputs=mapped_inputs, mapped_inputs_checksum=mapped_inputs_checksum,
                             inputs=ingredient_inputs_tuple, input_checksums=ingredient_input_checksums_tuple)
    else:
        # Regular Recipe
        recipe.invoke(inputs=ingredient_inputs_tuple, input_checksums=ingredient_input_checksums_tuple)
    return _print_and_return()
