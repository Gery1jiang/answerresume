from abc import ABC, abstractmethod


class FileService(ABC):
    """文件处理服务：上传、解析、查找。"""

    @abstractmethod
    def parse_document(self, file_path: str) -> str:
        """使用 Docling 解析文件内容，返回纯文本/Markdown。"""
        ...

    @abstractmethod
    def resolve_file(self, file_ref: str, user_id: str) -> str:
        """根据 file_ref（UUID 文件名）查找文件完整路径。
        只搜索用户自己的目录，不跨用户 fallback。"""
        ...

    @abstractmethod
    def save_upload(self, user_id: str, filename: str, content: bytes) -> dict:
        """保存上传文件到用户隔离目录。
        返回 {"file_id": str, "file_name": str, "file_type": str, "file_size": int}"""
        ...
