from typing import Dict, List, Tuple, Optional, cast

from .types import Status
from .recipe import Recipe, R
from .logging import log

import networkx as nx

OutputsAndChecksums = Tuple[R, Optional[str]]


def create_graph(recipe: Recipe[R]) -> nx.DiGraph:
    """
    Create a Directed Acyclic Graph (DAG) based on the provided recipe
    Each node in the graph represents a recipe, and has an associated "status" attribute

    :param recipe: The recipe to construct a graph for
    :return: The constructed graph
    """
    log.debug(f'Building graph for {recipe.name}')
    graph = nx.DiGraph()
    _add_recipe_to_graph(recipe, graph)
    return graph


def _add_recipe_to_graph(recipe: Recipe, graph: nx.DiGraph) -> None:
    """
    Add a node representing a recipe to the graph, and recursively add dependencies of the provided recipe as nodes with
    edges to the current node

    :param recipe: The recipe to create a node for
    :param graph: The graph to which the new node and edges should be added
    """
    graph.add_node(recipe)
    log.debug(f'Added {recipe.name} to graph')

    # For each ingredient, add an edge from the ingredient to this recipe
    for _ingredient in recipe.ingredients:
        _add_recipe_to_graph(_ingredient, graph)
        graph.add_edge(_ingredient, recipe)


def _compute_status(recipe: Recipe, graph: nx.DiGraph, statuses: Dict[Recipe, Status]) -> Status:
    def _store_and_return(_status: Status):
        statuses[recipe] = _status
        return _status

    # Check if one or more ingredients (dependencies) are dirty
    ingredient_dirty = False
    ingredient_output_checksums: List[Optional[str]] = []
    for ingredient in graph.predecessors(recipe):
        ingredient_status = _compute_status(ingredient, graph, statuses)
        if ingredient_status != Status.Ok:
            ingredient_dirty = True
        if ingredient.output_checksum is not None:
            ingredient_output_checksums.append(ingredient.output_checksum)
    ingredient_output_checksums_tuple: Tuple[Optional[str], ...] = tuple(ingredient_output_checksums)

    if recipe.transient or recipe.output_checksum is None:
        return _store_and_return(Status.NotEvaluatedYet)

    if ingredient_dirty:
        return _store_and_return(Status.IngredientDirty)

    status = is_clean(recipe, ingredient_output_checksums_tuple)
    return _store_and_return(status)


def compute_recipe_status(recipe: Recipe[R], graph: nx.DiGraph) -> Dict[Recipe, Status]:
    """
    Compute the Status for the provided recipe and all dependencies (ingredients or mapped inputs)

    :param recipe: The recipe for which status should be computed
    :param graph: The graph representing the recipe and all its dependencies
    :return: The status of the provided recipe and all dependencies as a dictionary
    """
    # Start recursion with an empty status dict
    statuses: Dict[Recipe, Status] = {}
    _compute_status(recipe, graph, statuses)
    return statuses


def evaluate_recipe(recipe: Recipe[R], graph: nx.DiGraph, statuses: Dict[Recipe, Status]) -> OutputsAndChecksums[R]:
    # Sort the graph topographically, such that any recipe in the sorted list only depends on earlier recipes
    # This guarantees that the 'outputs' and 'output_checksum' attributes will be available for all dependencies of a
    # recipe once we arrive at it in the order of iteration
    recipes = list(nx.topological_sort(graph))

    for recipe in recipes:
        # If status is Ok, the recipe has already been evaluated, so we can just move on to the next recipe
        if statuses[recipe] == Status.Ok:
            log.debug('Recipe already evaluated: {}'.format(recipe.name))
            continue
        log.debug('Evaluating recipe: {}'.format(recipe.name))

        # Collect inputs and checksums
        inputs = tuple(recipe.outputs for recipe in recipe.ingredients)
        input_checksums = tuple(recipe.output_checksum for recipe in recipe.ingredients)
        recipe.invoke(inputs, input_checksums)

    # Return the output and checksum of the final recipe
    return cast(R, recipe.outputs), recipe.output_checksum


def is_clean(recipe: Recipe[R], new_input_checksums: Tuple[Optional[str], ...]) -> Status:
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
    if recipe.output_checksum is None:
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


def brew(recipe: Recipe[R]) -> R:
    """
    Evaluate a Recipe and all dependent inputs - this will build the computational graph and execute any needed
    dependencies to produce the outputs of the input Recipe

    :param recipe: The Recipe to evaluate
    :return: The outputs of the Recipe (which correspond to the outputs of the bound function)
    """
    graph = create_graph(recipe)
    statuses = compute_recipe_status(recipe, graph)
    result, _ = evaluate_recipe(recipe, graph, statuses)
    return result
