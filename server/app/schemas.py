from __future__ import annotations

from typing import Optional, List, Union
from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    nome: str
    role: str
    is_default: bool


class UserCreate(BaseModel):
    nome: str
    role: str = "collab"
    is_default: bool = False
    senha: str = ""


class UserRoleUpdate(BaseModel):
    role: str


class UserLogin(BaseModel):
    nome: str
    senha: str



class AuthLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class CompanyOut(BaseModel):
    id: int
    nome: str
    cnpj: str = ""
    ie: str = ""
    regime: str = ""
    observacoes: List[str] = []
    data_entrada: Optional[str] = None
    data_saida: Optional[str] = None
    responsavel_id: Optional[int] = None
    email_principal: str = ""
    emails_extra: List[str] = []


class CompanyCreate(BaseModel):
    user_id: int
    nome: str
    cnpj: str = ""
    ie: str = ""
    regime: str = ""
    observacoes: Union[List[str], str] = ""
    data_entrada: Optional[str] = None
    data_saida: Optional[str] = None
    responsavel_id: Optional[int] = None
    email_principal: str = ""
    emails_extra: Union[List[str], str] = ""


class CompanyUpdate(BaseModel):
    nome: str
    cnpj: str = ""
    ie: str = ""
    regime: str = ""
    observacoes: Union[List[str], str] = ""
    data_entrada: Optional[str] = None
    data_saida: Optional[str] = None
    responsavel_id: Optional[int] = None
    email_principal: str = ""
    emails_extra: Union[List[str], str] = ""


class TaskOut(BaseModel):
    id: int
    company_id: int
    titulo: str
    tipo: str
    orgao: str
    tributo: str = ""
    competencia: Optional[str] = None
    vencimento: Optional[str] = None
    status: str
    pdf_path: Optional[str] = None
    has_pdf: bool = False


class TaskCreate(BaseModel):
    user_id: int
    company_id: int
    titulo: str
    tipo: str
    orgao: str
    tributo: str = ""
    competencia: Optional[str] = None
    vencimento: Optional[str] = None
    status: str


class TaskStatusUpdate(BaseModel):
    status: str


class TaskUpdate(BaseModel):
    titulo: str
    tipo: str
    orgao: str
    tributo: str = ""
    competencia: Optional[str] = None
    vencimento: Optional[str] = None
    status: str


class TaskLogOut(BaseModel):
    id: int
    task_id: int
    user_id: Optional[int] = None
    action: str
    details: Optional[str] = None
    created_at: str


class TaskCommentOut(BaseModel):
    id: int
    task_id: int
    author_id: int
    text: str
    created_at: str


class TaskCommentCreate(BaseModel):
    text: str


class NotificationOut(BaseModel):
    id: int
    user_id: int
    type: str
    ref_id: Optional[int] = None
    message: str
    is_read: bool
    created_at: str


class EmailSendPayload(BaseModel):
    company_id: int
    user_id: int
    subject: str = ""
    body: str = ""
    link: str = ""
    task_id: Optional[int] = None


class EmailLogOut(BaseModel):
    id: int
    company_id: int
    user_id: int
    to_emails: List[str]
    subject: str = ""
    body: str = ""
    link: str = ""
    task_id: Optional[int] = None
    attachment_name: Optional[str] = None
    created_at: str


class ServerSettingsOut(BaseModel):
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    server_name: str = "41 Fiscal Hub API"
    environment: str = "local"


class ServerSettingsUpdate(BaseModel):
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    server_name: str = "41 Fiscal Hub API"
    environment: str = "local"


class EmailSettingsOut(BaseModel):
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_sender: str = ""
    smtp_tls: bool = True


class EmailSettingsUpdate(BaseModel):
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_sender: str = ""
    smtp_tls: bool = True

