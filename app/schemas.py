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


# ===================== JOGO (missões) =====================
Sessao = Field(min_length=8, max_length=64)


class SessaoIn(BaseModel):
    sessao: str = Sessao


class RespostaEtapaIn(BaseModel):
    sessao: str = Sessao
    escolha: int = Field(ge=0)


class TrilhaOut(BaseModel):
    id: int
    publico: Publico
    titulo: str
    descricao: str
    total_missoes: int
    concluidas: int


class MissaoOut(BaseModel):
    id: int
    trilha_id: int
    titulo: str
    tema: str | None
    tipo: str
    ordem: int
    total_etapas: int
    pct_minimo: float
    xp_recompensa: int
    insignia: str | None
    status: Literal["bloqueada", "disponivel", "em_andamento", "concluida", "falhou"]
    melhor_pct: float | None = None


class EtapaOut(BaseModel):
    """Questão da etapa atual, SEM gabarito."""
    missao_id: int
    etapa: int  # 1-based
    total_etapas: int
    contexto: str
    questao_id: int
    tema: str
    enunciado: str
    opcoes: list[str]


class InicioMissaoOut(BaseModel):
    missao_id: int
    titulo: str
    narrativa_inicio: str
    etapa: EtapaOut


class ResultadoMissao(BaseModel):
    status: Literal["concluida", "falhou"]
    acertos: int
    total_etapas: int
    pct: float
    pct_minimo: float
    xp_conclusao: int
    insignia_nova: str | None = None
    narrativa_fim: str | None = None
    proxima_missao_id: int | None = None


class RespostaEtapaOut(BaseModel):
    acertou: bool
    correta: int
    explicacao: str
    xp_ganho: int
    xp_total: int
    nivel: int
    subiu_nivel: bool
    proxima_etapa: EtapaOut | None = None
    resultado: ResultadoMissao | None = None


class JogadorOut(BaseModel):
    sessao: str
    xp_total: int
    nivel: int
    xp_proximo_nivel: int
    sequencia_dias: int
    insignias: list[str]
    missoes_concluidas: int
