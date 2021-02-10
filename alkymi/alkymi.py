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
        if not is_foreach_clean(recipe, recipe.mapped_recipe.output_checksums[0]):
            status[recipe] = Status.MappedInputsDirty
            return status[recipe]

    # Check cleanliness of inputs and outputs
    status[recipe] = is_clean(recipe, ingredient_output_checksums_tuple)
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


def is_clean(recipe, new_input_checksums: Tuple[Optional[str], ...]) -> Status:
    """
    Check whether a Recipe is clean (result is cached) based on a set of (potentially new) input checksums

    :param recipe: The Recipe to check for cleanliness
    :param new_input_checksums: The (potentially new) input checksums to use for checking cleanliness
    :return: Whether the recipe is clean represented by the Status enum
    """
    # Non-pure function may have been changed by external circumstances, use custom check
    if recipe.custom_cleanliness_func is not None:
        if not recipe.custom_cleanliness_func(recipe.outputs):
            return Status.CustomDirty

    # Not clean if outputs were never generated
    if recipe.output_checksums is None:
        return Status.NotEvaluatedYet

    # Compute input checksums and perform equality check
    if recipe.input_checksums != new_input_checksums:
        log.debug('{} -> dirty: input checksums changed'.format(recipe.name))
        return Status.InputsChanged

    # Check if bound function has changed
    if recipe.last_function_hash is not None:
        if recipe.last_function_hash != recipe.function_hash:
            return Status.BoundFunctionChanged

    # Not clean if any output is no longer valid
    if not recipe.outputs_valid:
        return Status.OutputsInvalid

    # All checks passed
    return Status.Ok


def is_foreach_clean(recipe: ForeachRecipe, mapped_inputs_checksum: Optional[str]) -> bool:
    """
    Check whether a ForeachRecipe is clean (in addition to the regular recipe cleanliness checks). This is done by
    comparing the overall checksum for the current mapped inputs to that from the last invoke evaluation

    :param recipe: The ForeachRecipe to check cleanliness of mapped inputs for
    :param mapped_inputs_checksum: A single checksum for all the mapped inputs, used to quickly check
    whether anything has changed
    :return: Whether the input recipe needs to be reevaluated
    """
    return recipe.mapped_inputs_checksum == mapped_inputs_checksum


def brew(recipe: Recipe) -> Any:
    """
    Evaluate a Recipe and all dependent inputs - this will build the computational graph and execute any needed
    dependencies to produce the outputs of the input Recipe

    :param recipe: The Recipe to evaluate
    :return: The outputs of the Recipe (which correspond to the outputs of the bound function)
    """
    result, _ = evaluate_recipe(recipe, compute_recipe_status(recipe))
    if result is None:
        return None

    # Unwrap single item tuples
    # TODO(mathias): Replace tuples with a custom type to avoid issues if someone returns a tuple with one element
    if isinstance(result, tuple) and len(result) == 1:
        return result[0]
    return result
