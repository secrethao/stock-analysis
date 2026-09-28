from dataclasses import dataclass, field


@dataclass
class ModelResult:
    name: str
    applicable: bool
    price: float | None
    assumptions: dict = field(default_factory=dict)
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "applicable": self.applicable,
            "price": self.price,
            "assumptions": self.assumptions,
            "reason": self.reason,
        }
