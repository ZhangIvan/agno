"""Custom exceptions for object storage operations."""


class OSSBaseException(Exception):
    """Base exception for all OSS errors."""

    pass


class OSSUploadError(OSSBaseException):
    """Raised when an upload operation fails."""

    pass


class OSSDeleteError(OSSBaseException):
    """Raised when a delete operation fails."""

    pass


class OSSConfigError(OSSBaseException):
    """Raised when the storage configuration is invalid."""

    pass
