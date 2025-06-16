"""Type definitions for the repository pattern implementation."""

from typing import TypeVar, Union
from uuid import UUID

from .protocols import SqlaModel, DomainModel

# Type variables for SQLAlchemy and Domain models
SA = TypeVar("SA", bound=SqlaModel)
DM = TypeVar("DM", bound=DomainModel)

# Common types used in the repository
PrimitiveValue = Union[str, UUID, int, float, bool]
FilterValue = Union[PrimitiveValue, list[PrimitiveValue]]
IdValue = Union[str, UUID, int]
Filters = dict[str, str]


class CrudMeta(type):
    pass
