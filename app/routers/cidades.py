from fastapi import APIRouter, Query
from app.db import get_conn

router = APIRouter(prefix="/cidades", tags=["cidades"])


@router.get("")
def listar_cidades(
    busca: str | None = Query(None),
    renda_min: float | None = Query(None),
    renda_max: float | None = Query(None),
    limite: int = Query(200, ge=1, le=1000)
):
    sql = """
        with latest_renda as (
            select
                r.codigo_municipio,
                r.trimestre,
                r.valor_medio_m2,
                row_number() over (
                    partition by r.codigo_municipio
                    order by
                        cast(substring(r.trimestre from '(\\d{4})') as int) desc,
                        cast(substring(r.trimestre from '^(\\d)') as int) desc
                ) as rn
            from public.renda r
        ),
        latest_escolas as (
            select
                e.codigo_municipio,
                e.ano,
                e.valor,
                row_number() over (
                    partition by e.codigo_municipio
                    order by cast(e.ano as int) desc
                ) as rn
            from public.escolas e
        )
        select
            m.codigo_municipio,
            m.municipio_localidade,
            m.regiao,
            m.grande_regiao,
            lr.trimestre as renda_trimestre,
            lr.valor_medio_m2,
            coalesce(le.valor, 0) as total_escolas,
            coalesce(h.hospitais_2024, 0) as total_hospitais,
            coalesce(c.crimes_2024, 0) as total_crimes
        from public.municipios m
        left join latest_renda lr
            on lr.codigo_municipio = m.codigo_municipio
           and lr.rn = 1
        left join latest_escolas le
            on le.codigo_municipio = m.codigo_municipio
           and le.rn = 1
        left join public.hospitais h
            on h.codigo_municipio = m.codigo_municipio
        left join public.criminalidade c
            on c.codigo_municipio = m.codigo_municipio
        where 1 = 1
    """
    params = []

    if busca:
        sql += " and m.municipio_localidade ilike %s"
        params.append(f"%{busca}%")

    if renda_min is not None:
        sql += " and lr.valor_medio_m2 >= %s"
        params.append(renda_min)

    if renda_max is not None:
        sql += " and lr.valor_medio_m2 <= %s"
        params.append(renda_max)

    sql += " order by m.municipio_localidade asc limit %s"
    params.append(limite)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()