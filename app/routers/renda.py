from fastapi import APIRouter, Query
from app.db import get_conn

router = APIRouter(prefix="/renda", tags=["renda"])


@router.get("/historico")
def historico_renda(
    codigo_municipio: int = Query(...),
):
    sql = """
        select
            r.codigo_municipio,
            m.municipio_localidade,
            r.trimestre,
            r.valor_medio_m2
        from public.renda r
        join public.municipios m
          on m.codigo_municipio = r.codigo_municipio
        where r.codigo_municipio = %s
        order by
            cast(substring(r.trimestre from '(\\d{4})') as int) asc,
            cast(substring(r.trimestre from '^(\\d)') as int) asc
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, [codigo_municipio])
            return cur.fetchall()