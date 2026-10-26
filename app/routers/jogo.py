"""Endpoints do modo jogo (missões). O jogador é a `sessao` anônima do navegador."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (InsigniaJogador, Jogador, Missao, MissaoEtapa, ProgressoMissao, Questao,
                      Resposta, Trilha, agora)
from ..schemas import (EtapaOut, InicioMissaoOut, JogadorOut, MissaoOut, Publico, RespostaEtapaIn,
                       RespostaEtapaOut, ResultadoMissao, SessaoIn, TrilhaOut)

router = APIRouter(prefix="/api/jogo", tags=["jogo"])

XP_POR_NIVEL = 200
FUSO_RECIFE = timezone(timedelta(hours=-3))  # sem horário de verão


# ---------------- auxiliares ----------------
def _nivel(xp: int) -> int:
    return 1 + xp // XP_POR_NIVEL


def _jogador(db: Session, sessao: str, criar: bool = True) -> Jogador | None:
    j = db.scalar(select(Jogador).where(Jogador.sessao == sessao))
    if not j and criar:
        j = Jogador(sessao=sessao)
        db.add(j)
        db.flush()
    return j


def _atualiza_sequencia(j: Jogador) -> None:
    hoje = datetime.now(FUSO_RECIFE).date()
    if j.ultimo_dia == hoje:
        return
    j.sequencia_dias = (j.sequencia_dias or 0) + 1 if j.ultimo_dia == hoje - timedelta(days=1) else 1
    j.ultimo_dia = hoje


def _etapas_ativas(db: Session, missao_id: int) -> list[MissaoEtapa]:
    """Etapas cuja questão está ativa (questão desativada no admin some da missão)."""
    return list(db.scalars(
        select(MissaoEtapa).join(Questao).where(MissaoEtapa.missao_id == missao_id, Questao.ativo.is_(True))
        .order_by(MissaoEtapa.ordem)
    ))


def _missao(db: Session, mid: int) -> Missao:
    m = db.get(Missao, mid)
    if not m or not m.ativo:
        raise HTTPException(404, "Missão não encontrada")
    return m


def _progressos(db: Session, jogador: Jogador | None) -> dict[int, ProgressoMissao]:
    if not jogador:
        return {}
    return {p.missao_id: p for p in db.scalars(select(ProgressoMissao).where(ProgressoMissao.jogador_id == jogador.id))}


def _desbloqueada(m: Missao, progs: dict[int, ProgressoMissao]) -> bool:
    if not m.pre_requisito_id:
        return True
    p = progs.get(m.pre_requisito_id)
    return bool(p and p.ja_concluiu)


def _status(m: Missao, progs: dict[int, ProgressoMissao]) -> str:
    p = progs.get(m.id)
    if p:
        if p.status == "em_andamento":
            return "em_andamento"
        return "concluida" if p.ja_concluiu else "falhou"
    return "disponivel" if _desbloqueada(m, progs) else "bloqueada"


def _etapa_out(m: Missao, etapas: list[MissaoEtapa], idx: int) -> EtapaOut:
    e = etapas[idx]
    q = e.questao
    return EtapaOut(missao_id=m.id, etapa=idx + 1, total_etapas=len(etapas), contexto=e.contexto,
                    questao_id=q.id, tema=q.tema, enunciado=q.enunciado, opcoes=q.opcoes)


def _progresso_ativo(db: Session, m: Missao, sessao: str) -> tuple[Jogador, ProgressoMissao]:
    j = _jogador(db, sessao, criar=False)
    p = j and db.scalar(select(ProgressoMissao).where(ProgressoMissao.jogador_id == j.id,
                                                      ProgressoMissao.missao_id == m.id))
    if not p or p.status != "em_andamento":
        raise HTTPException(409, "Missão não iniciada. Chame /iniciar primeiro.")
    return j, p


# ---------------- trilhas e missões ----------------
@router.get("/trilhas", response_model=list[TrilhaOut])
def listar_trilhas(publico: Publico | None = None, sessao: str | None = Query(None, max_length=64),
                   db: Session = Depends(get_db)):
    st = select(Trilha).where(Trilha.ativo.is_(True)).order_by(Trilha.ordem)
    if publico:
        st = st.where(Trilha.publico == publico)
    progs = _progressos(db, _jogador(db, sessao, criar=False) if sessao else None)
    out = []
    for t in db.scalars(st):
        ms = [m for m in t.missoes if m.ativo]
        out.append(TrilhaOut(id=t.id, publico=t.publico, titulo=t.titulo, descricao=t.descricao,
                             total_missoes=len(ms),
                             concluidas=sum(1 for m in ms if progs.get(m.id) and progs[m.id].ja_concluiu)))
    return out


@router.get("/trilhas/{tid}/missoes", response_model=list[MissaoOut])
def listar_missoes(tid: int, sessao: str | None = Query(None, max_length=64), db: Session = Depends(get_db)):
    t = db.get(Trilha, tid)
    if not t or not t.ativo:
        raise HTTPException(404, "Trilha não encontrada")
    progs = _progressos(db, _jogador(db, sessao, criar=False) if sessao else None)
    out = []
    for m in t.missoes:
        if not m.ativo:
            continue
        p = progs.get(m.id)
        out.append(MissaoOut(id=m.id, trilha_id=t.id, titulo=m.titulo, tema=m.tema, tipo=m.tipo, ordem=m.ordem,
                             total_etapas=len(_etapas_ativas(db, m.id)), pct_minimo=m.pct_minimo,
                             xp_recompensa=m.xp_recompensa, insignia=m.insignia,
                             status=_status(m, progs), melhor_pct=p.melhor_pct if p else None))
    return out


# ---------------- jogando ----------------
@router.post("/missoes/{mid}/iniciar", response_model=InicioMissaoOut)
def iniciar(mid: int, dados: SessaoIn, db: Session = Depends(get_db)):
    m = _missao(db, mid)
    j = _jogador(db, dados.sessao)
    progs = _progressos(db, j)
    if not _desbloqueada(m, progs):
        raise HTTPException(403, "Missão bloqueada: conclua a missão anterior primeiro.")
    etapas = _etapas_ativas(db, m.id)
    if not etapas:
        raise HTTPException(409, "Esta missão está sem questões ativas.")

    p = progs.get(m.id)
    if not p:
        p = ProgressoMissao(jogador_id=j.id, missao_id=m.id)
        db.add(p)
    # (re)começa do zero: vale para 1ª vez, para quem falhou e para quem quer rejogar
    p.status, p.etapa_atual, p.acertos = "em_andamento", 0, 0
    p.tentativas = (p.tentativas or 0) + 1
    p.iniciada_em, p.concluida_em = agora(), None
    db.commit()
    return InicioMissaoOut(missao_id=m.id, titulo=m.titulo, narrativa_inicio=m.narrativa_inicio,
                           etapa=_etapa_out(m, etapas, 0))


@router.get("/missoes/{mid}/etapa", response_model=EtapaOut)
def etapa_atual(mid: int, sessao: str = Query(min_length=8, max_length=64), db: Session = Depends(get_db)):
    m = _missao(db, mid)
    _, p = _progresso_ativo(db, m, sessao)
    etapas = _etapas_ativas(db, m.id)
    return _etapa_out(m, etapas, min(p.etapa_atual, len(etapas) - 1))


@router.post("/missoes/{mid}/responder", response_model=RespostaEtapaOut)
def responder(mid: int, dados: RespostaEtapaIn, db: Session = Depends(get_db)):
    m = _missao(db, mid)
    j, p = _progresso_ativo(db, m, dados.sessao)
    etapas = _etapas_ativas(db, m.id)
    idx = min(p.etapa_atual, len(etapas) - 1)
    e = etapas[idx]
    q = e.questao
    if dados.escolha >= len(q.opcoes):
        raise HTTPException(422, "Opção inexistente para esta questão")

    acertou = dados.escolha == q.correta
    # grava também na tabela de respostas: o /dashboard e o CSV continuam enxergando tudo
    db.add(Resposta(questao_id=q.id, escolha=dados.escolha, acertou=acertou, sessao=dados.sessao))

    nivel_antes = j.nivel
    rejogando = p.ja_concluiu  # quem já concluiu pode treinar de novo, mas sem farmar XP
    xp = e.xp_acerto if (acertou and not rejogando) else 0
    if acertou:
        p.acertos += 1
    p.etapa_atual = idx + 1
    _atualiza_sequencia(j)

    resultado = proxima = None
    if p.etapa_atual >= len(etapas):  # última etapa: fecha a missão
        pct = round(p.acertos / len(etapas), 4)
        p.melhor_pct = max(p.melhor_pct or 0, pct)
        venceu = pct >= m.pct_minimo
        xp_conc, insignia_nova, prox_id = 0, None, None
        if venceu:
            p.status = "concluida"
            p.concluida_em = agora()
            if not p.ja_concluiu:
                xp_conc = m.xp_recompensa
                if m.insignia and not db.get(InsigniaJogador, (j.id, m.insignia)):
                    db.add(InsigniaJogador(jogador_id=j.id, insignia=m.insignia))
                    insignia_nova = m.insignia
            p.ja_concluiu = True
            prox = db.scalar(select(Missao).where(Missao.pre_requisito_id == m.id, Missao.ativo.is_(True)))
            prox_id = prox.id if prox else None
        else:
            p.status = "falhou"
        xp += xp_conc
        resultado = ResultadoMissao(status=p.status, acertos=p.acertos, total_etapas=len(etapas), pct=pct,
                                    pct_minimo=m.pct_minimo, xp_conclusao=xp_conc, insignia_nova=insignia_nova,
                                    narrativa_fim=m.narrativa_fim if venceu else None,
                                    proxima_missao_id=prox_id)
    else:
        proxima = _etapa_out(m, etapas, p.etapa_atual)

    j.xp_total += xp
    j.nivel = _nivel(j.xp_total)
    db.commit()
    return RespostaEtapaOut(acertou=acertou, correta=q.correta, explicacao=q.explicacao, xp_ganho=xp,
                            xp_total=j.xp_total, nivel=j.nivel, subiu_nivel=j.nivel > nivel_antes,
                            proxima_etapa=proxima, resultado=resultado)


# ---------------- perfil ----------------
@router.get("/jogador/{sessao}", response_model=JogadorOut)
def perfil(sessao: str, db: Session = Depends(get_db)):
    if not 8 <= len(sessao) <= 64:
        raise HTTPException(422, "Sessão inválida")
    j = _jogador(db, sessao, criar=False)
    if not j:  # jogador novo: perfil zerado, sem gravar nada
        return JogadorOut(sessao=sessao, xp_total=0, nivel=1, xp_proximo_nivel=XP_POR_NIVEL,
                          sequencia_dias=0, insignias=[], missoes_concluidas=0)
    insignias = list(db.scalars(select(InsigniaJogador.insignia).where(InsigniaJogador.jogador_id == j.id)
                                .order_by(InsigniaJogador.obtida_em)))
    concluidas = db.scalar(select(func.count(ProgressoMissao.id)).where(
        ProgressoMissao.jogador_id == j.id, ProgressoMissao.ja_concluiu.is_(True))) or 0
    return JogadorOut(sessao=j.sessao, xp_total=j.xp_total, nivel=j.nivel,
                      xp_proximo_nivel=j.nivel * XP_POR_NIVEL - j.xp_total,
                      sequencia_dias=j.sequencia_dias, insignias=insignias, missoes_concluidas=concluidas)
