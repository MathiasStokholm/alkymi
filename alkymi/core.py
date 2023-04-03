import asyncio
import concurrent.futures
import typing
from asyncio import Future, AbstractEventLoop, Task
from typing import Dict, Tuple, Optional, Any, Coroutine, Union

import networkx as nx

from . import checksums
from .config import ProgressType, AlkymiConfig
from .foreach_recipe import ForeachRecipe, MappedOutputs, MappedInputs
from .logging import log
from .progress import FancyProgress
from .recipe import Recipe, R
from .serialization import OutputWithValue
from .types import Status, ProgressCallback, EvaluateProgress

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


async def invoke(recipe: Recipe, inputs: Tuple[Any, ...], input_checksums: Tuple[Optional[str], ...],
                 loop: AbstractEventLoop, executor: Optional[concurrent.futures.Executor],
                 progress_callback: Optional[ProgressCallback] = None) -> OutputsAndChecksums:
    """
    Evaluate the Recipe using the provided inputs. This will call the bound function on the inputs.

    :param recipe: The recipe to evaluate given the provided inputs
    :param inputs: The inputs provided by the ingredients (dependencies) of the Recipe
    :param input_checksums: The (possibly new) input checksum
    :param loop: The asyncio event loop to use for scheduling the recipe evaluation
    :param executor: An optional executor to use for evaluating bound functions in parallel
    :param progress_callback: An optional callback to invoke when evaluation progress occurs
    :return: The output(s) and checksum(s) of the evaluated recipe
    """
    log.debug('Invoking recipe: {}'.format(recipe.name))

    # Signal that work has started on 1 out of 1 unit of work
    if progress_callback is not None:
        progress_callback(EvaluateProgress.Started, recipe, 1, 1)

    # Run code on executor if applicable, otherwise evaluate directly on this thread
    if executor is not None:
        outputs = await loop.run_in_executor(executor, recipe, *inputs)
    else:
        outputs = recipe(*inputs)
    recipe.set_result(outputs, input_checksums)

    # Signal that work has completed on 1 out of 1 unit of work
    if progress_callback is not None:
        progress_callback(EvaluateProgress.Done, recipe, 1, 1)

    return recipe.outputs, recipe.output_checksum


async def invoke_foreach(recipe: ForeachRecipe, inputs: Tuple[Any, ...],
                         input_checksums: Tuple[Optional[str], ...],
                         loop: AbstractEventLoop,
                         executor: Optional[concurrent.futures.Executor],
                         progress_callback: Optional[ProgressCallback] = None) -> OutputsAndChecksums:
    """
    Evaluate the ForeachRecipe using the provided inputs. This will apply the bound function to each item in the
    "mapped_inputs". If the result for any item is already cached, that result will be used instead (the checksum
    is used to check this). Only items from the immediately previous invoke call will be cached

    :param recipe: The ForeachRecipe to evaluate given the provided inputs
    :param inputs: The inputs provided by the ingredients (dependencies) of the ForeachRecipe
    :param input_checksums: The (possibly new) input checksum to use for checking cleanliness
    :param loop: The asyncio event loop to use for scheduling the recipe evaluation
    :param executor: An optional executor to use for evaluating bound functions in parallel
    :param progress_callback: An optional callback to invoke when evaluation progress occurs
    :return: The output(s) and checksum(s) of the evaluated recipe
    """
    log.debug("Invoking recipe: {}".format(recipe.name))

    # The first ingredient will provide the sequence to apply the bound function too
    mapped_inputs = inputs[0]
    mapped_inputs_checksum = input_checksums[0]
    other_inputs = inputs[1:]
    other_input_checksums = input_checksums[1:]

    if not (isinstance(mapped_inputs, list) or isinstance(mapped_inputs, dict)):
        raise RuntimeError("Cannot handle type in invoke(): {}".format(type(mapped_inputs)))

    mapped_inputs_of_same_type = recipe.mapped_inputs_type == type(mapped_inputs)

    # Check if a full reevaluation across all mapped inputs is needed
    needs_full_eval = recipe.transient or not mapped_inputs_of_same_type

    # Check if bound function has changed - this should cause a full reevaluation
    if not needs_full_eval:
        if recipe.function_hash != recipe.last_function_hash:
            needs_full_eval = True

    # Check if we actually need to do any work (in case everything remains the same as last invocation)
    if not needs_full_eval and recipe.input_checksums is not None:
        if recipe.input_checksums == input_checksums:
            # Outputs have to be valid for us to return them
            if recipe.outputs_valid:
                log.debug("Returning early since mapped inputs did not change since last evaluation")
                return recipe.outputs, recipe.output_checksum
        # If input checksums do not match, a full re-evaluation is needed if the mapped checksums match, since the
        # mismatch has to be caused by a non-mapped input
        elif mapped_inputs_checksum == recipe.mapped_inputs_checksum:
            needs_full_eval = True

    # Catch up on already done work
    # TODO(mathias): Refactor this insanity to avoid the list/dict type checking
    outputs: MappedOutputs = [] if isinstance(mapped_inputs, list) else {}
    evaluated: MappedInputs = [] if isinstance(mapped_inputs, list) else {}
    not_evaluated: MappedInputs = [] if isinstance(mapped_inputs, list) else {}
    if needs_full_eval or recipe.mapped_outputs is None:
        not_evaluated = mapped_inputs
    else:
        if isinstance(mapped_inputs, list) and isinstance(outputs, list) \
                and isinstance(evaluated, list) and isinstance(not_evaluated, list):
            for item in mapped_inputs:
                # Try to look up cached result for this input
                try:
                    new_checksum = checksums.checksum(item)
                    idx = recipe.mapped_inputs_checksums.index(new_checksum)  # type: ignore
                    found_checksum = recipe.mapped_inputs_checksums[idx]  # type: ignore
                    if new_checksum == found_checksum:
                        found_output = recipe.mapped_outputs[idx]
                        if found_output.valid:
                            outputs.append(found_output)
                            evaluated.append(item)
                            continue
                except ValueError:
                    pass
                not_evaluated.append(item)
        elif isinstance(mapped_inputs, dict):
            for key, item in mapped_inputs.items():
                # Try to look up cached result for this input
                found_checksum = recipe.mapped_inputs_checksums.get(key, None)  # type: ignore
                if found_checksum is not None:
                    new_checksum = checksums.checksum(key)
                    if new_checksum == found_checksum:
                        found_output = recipe.mapped_outputs[key]
                        if found_output.valid:
                            outputs[key] = found_output
                            evaluated[key] = item
                            continue
                not_evaluated[key] = item

    # Signal that work has started on X out of Y units of work
    if progress_callback is not None:
        progress_callback(EvaluateProgress.Started, recipe, len(mapped_inputs), len(evaluated))

    log.debug("Num already cached results: {}/{}".format(len(evaluated), len(mapped_inputs)))
    if len(evaluated) == len(mapped_inputs):
        log.debug("Returning early since all items were already cached")
        recipe.set_current_result(evaluated, outputs, mapped_inputs_checksum, other_input_checksums, True)
        return recipe.outputs, recipe.output_checksum

    # Perform remaining work - store state every time an evaluation is successful
    results: typing.Iterable[Any]
    if isinstance(not_evaluated, list) and isinstance(outputs, list) and isinstance(evaluated, list):
        if executor is not None:
            results = [loop.run_in_executor(executor, recipe.__call__, _item, *other_inputs) for _item in
                       not_evaluated]
        else:
            results = map(lambda _item: recipe(_item, *other_inputs), not_evaluated)
        for item, maybe_async_result in zip(not_evaluated, results):
            result = await maybe_async_result if isinstance(maybe_async_result, Future) else maybe_async_result
            outputs.append(OutputWithValue(result, checksums.checksum(result)))
            evaluated.append(item)
            recipe.set_current_result(evaluated, outputs, mapped_inputs_checksum, other_input_checksums, False)

            # Signal that work has completed on X out of Y units of work
            if progress_callback is not None:
                progress_callback(EvaluateProgress.InProgress, recipe, len(mapped_inputs), len(evaluated))
    elif isinstance(not_evaluated, dict):
        if executor is not None:
            results = [loop.run_in_executor(executor, recipe.__call__, _item, *other_inputs) for _item in
                       not_evaluated.values()]
        else:
            results = map(lambda _item: recipe(_item, *other_inputs), not_evaluated.values())
        for (key, item), maybe_async_result in zip(not_evaluated.items(), results):
            result = await maybe_async_result if isinstance(maybe_async_result, Future) else maybe_async_result
            outputs[key] = OutputWithValue(result, checksums.checksum(result))
            evaluated[key] = item
            recipe.set_current_result(evaluated, outputs, mapped_inputs_checksum, other_input_checksums, False)

            # Signal that work has completed on X out of Y units of work
            if progress_callback is not None:
                progress_callback(EvaluateProgress.InProgress, recipe, len(mapped_inputs), len(evaluated))

    recipe.set_current_result(evaluated, outputs, mapped_inputs_checksum, other_input_checksums, True)

    # Signal that work has completed on N out of N units of work
    if progress_callback is not None:
        progress_callback(EvaluateProgress.Done, recipe, len(mapped_inputs), len(evaluated))

    return recipe.outputs, recipe.output_checksum


async def schedule(loop: AbstractEventLoop, executor: Optional[concurrent.futures.Executor], recipe: Recipe,
                   status: Status, coros_or_tasks: Dict[Recipe, Union[Coroutine, Task]],
                   progress_callback: Optional[ProgressCallback] = None) -> OutputsAndChecksums:
    """
    Helper function used to asynchronously await inputs from dependant recipes, and then retrieve the output of the
    provided recipe (evaluating it if necessary). Note that inputs will only be awaited if needed (not if cached).

    :param loop: The asyncio event loop to use for scheduling the recipe evaluation
    :param executor: An optional executor to use for evaluating bound functions in parallel
    :param recipe: The recipe to evaluate using the executor
    :param status: The status of the recipe being scheduled - used to skip evaluation if unnecessary
    :param coros_or_tasks: Dictionary containing coroutines for recipes - used to await ingredient inputs
    :param progress_callback: An optional callback to invoke when evaluation progress occurs
    :return: A future that will eventually return the output(s) and checksum(s) of the recipe
    """

    # If status is Ok, simply return the result and checksum
    if status == Status.Ok:
        return recipe.outputs, recipe.output_checksum

    # Status is not Ok - evaluation needed
    # Convert needed inputs from coroutines to tasks - this is done to ensure that multiple recipes can await the result
    input_futures = []
    for ingredient in recipe.ingredients:
        coro_or_task = coros_or_tasks[ingredient]
        if not isinstance(coro_or_task, asyncio.Task):
            coro_or_task = loop.create_task(coro_or_task)
            coros_or_tasks[ingredient] = coro_or_task
        input_futures.append(coro_or_task)

    # Block while waiting for inputs to become available
    inputs_and_checksums = tuple(await asyncio.gather(*input_futures))
    inputs = tuple(inp[0] for inp in inputs_and_checksums)
    input_checksums = tuple(inp[1] for inp in inputs_and_checksums)
    if isinstance(recipe, ForeachRecipe):
        return await invoke_foreach(recipe, inputs, input_checksums, loop, executor, progress_callback)
    else:
        return await invoke(recipe, inputs, input_checksums, loop, executor, progress_callback)


def evaluate_recipe(recipe: Recipe[R], graph: nx.DiGraph, statuses: Dict[Recipe, Status], jobs: int,
                    progress_type: Optional[ProgressType] = None) -> OutputsAndChecksums[R]:
    """
    Evaluate a Recipe, including any dependencies that are not up-to-date

    :param recipe: The recipe to evaluate
    :param graph: The graph to use for evaluation
    :param statuses: The statuses of the recipes contained in the graph - used to skip evaluation if unnecessary
    :param jobs: The number of jobs to use for evaluating the recipe in parallel, 1 job corresponds to no parallelism,
                 zero or negative values will cause alkymi to use the system's default number of jobs
    :param progress_type: The method to use for showing progress, if None will default to setting in alkymi's config
    :return: The output(s) and checksum(s) of the evaluated recipe
    """
    # Create the executor to use for evaluating bound functions
    executor: Optional[concurrent.futures.Executor]
    if jobs == 1:
        executor = None
    else:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=jobs if jobs > 0 else None)

    # Determine the progress type to use - if not provided by caller, use current setting in alkymi's global config
    if progress_type is None:
        progress_type = AlkymiConfig.get().progress_type
    progress = FancyProgress(graph, statuses, recipe) if progress_type == ProgressType.Fancy else None

    # Create the asyncio event loop and set it on the calling thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _execute() -> OutputsAndChecksums[R]:
        # Sort the graph topographically, such that any recipe in the sorted list only depends on earlier recipes
        # This guarantees that futures only depend on already created futures
        recipes = list(nx.topological_sort(graph))

        # Create coroutines to evaluate each recipe - then from the top-down, the coroutines will request inputs that
        # they need from other coroutines, which will be upgraded to tasks
        # This approach is used to avoid loading outputs for recipes whose outputs are actually unused, because later
        # recipes are already cached
        coros_or_tasks: Dict[Recipe, Union[Coroutine, Task]] = {}
        for _recipe in recipes:
            # Note that 'schedule()' might mutate 'tasks' once awaited
            coros_or_tasks[_recipe] = schedule(loop, executor, _recipe, statuses[_recipe], coros_or_tasks,
                                               progress)

        # Wait for future for target recipe to return
        result = await coros_or_tasks[recipe]

        # Close coroutines that were not converted to tasks, since they were never needed for the execution
        for coro_or_task in coros_or_tasks.values():
            if not isinstance(coro_or_task, asyncio.Task):
                coro_or_task.close()

        return result

    # Return the output and checksum of the final recipe
    if progress is not None:
        progress.start()
    output, checksum = loop.run_until_complete(_execute())
    if progress is not None:
        progress.stop()
    return output, checksum


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


def brew(recipe: Recipe[R], *, jobs: int, progress_type: Optional[ProgressType]) -> R:
    """
    Evaluate a Recipe and all dependent inputs - this will build the computational graph and execute any needed
    dependencies to produce the outputs of the input Recipe

    :param recipe: The Recipe to evaluate
    :param jobs: The number of jobs to use for evaluating the recipe in parallel, 1 job corresponds to no parallelism,
                 zero or negative values will cause alkymi to use the system's default number of jobs
    :param progress_type: The method to use for showing progress, if None will default to setting in alkymi's config
    :return: The outputs of the Recipe (which correspond to the outputs of the bound function)
    """
    graph = create_graph(recipe)
    statuses = compute_recipe_status(recipe, graph)
    result, _ = evaluate_recipe(recipe, graph, statuses, jobs, progress_type)
    return result
