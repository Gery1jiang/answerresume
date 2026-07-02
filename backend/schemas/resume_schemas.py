from pydantic import BaseModel
from typing import Optional

class ResumeGenerateRequest(BaseModel):
    raw_text: str
    target_job: Optional[str] = ""
    user_id: str = ""

class PDFExportRequest(BaseModel):
    html: str
    css: Optional[str] = ""
