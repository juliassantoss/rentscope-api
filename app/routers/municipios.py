from fastapi import APIRouter
from app.db import get_conn

router = APIRouter(prefix="/municipios", tags=["municipios"])


@router.get("/")
def listar_municipios():
    sql = """
        select codigo_municipio, municipio_localidade
        from public.municipios
        order by municipio_localidade asc
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()