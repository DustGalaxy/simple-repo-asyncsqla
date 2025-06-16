# Type alias for better readability
from typing import Type, cast

from .exceptions import DiffAtrrsOnCreateCrud
from .utils import same_attrs
from .repository import AsyncCrud, CrudMeta
from .types import DM, SA


CRUDRepository = Type[AsyncCrud[SA, DM]]


def crud_factory(sqla_model: Type[SA], domain_model: Type[DM]) -> CRUDRepository:
    """Creates a type-safe CRUD repository for the given models."""
    if not same_attrs(sqla_model, domain_model):
        raise DiffAtrrsOnCreateCrud()

    new_class_name = f"{sqla_model.__name__}Repository"

    new_cls = CrudMeta(
        new_class_name,
        (AsyncCrud,),
        {
            "sqla_model": sqla_model,
            "domain_model": domain_model,
        },
    )
    return cast(CRUDRepository, new_cls)
