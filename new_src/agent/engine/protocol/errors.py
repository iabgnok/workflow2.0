class ProtocolError(Exception):
    """Base error for protocol-layer failures."""


class ProtocolSchemaError(ProtocolError):
    """Raised when parsed workflow cannot satisfy schema contract."""


class ProtocolGatekeeperError(ProtocolError):
    """Raised when gatekeeper hard rules reject the workflow."""


class ProtocolDryRunError(ProtocolError):
    """Raised when dry-run contract checks fail."""


class ProtocolRuntimeValidationError(ProtocolError):
    """Raised when runtime step input/output assertions fail."""
