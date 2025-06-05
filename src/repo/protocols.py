from typing import Any, Protocol, Self


class SqlaModel(Protocol):
    __tablename__: str


class DomainModel(Protocol):
    @classmethod
    def model_validate(cls, obj: Any, *args, **kwagrs) -> Self: ...
    def model_dump(self, *args, **kwagrs) -> dict[str, Any]: ...
