"""Index métrique compact (BK-Tree) pour la recherche de distances de Hamming."""

from __future__ import annotations

from dataclasses import dataclass, field

from .visual import hamming_distance


@dataclass
class _Node:
    value: int
    indexes: list[int] = field(default_factory=list)
    children: dict[int, "_Node"] = field(default_factory=dict)


class HammingIndex:
    """Arbre BK spécialisé pour la recherche efficace par distance de Hamming."""

    def __init__(self):
        self.root: _Node | None = None

    def add(self, value: int, index: int) -> None:
        if self.root is None:
            self.root = _Node(value, [index])
            return
        node = self.root
        while True:
            distance = hamming_distance(value, node.value)
            if distance == 0:
                node.indexes.append(index)
                return
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = _Node(value, [index])
                return
            node = child

    def neighbors(self, value: int, maximum_distance: int) -> list[int]:
        if self.root is None:
            return []
        matches: list[int] = []
        pending = [self.root]
        while pending:
            node = pending.pop()
            distance = hamming_distance(value, node.value)
            if distance <= maximum_distance:
                matches.extend(node.indexes)
            minimum = max(0, distance - maximum_distance)
            maximum = distance + maximum_distance
            pending.extend(
                child
                for edge, child in node.children.items()
                if minimum <= edge <= maximum
            )
        return matches
