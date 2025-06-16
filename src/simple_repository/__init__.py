"""
Simple Repository AsyncSQLA
A lightweight and type-safe repository pattern implementation for SQLAlchemy async.
"""

from .factory import crud_factory

__all__ = [
    "crud_factory",
]

__version__ = "0.1.3"
