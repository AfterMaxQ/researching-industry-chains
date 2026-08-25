"""客户端错误类型。"""


class ClientError(Exception):
    """携带稳定错误代码和可选明细的客户端错误。"""

    def __init__(
        self, code: str, message: str, details: dict | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict:
        """返回适合命令行 JSON 输出的错误对象。"""
        error = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return error
