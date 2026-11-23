from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Declaration:
    """A Lean declaration extracted at source level (heuristic)."""

    name: str
    kind: str
    file: str
    line: int
    source: str
    dependencies: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["dependencies"] = list(self.dependencies)
        return result
