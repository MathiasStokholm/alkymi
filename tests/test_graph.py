#!/usr/bin/env python
import threading
import time
from pathlib import Path
from typing import List, Tuple

import pytest

import alkymi as alk
from alkymi import AlkymiConfig


def test_create_graph() -> None:
    """
    Test that a Directed Acyclic Graph (DAG) is correctly created from a set of recipes with dependencies on each other
    """
    AlkymiConfig.get().cache = False

    @alk.recipe()
    def unused() -> None:
        return None

    @alk.recipe()
    def a() -> str:
        return "a"

    @alk.recipe()
    def b() -> str:
        return "b"

    @alk.recipe()
    def c() -> str:
        return "c"

    @alk.recipe()
    def depends_a(a: str) -> List[str]:
        return [a, a, a, a]

    @alk.foreach(depends_a)
    def foreach_a(a: str) -> str:
        return a + "_"

    @alk.recipe()
    def depends_ab(a: str, b: str) -> str:
        return a + b

    @alk.recipe()
    def root(foreach_a: List[str], depends_ab: str, c: str) -> str:
        return "".join(foreach_a) + depends_ab + c

    # Create a graph from the 'root' recipe (this will automatically traverse the dependencies)
    graph = alk.core.create_graph(root)

    # Graph should be directed and not a multi-graph (no parallel edges)
    assert graph.is_directed()
    assert not graph.is_multigraph()

    # Graph should have one node for each recipe
    assert len(graph.nodes) == len([a, b, c, depends_a, foreach_a, depends_ab, root])

    # The unused recipe should not be in the graph
    assert not graph.has_node(unused)

    # The graph should have the following edges (dependencies)
    assert graph.has_successor(a, depends_a)
    assert graph.has_successor(a, depends_ab)
    assert graph.has_successor(b, depends_ab)
    assert graph.has_successor(depends_a, foreach_a)
    assert graph.has_successor(foreach_a, root)
    assert graph.has_successor(depends_ab, root)
    assert graph.has_successor(c, root)


def test_sequential() -> None:
    """
    Test that recipes can execute sequentially (without parallelism)
    """
    AlkymiConfig.get().cache = False

    @alk.recipe()
    def a() -> Tuple[float, int]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing a on {thread_idx}")
        time.sleep(0.02)
        called = time.perf_counter()
        return called, thread_idx

    @alk.recipe()
    def b() -> Tuple[float, int]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing b on {thread_idx}")
        time.sleep(0.02)
        called = time.perf_counter()
        return called, thread_idx

    @alk.recipe()
    def ab(a, b) -> Tuple[Tuple[float, int], ...]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing ab on {thread_idx}")
        called = time.perf_counter()
        return a, b, (called, thread_idx)

    # 'a' and 'b' should not have executed in parallel
    results_a, results_b, results_ab = ab.brew(jobs=1)
    assert results_a[0] != pytest.approx(results_b[0], abs=0.01)
    assert results_a != pytest.approx(results_ab[0])

    # 'a', 'b' and 'ab' should have executed on the current (main) thread
    main_thread_idx = threading.current_thread().ident
    assert main_thread_idx is not None
    assert results_a[1] == main_thread_idx
    assert results_b[1] == main_thread_idx
    assert results_ab[1] == main_thread_idx


# Barrier used by test_parallel_threading - has to be global to avoid being captured in checksum (cannot be pickled)
barrier = threading.Barrier(parties=2, timeout=1)


@pytest.mark.parametrize("jobs", (0, 2, 5, 8, -1))
def test_parallel_threading(jobs: int) -> None:
    """
    Test that recipes can execute in parallel by waiting on a barrier with N=2 from two recipes - the waits will time
    out if less than two threads wait on the barrier in parallel
    """
    AlkymiConfig.get().cache = False
    barrier.reset()

    @alk.recipe()
    def a() -> int:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing a on {thread_idx}")
        barrier.wait()
        return thread_idx

    @alk.recipe()
    def b() -> int:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing b on {thread_idx}")
        barrier.wait()
        return thread_idx

    @alk.recipe()
    def ab(a: int, b: int) -> Tuple[int, ...]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing ab on {thread_idx}")
        return a, b, thread_idx

    # 'a' and 'b' should have executed in parallel
    try:
        thread_idx_a, thread_idx_b, _ = ab.brew(jobs=jobs)
        # 'a' and 'b' should have executed on different threads
        assert thread_idx_a != thread_idx_b
    except threading.BrokenBarrierError:
        pytest.fail("a and b did not execute in parallel")


# Barrier used by test_parallel_foreach - has to be global to avoid being captured in checksum (cannot be pickled)
foreach_barrier = threading.Barrier(parties=10, timeout=1)


def test_parallel_foreach() -> None:
    """
    Test that execution of ForeachRecipe happens correctly in parallel by requiring N threads to block on the barrier
    from the bound function
    """
    jobs = foreach_barrier.parties
    AlkymiConfig.get().cache = False
    foreach_barrier.reset()

    # Run a number of jobs in parallel that matches the barrier wait count
    input_ids = alk.recipes.arg(list(range(0, jobs)), name="input_ids")

    @alk.foreach(input_ids)
    def synchronize(input_id: int) -> Tuple[int, int]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        foreach_barrier.wait()
        return input_id, thread_idx

    try:
        # Gather results
        id_to_thread_map = {
            result[0]: result[1]  # type: ignore
            for result in synchronize.brew(jobs=jobs)
        }

        # Check that all calls happened on unique threads
        assert len(id_to_thread_map.values()) == len(set(id_to_thread_map.values()))

        # Check that all IDs were processed in the correct order
        assert list(id_to_thread_map.keys()) == input_ids.brew()
    except threading.BrokenBarrierError:
        pytest.fail("ForeachRecipe did not execute bound functions in parallel")


@pytest.mark.parametrize("jobs", (1, 3))
def test_lazy_loading(tmp_path: Path, jobs: int) -> None:
    """
    Test that alkymi will only load cached results when needed to provide the requested up-to-date output
    """
    AlkymiConfig.get().cache = True
    AlkymiConfig.get().cache_path = tmp_path

    def a_value() -> bytes:
        return "cached string".encode()

    def capitalized_value(a_value: bytes) -> str:
        return a_value.decode().upper()

    # Create recipes and evaluate
    a_value_recipe_1 = alk.recipe()(a_value)
    capitalized_value_recipe_1 = alk.recipe((a_value_recipe_1,))(capitalized_value)
    assert capitalized_value_recipe_1.brew(jobs=jobs) == "CACHED STRING"
    maybe_cached_value_1 = getattr(getattr(a_value_recipe_1, "_outputs"), "_value")
    assert maybe_cached_value_1 is not None, "Outputs from 'a_value' should not be None after execution"

    # Recreate recipes to force cache load and evaluate
    a_value_recipe_2 = alk.recipe()(a_value)
    capitalized_value_recipe_2 = alk.recipe((a_value_recipe_2,))(capitalized_value)
    assert capitalized_value_recipe_2.brew(jobs=jobs) == "CACHED STRING"

    # The outputs should not have been loaded, since 'capitalized_value' was already cached
    maybe_cached_value_2 = getattr(getattr(a_value_recipe_2, "_outputs"), "_value")
    assert maybe_cached_value_2 is None, "Outputs from 'a_value' should not have been loaded unnecessarily"
