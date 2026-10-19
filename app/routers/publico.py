from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Questao, Resposta
from ..schemas import Correcao, Publico, QuestaoPublica, RespostaCriar

router = APIRouter(prefix="/api", tags=["público"])


@router.get("/questoes", response_model=list[QuestaoPublica])
def listar(
    publico: Publico | None = None,
    tema: str | None = None,
    busca: str | None = Query(None, max_length=100),
    gabarito: bool = Query(False, description="true = modo leitura (inclui resposta e comentário)"),
    db: Session = Depends(get_db),
):
    st = select(Questao).where(Questao.ativo.is_(True))
    if publico:
        st = st.where(Questao.publico == publico)
    if tema:
        st = st.where(Questao.tema == tema)
    if busca:
        like = f"%{busca}%"
        st = st.where(or_(Questao.enunciado.ilike(like), Questao.explicacao.ilike(like), Questao.tema.ilike(like)))
    out = []
    for q in db.scalars(st.order_by(Questao.publico, Questao.id)):
        item = QuestaoPublica.model_validate(q)
        if not gabarito:
            item.correta = None
            item.explicacao = None
        out.append(item)
    return out


@router.get("/temas", response_model=list[str])
def temas(publico: Publico | None = None, db: Session = Depends(get_db)):
    st = select(Questao.tema).where(Questao.ativo.is_(True)).distinct()
    if publico:
        st = st.where(Questao.publico == publico)
    return sorted(db.scalars(st))


@router.post("/respostas", response_model=Correcao, status_code=201)
def responder(r: RespostaCriar, db: Session = Depends(get_db)):
    q = db.get(Questao, r.questao_id)
    if not q or not q.ativo:
        raise HTTPException(404, "Questão não encontrada")
    if r.escolha >= len(q.opcoes):
        raise HTTPException(422, "Opção inexistente para esta questão")
    acertou = r.escolha == q.correta
    db.add(Resposta(questao_id=q.id, escolha=r.escolha, acertou=acertou, sessao=r.sessao))
    db.commit()
    return Correcao(questao_id=q.id, acertou=acertou, correta=q.correta, explicacao=q.explicacao)
