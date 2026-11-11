"""Operational errors carry safe, stable codes rather than external payloads."""


class OperationalError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ConfigurationError(OperationalError):
    def __init__(self, setting: str):
        self.setting = setting
        super().__init__(f'Invalid or missing configuration: {setting}')
