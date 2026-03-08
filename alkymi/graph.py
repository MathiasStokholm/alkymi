from collections import deque
from typing import Deque, Dict, Generic, Iterator, Set, TypeVar

N = TypeVar("N")


class Graph(Generic[N]):
    """
    A directed acyclic graph (DAG) used to represent recipe dependencies in alkymi.

    Each node represents a Recipe, and each directed edge from node A to node B indicates that
    recipe A is an ingredient (dependency) of recipe B. The graph is always directed, acyclic,
    and contains no parallel edges.
    """

    def __init__(self) -> None:
        self._nodes: Set[N] = set()
        # Adjacency is stored as insertion-ordered dicts (used as ordered sets) to ensure that
        # predecessors() and successors() return neighbours in the order edges were added.
        # This is critical for correctness: _compute_status iterates predecessors to build
        # ingredient_output_checksums, which must match the order in which invoke/invoke_foreach
        # stores _input_checksums (i.e. recipe.ingredients order).
        self._successors: Dict[N, Dict[N, None]] = {}
        self._predecessors: Dict[N, Dict[N, None]] = {}

    def add_node(self, node: N) -> None:
        """Add a node to the graph."""
        if node not in self._nodes:
            self._nodes.add(node)
            self._successors[node] = {}
            self._predecessors[node] = {}

    def add_edge(self, from_node: N, to_node: N) -> None:
        """Add a directed edge from from_node to to_node, adding the nodes if not already present."""
        self.add_node(from_node)
        self.add_node(to_node)
        self._successors[from_node][to_node] = None
        self._predecessors[to_node][from_node] = None

    def predecessors(self, node: N) -> Iterator[N]:
        """Return an iterator over predecessor nodes in edge-insertion order."""
        return iter(self._predecessors.get(node, {}).keys())

    def successors(self, node: N) -> Iterator[N]:
        """Return an iterator over successor nodes in edge-insertion order."""
        return iter(self._successors.get(node, {}).keys())

    def has_node(self, node: N) -> bool:
        """Return True if the node is in the graph."""
        return node in self._nodes

    def __contains__(self, node: object) -> bool:
        """Return True if the node is in the graph."""
        return node in self._nodes

    def has_successor(self, node: N, successor: N) -> bool:
        """Return True if there is a directed edge from node to successor."""
        return successor in self._successors.get(node, {})

    @property
    def nodes(self) -> Set[N]:
        """Return the set of all nodes in the graph."""
        return self._nodes


def topological_sort(graph: Graph[N]) -> Iterator[N]:
    """
    Perform a topological sort of the given directed acyclic graph using Kahn's algorithm.
    Returns nodes in an order where each node appears only after all its predecessors.

    :param graph: The directed acyclic graph to sort
    :return: An iterator of nodes in topological order
    :raises ValueError: If the graph contains a cycle
    """
    in_degree: Dict[N, int] = {node: 0 for node in graph.nodes}
    for node in graph.nodes:
        for successor in graph.successors(node):
            in_degree[successor] += 1

    queue: Deque[N] = deque(node for node, degree in in_degree.items() if degree == 0)
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for successor in graph.successors(node):
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)

    if len(result) != len(graph.nodes):
        raise ValueError("Graph contains a cycle")

    return iter(result)
