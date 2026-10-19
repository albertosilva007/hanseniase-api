import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.orm import Session

from ..auth import admin_atual, confere_senha, cria_token
from ..database import get_db
from ..models import Questao, Resposta, Usuario
from ..schemas import Login, QuestaoAdmin, QuestaoAtualizar, QuestaoCriar, Token

router = APIRouter(prefix="/api", tags=["admin"])
protegido = [Depends(admin_atual)]


@router.post("/auth/login", response_model=Token)
def login(dados: Login, db: Session = Depends(get_db)):
    u = db.scalar(select(Usuario).where(Usuario.email == dados.email.strip().lower()))
    if not u or not confere_senha(dados.senha, u.senha_hash):
        raise HTTPException(401, "E-mail ou senha incorretos")
    return Token(access_token=cria_token(u.email))


@router.get("/admin/me", dependencies=protegido)
def me(u: Usuario = Depends(admin_atual)):
    return {"email": u.email}


# ---------- CRUD ----------
@router.get("/admin/questoes", response_model=list[QuestaoAdmin], dependencies=protegido)
def listar_todas(db: Session = Depends(get_db)):
    return db.scalars(select(Questao).order_by(Questao.id)).all()


@router.post("/admin/questoes", response_model=QuestaoAdmin, status_code=201, dependencies=protegido)
def criar(dados: QuestaoCriar, db: Session = Depends(get_db)):
    q = Questao(**dados.model_dump())
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.put("/admin/questoes/{qid}", response_model=QuestaoAdmin, dependencies=protegido)
def atualizar(qid: int, dados: QuestaoAtualizar, db: Session = Depends(get_db)):
    q = db.get(Questao, qid)
    if not q:
        raise HTTPException(404, "Questão não encontrada")
    for k, v in dados.model_dump().items():
        setattr(q, k, v)
    db.commit()
    db.refresh(q)
    return q


@router.delete("/admin/questoes/{qid}", status_code=204, dependencies=protegido)
def excluir(qid: int, db: Session = Depends(get_db)):
    q = db.get(Questao, qid)
    if not q:
        raise HTTPException(404, "Questão não encontrada")
    db.delete(q)
    db.commit()


# ---------- Estatísticas ----------
def _taxa(acertos, total):
    return round(acertos / total * 100, 1) if total else None


@router.get("/admin/stats", dependencies=protegido)
def stats(db: Session = Depends(get_db)):
    acertos = func.sum(cast(case((Resposta.acertou, 1), else_=0), Integer))
    total_r, total_a, sessoes = db.execute(
        select(func.count(Resposta.id), acertos, func.count(func.distinct(Resposta.sessao)))
    ).one()
    total_a = total_a or 0

    por_questao = []
    for qid, pub, tema, enun, n, a in db.execute(
        select(Questao.id, Questao.publico, Questao.tema, Questao.enunciado,
               func.count(Resposta.id), acertos)
        .join(Resposta, Resposta.questao_id == Questao.id, isouter=True)
        .group_by(Questao.id).order_by(Questao.id)
    ):
        por_questao.append({"id": qid, "publico": pub, "tema": tema, "enunciado": enun,
                            "respostas": n, "acertos": a or 0, "taxa": _taxa(a or 0, n)})

    def agrupa(chave):
        d = {}
        for q in por_questao:
            k = q[chave]
            g = d.setdefault(k, {chave: k, "respostas": 0, "acertos": 0})
            g["respostas"] += q["respostas"]
            g["acertos"] += q["acertos"]
        for g in d.values():
            g["taxa"] = _taxa(g["acertos"], g["respostas"])
        return sorted(d.values(), key=lambda g: g[chave])

    dia = func.date(Resposta.criado_em)
    por_dia = [{"dia": str(d), "respostas": n, "acertos": a or 0}
               for d, n, a in db.execute(select(dia, func.count(Resposta.id), acertos)
                                         .group_by(dia).order_by(dia))]

    return {
        "total_respostas": total_r, "total_acertos": total_a,
        "taxa_geral": _taxa(total_a, total_r), "sessoes": sessoes,
        "total_questoes": len(por_questao),
        "por_publico": agrupa("publico"), "por_tema": agrupa("tema"),
        "por_questao": por_questao, "por_dia": por_dia,
    }


@router.get("/admin/respostas.csv", dependencies=protegido)
def exportar_csv(db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["resposta_id", "criado_em", "sessao", "questao_id", "publico", "tema", "escolha", "correta", "acertou"])
    for r, q in db.execute(select(Resposta, Questao).join(Questao).order_by(Resposta.id)):
        w.writerow([r.id, r.criado_em.isoformat(), r.sessao, q.id, q.publico, q.tema, r.escolha, q.correta, int(r.acertou)])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=respostas_hanseniase.csv"})
