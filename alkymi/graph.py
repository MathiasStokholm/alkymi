from collections import deque
from typing import Any, Deque, Dict, Generic, Iterator, Set, TypeVar

N = TypeVar("N")


class Graph(Generic[N]):
    """
    A directed acyclic graph (DAG) used to represent recipe dependencies in alkymi.

    Each node represents a Recipe, and each directed edge from node A to node B indicates that
    recipe A is an ingredient (dependency) of recipe B. The graph is always directed, acyclic,
    and contains no parallel edges.
    """

    def __init__(self) -> None:
        self._nodes: Set[Any] = set()
        self._successors: Dict[Any, Set[Any]] = {}
        self._predecessors: Dict[Any, Set[Any]] = {}

    def add_node(self, node: Any) -> None:
        """Add a node to the graph."""
        if node not in self._nodes:
            self._nodes.add(node)
            self._successors[node] = set()
            self._predecessors[node] = set()

    def add_edge(self, from_node: Any, to_node: Any) -> None:
        """Add a directed edge from from_node to to_node, adding the nodes if not already present."""
        self.add_node(from_node)
        self.add_node(to_node)
        self._successors[from_node].add(to_node)
        self._predecessors[to_node].add(from_node)

    def predecessors(self, node: Any) -> Iterator[Any]:
        """Return an iterator over predecessor nodes (nodes with edges pointing to the given node)."""
        return iter(self._predecessors.get(node, set()))

    def successors(self, node: Any) -> Iterator[Any]:
        """Return an iterator over successor nodes (nodes that the given node has edges pointing to)."""
        return iter(self._successors.get(node, set()))

    def has_node(self, node: Any) -> bool:
        """Return True if the node is in the graph."""
        return node in self._nodes

    def __contains__(self, node: Any) -> bool:
        """Return True if the node is in the graph."""
        return node in self._nodes

    def has_successor(self, node: Any, successor: Any) -> bool:
        """Return True if there is a directed edge from node to successor."""
        return successor in self._successors.get(node, set())

    @staticmethod
    def is_directed() -> bool:
        """Return True since this is always a directed graph."""
        return True

    @staticmethod
    def is_multigraph() -> bool:
        """Return False since parallel edges are not supported."""
        return False

    @property
    def nodes(self) -> Set[Any]:
        """Return the set of all nodes in the graph."""
        return self._nodes


def topological_sort(graph: Graph) -> Iterator[Any]:
    """
    Perform a topological sort of the given directed acyclic graph using Kahn's algorithm.
    Returns nodes in an order where each node appears only after all its predecessors.

    :param graph: The directed acyclic graph to sort
    :return: An iterator of nodes in topological order
    :raises ValueError: If the graph contains a cycle
    """
    in_degree = {node: 0 for node in graph.nodes}
    for node in graph.nodes:
        for successor in graph.successors(node):
            in_degree[successor] += 1

    queue: Deque[Any] = deque(node for node, degree in in_degree.items() if degree == 0)
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
