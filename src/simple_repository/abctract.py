from abc import ABC, ABCMeta, abstractmethod
from typing import Any, Generic, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ._types import SA, DM, FilterValue, Filters, IdValue
from .protocols import Schema


# --- Метакласс для защиты атрибутов класса ---
class FrozenClassAttributesMeta(ABCMeta):
    """
    Metaclass that prevents reassigning
    'sqla_model' and 'domain_model' attributes after they are first set.
    """

    def __setattr__(cls, name: str, value: Any) -> None:
        """
        Intercepts attempts to set attributes on the class.
        If 'sqla_model' or 'domain_model' already exist,
        raises AttributeError to prevent changing them.
        """
        if name in ("sqla_model", "domain_model"):
            if hasattr(cls, name):
                raise AttributeError(
                    f"Cannot reassign immutable class attribute '{name}' on class '{cls.__name__}'. "
                    "These attributes are set by crud_factory and should not be changed."
                )
        super().__setattr__(name, value)


# --- Интерфейс базового репозитория ---
class IAsyncCrud(ABC, Generic[SA, DM]):
    """
    Abstract base class that defines the interface for async CRUD operations.
    Parameterized by SQLAlchemy model (SA) and domain model (DM).
    """

    @abstractmethod
    async def get_one(
        self,
        session: AsyncSession,
        id_: IdValue,
        column: str = "id",
    ) -> DM:
        """
        Asynchronously get a domain model by its ID.
        """
        pass

    @abstractmethod
    async def get_many(
        self,
        session: AsyncSession,
        filter: FilterValue,
        column: str = "id",
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> list[DM]:
        """
        Asynchronously get a list of domain models by a list of IDs.
        """
        pass

    @abstractmethod
    async def get_all(
        self,
        session: AsyncSession,
        offset: int = 0,
        limit: Optional[int] = 100,
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> tuple[list[DM], int]:
        """
        Asynchronously get a paginated list of domain models.
        """
        pass

    @abstractmethod
    async def create(
        self,
        session: AsyncSession,
        data: DM,
    ) -> DM:
        """
        Asynchronously create a new record in the database from a domain model.
        """
        pass

    @abstractmethod
    async def create_many(
        self,
        session: AsyncSession,
        data: list[DM],
        return_models: bool = False,
    ) -> list[DM] | bool:
        """
        Asynchronously create multiple records in the database from domain models.
        """
        pass

    @abstractmethod
    async def update(
        self,
        session: AsyncSession,
        data: DM,
    ) -> DM:
        """
        Asynchronously update an existing record in the database by its ID.
        """
        pass

    @abstractmethod
    async def patch(
        self,
        session: AsyncSession,
        data: Schema,
        id_: IdValue,
        column: str = "id",
    ) -> DM:
        """
        Asynchronously partially update an existing record in the database by its ID.
        """
        pass

    @abstractmethod
    async def remove(
        self,
        session: AsyncSession,
        id_: IdValue,
        column: str = "id",
        raise_not_found: bool = False,
    ) -> int:
        """
        Asynchronously delete a record from the database by its ID.
        """
        pass

    @abstractmethod
    async def remove_many(
        self,
        session: AsyncSession,
        ids: list[IdValue],
        column: str = "id",
    ) -> int:
        """
        Asynchronously delete multiple records from the database by a list of IDs.
        """
        pass

    @abstractmethod
    async def count(
        self,
        session: AsyncSession,
        filters: Optional[Filters] = None,
    ) -> int:
        """
        Asynchronously count the number of records in the database.
        """
        pass
