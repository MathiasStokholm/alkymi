#!/usr/bin/env python
import logging
from pathlib import Path
from typing import List, Tuple

from alkymi import AlkymiConfig
import alkymi as alk
from alkymi.core import Status
from alkymi.recipe import Recipe


def test_caching(caplog, tmpdir):
    """
    Test that a cache is created (in the set location), and that recipe can be restored correctly
    """
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache = True
    AlkymiConfig.get().cache_path = tmpdir

    # Manually wrap the function
    a_value = 42

    def should_cache() -> int:
        return a_value

    should_cache_recipe = alk.recipe()(should_cache)

    should_cache_recipe.brew()
    assert should_cache_recipe.status() == Status.Ok
    assert (tmpdir / Recipe.CACHE_DIRECTORY_NAME / "tests" / "should_cache").is_dir()

    # Create a "copy" to force reloading from cache
    should_cache_recipe_copy = alk.recipe()(should_cache)
    assert should_cache_recipe_copy.status() == Status.Ok

    # Try changing the bound function and seeing that we catch it
    a_value = 1337
    assert should_cache_recipe.status() == Status.BoundFunctionChanged
    assert should_cache_recipe_copy.status() == Status.BoundFunctionChanged
    should_cache_recipe_copy_2 = alk.recipe()(should_cache)
    assert should_cache_recipe_copy_2.status() == Status.BoundFunctionChanged


def test_caching_no_return_value(caplog, tmpdir):
    """
    Test that caching works even when the bound function doesn't return anything (None)
    """
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache = True
    AlkymiConfig.get().cache_path = tmpdir

    @alk.recipe()
    def no_return_value() -> None:
        some_state = "This is a debug statement from test_caching_no_return_value()"
        alk.log.debug(some_state)  # Simulate non-pure function

    assert no_return_value.status() == Status.NotEvaluatedYet
    no_return_value.brew()
    assert no_return_value.status() == Status.Ok
    assert (tmpdir / Recipe.CACHE_DIRECTORY_NAME / "tests" / "no_return_value").is_dir()


# We use these globals to avoid altering the hashes of bound functions when these change
execution_counts: List[int] = []
stopping_point: int = 0


def test_foreach_caching(caplog, tmpdir):
    """
    Test that ForeachRecipe is able to handle failures, reloading, etc.
    """
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = True
    AlkymiConfig.get().cache_path = tmpdir  # Use temporary directory for caching

    global execution_counts, stopping_point
    execution_counts = [0] * 5
    stopping_point = 2

    arg = alk.recipes.arg(list(range(len(execution_counts))), name="args")

    def _check_counts(expected_counts: Tuple[int, int, int, int, int]):
        for actual_count, expected_count in zip(execution_counts, expected_counts):
            assert actual_count == expected_count

    def record_execution(idx: int) -> int:
        if idx == stopping_point:
            raise InterruptedError("Simulated failure")
        execution_counts[idx] += 1
        return execution_counts[idx]

    record_execution_recipe = alk.foreach(arg)(record_execution)
    assert record_execution_recipe.status() == Status.NotEvaluatedYet

    # Initial brew should cause executions up until stopping point
    try:
        record_execution_recipe.brew()
    except InterruptedError:
        pass
    _check_counts((1, 1, 0, 0, 0))

    # At this point, the status should have changed to reflect the partial evaluation
    assert record_execution_recipe.status() == Status.MappedInputsDirty

    # Move interruption by one
    stopping_point += 1
    try:
        record_execution_recipe.brew()
    except InterruptedError:
        pass
    _check_counts((1, 1, 1, 0, 0))
    assert record_execution_recipe.status() == Status.MappedInputsDirty

    # Reloading the recipe from cache should result in the same partially evaluated state
    record_execution_recipe_copy = alk.foreach(arg)(record_execution)
    assert record_execution_recipe_copy.status() == Status.MappedInputsDirty

    # Move interruption by another index - only the single element should be evaluated now
    stopping_point += 1
    try:
        record_execution_recipe_copy.brew()
    except InterruptedError:
        pass
    _check_counts((1, 1, 1, 1, 0))
    assert record_execution_recipe_copy.status() == Status.MappedInputsDirty

    # Reload from cache and finish
    record_execution_recipe_copy_2 = alk.foreach(arg)(record_execution)
    assert record_execution_recipe_copy_2.status() == Status.MappedInputsDirty
    stopping_point = -1
    record_execution_recipe_copy_2.brew()
    _check_counts((1, 1, 1, 1, 1))
    assert record_execution_recipe_copy_2.status() == Status.Ok
