from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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


# =====================================================================
# JOGO: trilhas → missões → etapas (cada etapa aponta para uma questão)
# O jogador é anônimo: identificado pela mesma `sessao` usada em /respostas.
# =====================================================================
class Trilha(Base):
    __tablename__ = "trilhas"
    id: Mapped[int] = mapped_column(primary_key=True)
    publico: Mapped[str] = mapped_column(String(10), index=True)  # "prof" | "pac"
    titulo: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str] = mapped_column(Text, default="")
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    missoes: Mapped[list["Missao"]] = relationship(
        back_populates="trilha", cascade="all, delete-orphan", order_by="Missao.ordem"
    )


class Missao(Base):
    __tablename__ = "missoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    trilha_id: Mapped[int] = mapped_column(ForeignKey("trilhas.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str] = mapped_column(String(120))
    tema: Mapped[str | None] = mapped_column(String(80), nullable=True)  # None no "chefe" (mistura temas)
    tipo: Mapped[str] = mapped_column(String(20), default="quiz")  # quiz | chefe | caso_clinico | diaria
    narrativa_inicio: Mapped[str] = mapped_column(Text, default="")
    narrativa_fim: Mapped[str] = mapped_column(Text, default="")
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    pre_requisito_id: Mapped[int | None] = mapped_column(ForeignKey("missoes.id", ondelete="SET NULL"), nullable=True)
    pct_minimo: Mapped[float] = mapped_column(default=0.7)
    xp_recompensa: Mapped[int] = mapped_column(Integer, default=50)
    insignia: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    trilha: Mapped[Trilha] = relationship(back_populates="missoes")
    etapas: Mapped[list["MissaoEtapa"]] = relationship(
        back_populates="missao", cascade="all, delete-orphan", order_by="MissaoEtapa.ordem"
    )


class MissaoEtapa(Base):
    __tablename__ = "missao_etapas"
    __table_args__ = (UniqueConstraint("missao_id", "ordem"), UniqueConstraint("missao_id", "questao_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    missao_id: Mapped[int] = mapped_column(ForeignKey("missoes.id", ondelete="CASCADE"), index=True)
    questao_id: Mapped[int] = mapped_column(ForeignKey("questoes.id", ondelete="CASCADE"), index=True)
    ordem: Mapped[int] = mapped_column(Integer)
    contexto: Mapped[str] = mapped_column(Text, default="")  # fala/trecho narrativo antes da pergunta
    xp_acerto: Mapped[int] = mapped_column(Integer, default=10)

    missao: Mapped[Missao] = relationship(back_populates="etapas")
    questao: Mapped[Questao] = relationship()


class Jogador(Base):
    __tablename__ = "jogadores"
    id: Mapped[int] = mapped_column(primary_key=True)
    sessao: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    nivel: Mapped[int] = mapped_column(Integer, default=1)
    sequencia_dias: Mapped[int] = mapped_column(Integer, default=0)
    ultimo_dia: Mapped[date | None] = mapped_column(Date, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class ProgressoMissao(Base):
    __tablename__ = "progresso_missoes"
    __table_args__ = (UniqueConstraint("jogador_id", "missao_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    jogador_id: Mapped[int] = mapped_column(ForeignKey("jogadores.id", ondelete="CASCADE"), index=True)
    missao_id: Mapped[int] = mapped_column(ForeignKey("missoes.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(15), default="em_andamento")  # em_andamento | concluida | falhou
    etapa_atual: Mapped[int] = mapped_column(Integer, default=0)  # índice 0-based nas etapas ativas
    acertos: Mapped[int] = mapped_column(Integer, default=0)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    melhor_pct: Mapped[float | None] = mapped_column(nullable=True)
    ja_concluiu: Mapped[bool] = mapped_column(Boolean, default=False)  # XP de conclusão só na 1ª vez
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InsigniaJogador(Base):
    __tablename__ = "insignias_jogador"
    jogador_id: Mapped[int] = mapped_column(ForeignKey("jogadores.id", ondelete="CASCADE"), primary_key=True)
    insignia: Mapped[str] = mapped_column(String(80), primary_key=True)
    obtida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
