from typing import Dict, List, Tuple, Optional, cast

from .types import Status
from .recipe import Recipe, R
from .logging import log
from .foreach_recipe import ForeachRecipe

import networkx as nx

# TODO(mathias): Rename this file to something more fitting
OutputsAndChecksums = Tuple[R, Optional[str]]


def create_graph(recipe: Recipe[R]) -> nx.DiGraph:
    graph = nx.DiGraph()
    add_recipe_to_graph(recipe, graph)
    return graph


def add_node_and_dependencies_to_graph(graph: nx.DiGraph, recipe: Recipe, status: Status) -> Status:
    graph.add_node(recipe, status=status)

    # For each ingredient, add an edge from the ingredient to this recipe
    for _ingredient in recipe.ingredients:
        graph.add_edge(_ingredient, recipe)

    if isinstance(recipe, ForeachRecipe):
        # Add an edge from the mapped recipe to this recipe
        graph.add_edge(recipe.mapped_recipe, recipe)
    return status


def add_recipe_to_graph(recipe: Recipe[R], graph: nx.DiGraph) -> Status:
    # Add ingredients as dependencies - create an edge in graph from ingredient to this recipe
    # This is done before any returns to ensure that the full graph is constructed, regardless of statuses
    ingredient_dirty = False
    ingredient_output_checksums: List[Optional[str]] = []
    for ingredient in recipe.ingredients:
        ingredient_status = add_recipe_to_graph(ingredient, graph)
        if ingredient_status != Status.Ok:
            ingredient_dirty = True
        if ingredient.output_checksum is not None:
            ingredient_output_checksums.append(ingredient.output_checksum)
    ingredient_output_checksums_tuple: Tuple[Optional[str], ...] = tuple(ingredient_output_checksums)

    # For ForeachRecipes, add the mapped input as a dependency - create an edge in graph from mapped input to this
    # recipe. This is done before any returns to ensure that the full graph is constructed, regardless of statuses
    mapped_dirty = False
    if isinstance(recipe, ForeachRecipe):
        # Check cleanliness of mapped inputs, inputs and outputs
        mapped_recipe_status = add_recipe_to_graph(recipe.mapped_recipe, graph)
        if mapped_recipe_status != Status.Ok:
            mapped_dirty = True
        else:
            if recipe.mapped_recipe.output_checksum is None:
                raise Exception("Input checksum to mapped recipe {} is None".format(recipe.name))
            if not is_foreach_clean(recipe, recipe.mapped_recipe.output_checksum):
                mapped_dirty = True

    if recipe.transient or recipe.output_checksum is None:
        return add_node_and_dependencies_to_graph(graph, recipe, Status.NotEvaluatedYet)

    if ingredient_dirty:
        return add_node_and_dependencies_to_graph(graph, recipe, Status.IngredientDirty)

    if mapped_dirty:
        return add_node_and_dependencies_to_graph(graph, recipe, Status.MappedInputsDirty)

    status = is_clean(recipe, ingredient_output_checksums_tuple)
    return add_node_and_dependencies_to_graph(graph, recipe, status)


def compute_recipe_status(recipe: Recipe[R]) -> Dict[Recipe, Status]:
    """
    Compute the Status for the provided recipe and all dependencies (ingredients or mapped inputs)

    :param recipe: The recipe for which status should be computed
    :return: The status of the provided recipe and all dependencies as a dictionary
    """
    # Create graph and extract status map from it
    graph = create_graph(recipe)
    status: Dict[Recipe, Status] = nx.get_node_attributes(graph, "status")
    return status


def evaluate_recipe(recipe: Recipe[R], graph: nx.DiGraph) -> OutputsAndChecksums[R]:
    log.debug('Evaluating recipe: {}'.format(recipe.name))

    def topological_sort_grouping(g):
        # copy the graph
        _g = g.copy()
        res = []
        # while _g is not empty
        while _g:
            zero_indegree = [v for v, d in _g.in_degree() if d == 0]
            res.append(zero_indegree)
            _g.remove_nodes_from(zero_indegree)
        return res

    # Sort the graph into steps where each element (recipe) is independent, such that each task in a step can be
    # evaluated in parallel, and such that any recipe in step N only depends on recipes in steps < N
    # This guarantees that the 'outputs' and 'output_checksum' attributes will be available for all dependencies of a
    # recipe once we arrive at it in the order of iteration
    steps = list(topological_sort_grouping(graph))
    statuses = nx.get_node_attributes(graph, "status")

    for step in steps:
        for recipe in step:
            # If status is Ok, the recipe has already been evaluated, so we can just move on to the next recipe
            if statuses[recipe] == Status.Ok:
                continue

            # Collect inputs and checksums
            inputs = tuple(recipe.outputs for recipe in recipe.ingredients)
            input_checksums = tuple(recipe.output_checksum for recipe in recipe.ingredients)

            if isinstance(recipe, ForeachRecipe):
                # Collect mapped inputs and checksum of these
                mapped_inputs = recipe.mapped_recipe.outputs
                mapped_inputs_checksum = recipe.mapped_recipe.output_checksum

                # Mapped inputs can either be a list or a dictionary
                if not isinstance(mapped_inputs, list) and not isinstance(mapped_inputs, dict):
                    raise Exception("Input to mapped recipe {} must be a list or a dict".format(recipe.name))

                recipe.invoke_mapped(mapped_inputs, mapped_inputs_checksum, inputs, input_checksums)
            else:
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


def is_foreach_clean(recipe: ForeachRecipe[R], mapped_inputs_checksum: Optional[str]) -> bool:
    """
    Check whether a ForeachRecipe is clean (in addition to the regular recipe cleanliness checks). This is done by
    comparing the overall checksum for the current mapped inputs to that from the last invoke evaluation

    :param recipe: The ForeachRecipe to check cleanliness of mapped inputs for
    :param mapped_inputs_checksum: A single checksum for all the mapped inputs, used to quickly check
        whether anything has changed
    :return: Whether the input recipe needs to be reevaluated
    """
    return recipe.mapped_inputs_checksum == mapped_inputs_checksum


def brew(recipe: Recipe[R]) -> R:
    """
    Evaluate a Recipe and all dependent inputs - this will build the computational graph and execute any needed
    dependencies to produce the outputs of the input Recipe

    :param recipe: The Recipe to evaluate
    :return: The outputs of the Recipe (which correspond to the outputs of the bound function)
    """
    result, _ = evaluate_recipe(recipe, create_graph(recipe))
    return result
