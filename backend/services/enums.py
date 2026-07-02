from enum import Enum


class EventType(str, Enum):
    """访客事件类型枚举 — 替代 event_type 裸字符串。

    使用 str 继承确保序列化到数据库时自动转为字符串，
    无需修改 Stats 模型字段类型。
    """
    VISIT = "visit"
    CHAT = "chat"
    DOWNLOAD = "download"
    PREVIEW = "preview"
    PORTFOLIO = "portfolio"
