import asyncio
import concurrent.futures
from typing import Dict, Tuple, Optional, cast, Awaitable

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
    """
    Compute the status for the provided recipe (and recursively for dependencies) and add them all to the provided
    'statuses' dict

    :param recipe: The recipe to compute the status for
    :param graph: The graph to use for establishing statuses
    :param statuses: A dictionary used to collect the results of the recursive call
    :return status: The status of this recipe
    """

    def _store_and_return(_status: Status) -> Status:
        """
        Helper function to store a result in the 'statuses' dict before returning it
        """
        statuses[recipe] = _status
        return _status

    # Determine statuses of dependencies - note that this recursively computes statuses for dependencies and adds them
    # to 'statuses', so this needs to be called before any return
    dependencies = tuple(graph.predecessors(recipe))
    ingredient_statuses = tuple(
        _compute_status(ingredient, graph, statuses)
        for ingredient in dependencies
    )

    # If output checksum is None (or transient), a full re-evaluation is needed
    if recipe.transient or recipe.output_checksum is None:
        return _store_and_return(Status.NotEvaluatedYet)

    # Check if one or more ingredients (dependencies) are dirty
    if any(status != Status.Ok for status in ingredient_statuses):
        return _store_and_return(Status.IngredientDirty)

    # Check if one or more ingredients (dependencies) are dirty
    ingredient_output_checksums: Tuple[Optional[str], ...] = tuple(
        ingredient.output_checksum
        for ingredient in dependencies
        if ingredient.output_checksum is not None
    )
    status = is_clean(recipe, ingredient_output_checksums)
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


def retrieve_recipe_outputs(recipe: Recipe, status: Status, inputs_and_checksums: Tuple[OutputsAndChecksums] = ()):
    # If status is not Ok, call invoke to run recipe
    if status != Status.Ok:
        _inputs = tuple(inp[0] for inp in inputs_and_checksums)
        _input_checksums = tuple(inp[1] for inp in inputs_and_checksums)
        recipe.invoke(_inputs, _input_checksums)
    return recipe.outputs, recipe.output_checksum


def evaluate_recipe(recipe: Recipe[R], graph: nx.DiGraph, statuses: Dict[Recipe, Status]) -> OutputsAndChecksums[R]:
    """
    Evaluate a Recipe, including any dependencies that are not up-to-date

    :param recipe: The recipe to evaluate
    :param graph: The graph to use for evaluation
    :param statuses: The statuses of the recipes contained in the graph - used to skip evaluation if unnecessary
    :return: The output(s) and checksum(s) of the evaluated recipe
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
    loop = asyncio.get_event_loop()

    async def _schedule(_recipe: Recipe, inputs_and_checksum_futures: Tuple[Awaitable[OutputsAndChecksums], ...]):
        inputs_and_checksums = tuple([await inp for inp in inputs_and_checksum_futures])
        return loop.run_in_executor(executor, retrieve_recipe_outputs, _recipe, statuses[_recipe], inputs_and_checksums)

    async def _execute() -> Awaitable[OutputsAndChecksums]:
        # Sort the graph topographically, such that any recipe in the sorted list only depends on earlier recipes
        # This guarantees that futures only depend on already created futures
        recipes = list(nx.topological_sort(graph))

        tasks = {}
        for _recipe in recipes:
            input_futures = tuple(tasks[ingredient] for ingredient in _recipe.ingredients)
            tasks[_recipe] = await _schedule(_recipe, input_futures)

        # Wait for future for target recipe to return
        return await tasks[recipe]

    # Return the output and checksum of the final recipe
    output, checksum = loop.run_until_complete(_execute())
    return cast(R, output), checksum


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
