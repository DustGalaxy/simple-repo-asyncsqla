"""
Simple Repository AsyncSQLA
A lightweight and type-safe repository pattern implementation for SQLAlchemy async.
"""

from .factory import crud_factory
from .utils import BaseDomainModel, BaseSchema

__all__ = [
    "crud_factory",
    "BaseDomainModel",
    "BaseSchema",
]

__version__ = "1.0.0"
