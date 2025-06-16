"""
Simple Repository AsyncSQLA
A lightweight and type-safe repository pattern implementation for SQLAlchemy async.
"""

from .repository import crud_factory, AsyncCrud, CRUDRepository
from .protocols import SqlaModel, DomainModel
from .exceptions import (
    RepositoryException,
    NotFoundException,
    IntegrityConflictException,
    DiffAtrrsOnCreateCrud,
)
from .types import SA, DM, PrimitiveValue, FilterValue, Filters, IdValue

__all__ = [
    "crud_factory",
    "AsyncCrud",
    "CRUDRepository",
    "SqlaModel",
    "DomainModel",
    "RepositoryException",
    "NotFoundException",
    "IntegrityConflictException",
    "DiffAtrrsOnCreateCrud",
    "SA",
    "DM",
    "PrimitiveValue",
    "FilterValue",
    "IdValue",
    "Filters",
]

__version__ = "0.1.3"
