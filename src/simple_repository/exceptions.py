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
    """Exception raised when sqla and domain models don`t have same attrs"""

    pass
