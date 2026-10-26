"""Converte o banco de questões em trilhas de missões.

Regra:
- 1 trilha por público ("prof" e "pac").
- Dentro da trilha, 1 missão por tema, na ordem pedagógica de ORDEM_TEMAS
  (temas novos entram no fim, em ordem alfabética).
- Tema com mais de TAM_MAX questões é quebrado em partes ("Parte 1", "Parte 2"...).
- Cada missão só desbloqueia quando a anterior é concluída (pre_requisito_id).
- No fim da trilha há um "Desafio final" (tipo chefe) com 1 questão de cada tema,
  exigindo 80% de acerto.

Os textos de narrativa são placeholders: a equipe revisa e edita depois.
"""
from collections import defaultdict

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import Missao, MissaoEtapa, ProgressoMissao, Questao, Trilha

TAM_MAX = 4
PCT_MISSAO = 0.7
PCT_CHEFE = 0.8
XP_MISSAO = 50
XP_CHEFE = 150
XP_ACERTO = 10

TRILHAS = {
    "prof": ("Jornada do Profissional", "Do bacilo à vigilância: domine o cuidado da hanseníase na atenção primária."),
    "pac": ("Jornada do Paciente", "Entenda a hanseníase, o tratamento e como cuidar de si no dia a dia."),
}

ORDEM_TEMAS = {
    "prof": ["Etiologia e transmissão", "Diagnóstico", "Classificação", "Tratamento",
             "Reações hansênicas", "Incapacidades", "Vigilância"],
    "pac": ["Transmissão", "Sinais e sintomas", "Tratamento", "Autocuidado", "Convivência"],
}


def _ordena_temas(publico: str, temas: list[str]) -> list[str]:
    base = ORDEM_TEMAS.get(publico, [])
    conhecidos = [t for t in base if t in temas]
    novos = sorted(t for t in temas if t not in base)
    return conhecidos + novos


def gera_missoes(db: Session, recriar: bool = False) -> dict:
    """Gera as trilhas a partir das questões ativas. Sem `recriar`, não mexe se já houver trilhas."""
    if db.scalar(select(func.count(Trilha.id))):
        if not recriar:
            return {"trilhas": 0, "missoes": 0, "etapas": 0, "obs": "já existem trilhas; use recriar=true"}
        # apaga na ordem certa (o SQLite não aplica ON DELETE CASCADE por padrão).
        # O progresso dos jogadores nas missões antigas também vai embora; XP e insígnias ficam.
        db.execute(delete(ProgressoMissao))
        db.execute(delete(MissaoEtapa))
        db.execute(delete(Missao))
        db.execute(delete(Trilha))
        db.flush()

    questoes = db.scalars(select(Questao).where(Questao.ativo.is_(True)).order_by(Questao.id)).all()
    por_publico: dict[str, dict[str, list[Questao]]] = defaultdict(lambda: defaultdict(list))
    for q in questoes:
        por_publico[q.publico][q.tema].append(q)

    n_trilhas = n_missoes = n_etapas = 0
    for ordem_trilha, publico in enumerate(sorted(por_publico, key=lambda p: list(TRILHAS).index(p)
                                                   if p in TRILHAS else 99), start=1):
        temas = por_publico[publico]
        titulo, descricao = TRILHAS.get(publico, (f"Jornada ({publico})", ""))
        trilha = Trilha(publico=publico, titulo=titulo, descricao=descricao, ordem=ordem_trilha)
        db.add(trilha)
        db.flush()
        n_trilhas += 1

        anterior: Missao | None = None
        ordem = 0
        for tema in _ordena_temas(publico, list(temas)):
            lista = temas[tema]
            n = -(-len(lista) // TAM_MAX)  # nº de partes (teto); divide de forma equilibrada: 5 → 3+2
            tam, resto = divmod(len(lista), n)
            blocos, ini = [], 0
            for k in range(n):
                fim = ini + tam + (1 if k < resto else 0)
                blocos.append(lista[ini:fim])
                ini = fim
            for i, bloco in enumerate(blocos, start=1):
                ordem += 1
                sufixo = f" — Parte {i}" if len(blocos) > 1 else ""
                m = Missao(
                    trilha_id=trilha.id, titulo=f"{tema}{sufixo}", tema=tema, tipo="quiz", ordem=ordem,
                    pre_requisito_id=anterior.id if anterior else None,
                    pct_minimo=PCT_MISSAO, xp_recompensa=XP_MISSAO,
                    insignia=f"{tema}" if i == len(blocos) else None,
                    narrativa_inicio=f"Nova missão: {tema.lower()}. Responda às perguntas para avançar.",
                    narrativa_fim=f"Missão concluída! Você avançou em {tema.lower()}.",
                )
                db.add(m)
                db.flush()
                for j, q in enumerate(bloco, start=1):
                    db.add(MissaoEtapa(missao_id=m.id, questao_id=q.id, ordem=j, xp_acerto=XP_ACERTO))
                    n_etapas += 1
                anterior = m
                n_missoes += 1

        # Desafio final: 1 questão de cada tema (só faz sentido com 2+ temas)
        if len(temas) >= 2:
            ordem += 1
            chefe = Missao(
                trilha_id=trilha.id, titulo="Desafio final", tema=None, tipo="chefe", ordem=ordem,
                pre_requisito_id=anterior.id if anterior else None,
                pct_minimo=PCT_CHEFE, xp_recompensa=XP_CHEFE, insignia=f"Mestre da {titulo}",
                narrativa_inicio="Hora do desafio final: uma pergunta de cada tema. Precisa de 80% para vencer.",
                narrativa_fim=f"Você completou a {titulo}!",
            )
            db.add(chefe)
            db.flush()
            for j, tema in enumerate(_ordena_temas(publico, list(temas)), start=1):
                db.add(MissaoEtapa(missao_id=chefe.id, questao_id=temas[tema][-1].id, ordem=j,
                                   xp_acerto=XP_ACERTO * 2))
                n_etapas += 1
            n_missoes += 1

    db.commit()
    return {"trilhas": n_trilhas, "missoes": n_missoes, "etapas": n_etapas}
