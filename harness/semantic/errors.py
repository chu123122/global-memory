"""Shared semantic retrieval error types."""
from __future__ import annotations


class SemanticError(RuntimeError):
    """Error with a stable machine-readable error code."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code

    def to_dict(self) -> dict[str, str]:
        return {"errorCode": self.error_code, "message": str(self)}
