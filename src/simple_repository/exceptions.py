class RepositoryException(Exception):
    """Base exception for repository operations"""

    pass


class IntegrityConflictException(RepositoryException):
    """Exception raised when integrity constraints are violated"""

    pass


class NotFoundException(RepositoryException):
    """Exception raised when entity is not found"""

    pass


class DiffAtrrsOnCreateCrud(RepositoryException):
    def __str__(self) -> str:
        return """'sqla_model' and 'domain_model' must have same attrs
                                  
Example, same attrs names:
class MyBelovedSqlaModel:
    __tablename__ = "tablename"

    meme: Mapped[str] # attr 1
                                  
@dataclass
class MyBelovedDomainModel:
    meme: str # attr 2

    def model_dump(self) -> dict[str, Any]:
        return {"meme": self.meme}

    @classmethod
    def model_validate(cls, sqla_model: SqlaModel) -> Self:
        return cls(meme=sqla_model.meme)                            
"""
