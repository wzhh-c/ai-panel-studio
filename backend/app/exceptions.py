"""Custom exceptions for the repository layer."""


class RepositoryError(Exception):
    """Base exception for repository-level errors."""


class DuplicateRecordError(RepositoryError):
    """Raised when a unique constraint or primary key conflict occurs."""


class ForeignKeyError(RepositoryError):
    """Raised when a foreign key constraint is violated."""


class RecordNotFoundError(RepositoryError):
    """Raised when a requested record does not exist."""
