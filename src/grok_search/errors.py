from __future__ import annotations


class AppError(Exception):
    code = "internal_error"
    exit_code = 1

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UsageAppError(AppError):
    code = "usage_error"
    exit_code = 2


class ConfigAppError(AppError):
    code = "config_error"
    exit_code = 3


class NotFoundAppError(AppError):
    code = "not_found"
    exit_code = 4


class NetworkAppError(AppError):
    code = "network_error"
    exit_code = 5


class UpstreamAppError(AppError):
    code = "upstream_error"
    exit_code = 6

