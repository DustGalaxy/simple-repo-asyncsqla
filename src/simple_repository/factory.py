from typing import Type, cast

from .abctract import IAsyncCrud
from .exceptions import DiffAtrrsOnCreateCrud
from .utils import same_attrs
from .implementation import AsyncCrud
from ._types import DM, SA


def crud_factory(sqla_model: Type[SA], domain_model: Type[DM]) -> Type[IAsyncCrud[SA, DM]]:
    """Creates a type-safe CRUD repository for the given models."""
    if not same_attrs(sqla_model, domain_model):
        raise DiffAtrrsOnCreateCrud(
            f"Attribute mismatch between SQLAlchemy model '{sqla_model.__name__}' "
            f"and Domain model '{domain_model.__name__}'.\n\n"
            "Both models must define the same set of attributes for the repository to function correctly.\n"
            f"Please ensure that '{sqla_model.__name__}' and '{domain_model.__name__}' have identical attribute names.\n\n"
            "Example of matching attributes:\n"
            "SQLAlchemy Model:\n"
            "class MySqlaModel(Base):\n"
            "    id: Mapped[int]\n"
            "    name: Mapped[str]\n\n"
            "Domain Model:\n"
            "@dataclass\n"
            "class MyDomainModel:\n"
            "    id: int\n"
            "    name: str\n"
            "    # Ensure model_dump and model_validate are implemented as required by DomainModel protocol."
        )

    new_class_name = f"{sqla_model.__name__}Repository"

    new_cls = type(
        new_class_name,
        (AsyncCrud,),
        {
            "sqla_model": sqla_model,
            "domain_model": domain_model,
        },
    )
    return cast(Type[IAsyncCrud[SA, DM]], new_cls)
