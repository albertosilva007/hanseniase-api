from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Questao(Base):
    __tablename__ = "questoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    publico: Mapped[str] = mapped_column(String(10), index=True)  # "prof" | "pac"
    tema: Mapped[str] = mapped_column(String(80), index=True)
    enunciado: Mapped[str] = mapped_column(Text)
    opcoes: Mapped[list] = mapped_column(JSON)
    correta: Mapped[int] = mapped_column(Integer)
    explicacao: Mapped[str] = mapped_column(Text, default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)

    respostas: Mapped[list["Resposta"]] = relationship(
        back_populates="questao", cascade="all, delete-orphan", passive_deletes=True
    )


class Resposta(Base):
    __tablename__ = "respostas"
    id: Mapped[int] = mapped_column(primary_key=True)
    questao_id: Mapped[int] = mapped_column(ForeignKey("questoes.id", ondelete="CASCADE"), index=True)
    escolha: Mapped[int] = mapped_column(Integer)
    acertou: Mapped[bool] = mapped_column(Boolean, index=True)
    sessao: Mapped[str] = mapped_column(String(64), index=True)  # id anônimo gerado no navegador
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)

    questao: Mapped[Questao] = relationship(back_populates="respostas")
