#!/usr/bin/env python
import threading
import time
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
        time.sleep(0.01)
        called = time.perf_counter()
        return called, thread_idx

    @alk.recipe()
    def b() -> Tuple[float, int]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing b on {thread_idx}")
        time.sleep(0.01)
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
    assert results_a[0] != pytest.approx(results_b[0])
    assert results_a != pytest.approx(results_ab[0])

    # 'a' and 'b' should have executed on the same thread
    assert results_a[1] == results_b[1]


@pytest.mark.parametrize("jobs", (0, 3, 5, 8, -1))
def test_parallel_threading(jobs: int) -> None:
    """
    Test that recipes can execute in parallel
    """
    AlkymiConfig.get().cache = False

    @alk.recipe()
    def a() -> Tuple[float, int]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing a on {thread_idx}")
        time.sleep(0.01)
        called = time.perf_counter()
        return called, thread_idx

    @alk.recipe()
    def b() -> Tuple[float, int]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing b on {thread_idx}")
        time.sleep(0.01)
        called = time.perf_counter()
        return called, thread_idx

    @alk.recipe()
    def ab(a, b) -> Tuple[Tuple[float, int], ...]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        print(f"Executing ab on {thread_idx}")
        called = time.perf_counter()
        return a, b, (called, thread_idx)

    # 'a' and 'b' should have executed in parallel
    results_a, results_b, results_ab = ab.brew(jobs=jobs)
    assert results_a[0] == pytest.approx(results_b[0])
    assert results_a != pytest.approx(results_ab[0])

    # 'a' and 'b' should have executed on different threads
    assert results_a[1] != results_b[1]
