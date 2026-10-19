from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Publico = Literal["prof", "pac"]


class QuestaoBase(BaseModel):
    publico: Publico
    tema: str = Field(min_length=2, max_length=80)
    enunciado: str = Field(min_length=5)
    opcoes: list[str] = Field(min_length=2, max_length=6)
    correta: int = Field(ge=0)
    explicacao: str = ""
    ativo: bool = True

    @model_validator(mode="after")
    def _checa_correta(self):
        if self.correta >= len(self.opcoes):
            raise ValueError("'correta' precisa apontar para uma das opções")
        if any(not o.strip() for o in self.opcoes):
            raise ValueError("nenhuma opção pode ficar vazia")
        return self


class QuestaoCriar(QuestaoBase):
    pass


class QuestaoAtualizar(QuestaoBase):
    pass


class QuestaoAdmin(QuestaoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    criado_em: datetime
    atualizado_em: datetime


class QuestaoPublica(BaseModel):
    """Versão pública: o gabarito só vem quando pedido (modo leitura)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    publico: Publico
    tema: str
    enunciado: str
    opcoes: list[str]
    correta: int | None = None
    explicacao: str | None = None


class RespostaCriar(BaseModel):
    questao_id: int
    escolha: int = Field(ge=0)
    sessao: str = Field(min_length=8, max_length=64)


class Correcao(BaseModel):
    questao_id: int
    acertou: bool
    correta: int
    explicacao: str


class Login(BaseModel):
    email: str
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
