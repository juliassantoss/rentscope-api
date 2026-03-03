from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.db import get_conn

router = APIRouter(prefix="/filtros", tags=["filtros"])


class FiltroIn(BaseModel):
    usuario_id: str = Field(..., description="UUID do utilizador (temporário, depois vem do JWT)")
    codigo_pais: str = "PT"

    preco_m2: float | None = None
    metragem_minima: float | None = None
    taxa_criminalidade: int | None = None

    quer_museus: bool = False
    quer_galerias_arte: bool = False
    quer_bibliotecas: bool = False
    quer_hospitais: bool = False
    quer_escolas: bool = False


@router.post("/salvar")
def salvar_filtro(body: FiltroIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.filtros_salvos (
                    usuario_id, codigo_pais,
                    preco_m2, metragem_minima, taxa_criminalidade,
                    quer_museus, quer_galerias_arte, quer_bibliotecas, quer_hospitais, quer_escolas
                )
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                returning id, criado_em;
                """,
                (
                    body.usuario_id,
                    body.codigo_pais,
                    body.preco_m2,
                    body.metragem_minima,
                    body.taxa_criminalidade,
                    body.quer_museus,
                    body.quer_galerias_arte,
                    body.quer_bibliotecas,
                    body.quer_hospitais,
                    body.quer_escolas,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return row