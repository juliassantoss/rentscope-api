from fastapi import APIRouter, Query
from app.db import get_conn

router = APIRouter(prefix="/cidades", tags=["cidades"])


@router.get("")
def listar_cidades(
    codigo_pais: str = Query("PT"),
    busca: str | None = Query(None),
    limite: int = Query(200, ge=1, le=1000)
):
    sql = """
        select id, nome, distrito, latitude, longitude
        from public.cidades
        where codigo_pais = %s
    """
    params = [codigo_pais]

    if busca:
        sql += " and nome ilike %s"
        params.append(f"%{busca}%")

    sql += " order by nome asc limit %s"
    params.append(limite)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()