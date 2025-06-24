from typing import Type, cast

from .exceptions import DiffAtrrsOnCreateCrud
from .utils import same_attrs
from .repository import AsyncCrud, CrudMeta
from .types import DM, SA


def crud_factory(sqla_model: Type[SA], domain_model: Type[DM]) -> Type[AsyncCrud[SA, DM]]:
    """Creates a type-safe CRUD repository for the given models."""
    if not same_attrs(sqla_model, domain_model):
        raise DiffAtrrsOnCreateCrud(f"""{sqla_model} and {domain_model} must have same attrs
                                  
Example, same attrs names:
class SqlaModel(Base):
    __tablename__ = "tablename" # ignore

    id: Mapped[int] # attr 1
    meme: Mapped[str] # attr 2
                                  
@dataclass
class DomainModel:
    id: int # attr 1
    meme: str # attr 2

    def model_dump(self, *, exclude_unset=False) -> dict[str, Any]:
        ...

    @classmethod
    def model_validate(cls, sqla_model: SqlaModel) -> Self:
        ...                           
""")

    new_class_name = f"{sqla_model.__name__}Repository"

    new_cls = CrudMeta(
        new_class_name,
        (AsyncCrud,),
        {
            "sqla_model": sqla_model,
            "domain_model": domain_model,
        },
    )
    return cast(Type[AsyncCrud[SA, DM]], new_cls)
