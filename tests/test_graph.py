#!/usr/bin/env python

from typing import List
from alkymi import AlkymiConfig
import alkymi as alk


def test_graph_construction() -> None:
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

    # Evaluating the graph should result in the following output
    result, _ = alk.core.evaluate_recipe(root, graph)
    assert result == "a_a_a_a_abc"
