"""Named errors of the domain."""


class DomainError(Exception):
    """Base class for every error the domain raises."""


class InvalidDesign(DomainError):
    """The design file is not a well-formed description of a landing zone."""


class InvalidPolicy(DomainError):
    """A policy entry is incomplete or contradicts its own kind."""


class InvalidRequest(DomainError):
    """A request or scenario cannot be understood."""
