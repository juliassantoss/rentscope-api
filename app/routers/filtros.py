from math import isfinite
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.db import get_conn

router = APIRouter(prefix="/filtros", tags=["filtros"])


class FiltroIn(BaseModel):
    usuario_id: str = Field(...,
                            description="UUID do utilizador (temporÃ¡rio, depois vem do JWT)")
    codigo_pais: str = "PT"

    preco_m2: float | None = None
    metragem_minima: float | None = None
    taxa_criminalidade: int | None = None

    quer_museus: bool = False
    quer_galerias_arte: bool = False
    quer_bibliotecas: bool = False
    quer_hospitais: bool = False
    quer_escolas: bool = False


class ScoreFiltroIn(BaseModel):
    busca: str | None = None

    renda_min: float | None = None
    renda_max: float | None = None

    peso_renda: float = 1.0
    peso_escolas: float = 1.0
    peso_hospitais: float = 1.0
    peso_criminalidade: float = 1.0

    limite: int = 400


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


@router.post("/aplicar")
def aplicar_filtros(body: ScoreFiltroIn):
    peso_renda = max(body.peso_renda, 0.0)
    peso_escolas = max(body.peso_escolas, 0.0)
    peso_hospitais = max(body.peso_hospitais, 0.0)
    peso_criminalidade = max(body.peso_criminalidade, 0.0)

    soma_pesos = peso_renda + peso_escolas + peso_hospitais + peso_criminalidade
    if soma_pesos == 0:
        soma_pesos = 1.0

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
                    order by cast(split_part(e.ano, '/', 1) as int) desc
                ) as rn
            from public.escolas e
        ),
        base as (
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
        ),
        buscado as (
            select *
            from base
            where 1 = 1
        ),
        enriquecido as (
            select
                *,
                ln(1 + total_escolas) as escolas_suave,
                ln(1 + total_hospitais) as hospitais_suave,
                ln(1 + total_crimes) as crimes_suave
            from buscado
        ),
        normalizado as (
            select
                *,
                min(escolas_suave) over () as min_escolas_suave,
                max(escolas_suave) over () as max_escolas_suave,
                min(hospitais_suave) over () as min_hospitais_suave,
                max(hospitais_suave) over () as max_hospitais_suave,
                min(crimes_suave) over () as min_crimes_suave,
                max(crimes_suave) over () as max_crimes_suave,
                min(valor_medio_m2) over () as min_renda_data,
                max(valor_medio_m2) over () as max_renda_data
            from enriquecido
        ),
        scoreado as (
            select
                codigo_municipio,
                municipio_localidade,
                regiao,
                grande_regiao,
                renda_trimestre,
                valor_medio_m2,
                total_escolas,
                total_hospitais,
                total_crimes,

                case
                    when max_escolas_suave = min_escolas_suave then 1.0
                    else (escolas_suave - min_escolas_suave) / nullif(max_escolas_suave - min_escolas_suave, 0)
                end as score_escolas,

                case
                    when max_hospitais_suave = min_hospitais_suave then 1.0
                    else (hospitais_suave - min_hospitais_suave) / nullif(max_hospitais_suave - min_hospitais_suave, 0)
                end as score_hospitais,

                case
                    when max_crimes_suave = min_crimes_suave then 1.0
                    else 1.0 - ((crimes_suave - min_crimes_suave)::float / nullif(max_crimes_suave - min_crimes_suave, 0))
                end as score_criminalidade,

                case
                    -- Caso novo: sem filtro de min/max. PontuaÃ§Ã£o inversa
                    -- normalizada â€” municÃ­pio mais barato = 1.0, mais caro = 0.0.
                    -- MunicÃ­pio sem dados de renda contribui 0.
                    when %s is null and %s is null then
                        case
                            when valor_medio_m2 is null then 0.0
                            when max_renda_data is null or min_renda_data is null then 1.0
                            when max_renda_data = min_renda_data then 1.0
                            else 1.0 - (
                                (valor_medio_m2 - min_renda_data)::float
                                / nullif(max_renda_data - min_renda_data, 0)
                            )
                        end

                    -- Caso legacy: histÃ³rico antigo guardou min/max. MantÃ©m o
                    -- comportamento original baseado em intervalo de renda.
                    when %s is not null and %s is not null and valor_medio_m2 between %s and %s then 1.0

                    when %s is not null and %s is not null then
                        greatest(
                            0.0,
                            1.0 - (
                                case
                                    when valor_medio_m2 < %s then (%s - valor_medio_m2)
                                    when valor_medio_m2 > %s then (valor_medio_m2 - %s)
                                    else 0.0
                                end
                            ) / nullif(greatest(%s - min_renda_data, max_renda_data - %s, 1.0), 0)
                        )

                    when %s is not null then
                        greatest(
                            0.0,
                            1.0 - abs(valor_medio_m2 - %s) / nullif(greatest(max_renda_data - min_renda_data, 1.0), 0)
                        )

                    when %s is not null then
                        greatest(
                            0.0,
                            1.0 - abs(valor_medio_m2 - %s) / nullif(greatest(max_renda_data - min_renda_data, 1.0), 0)
                        )

                    else 1.0
                end as score_renda
            from normalizado
        )
        select
            codigo_municipio,
            municipio_localidade,
            regiao,
            grande_regiao,
            renda_trimestre,
            valor_medio_m2,
            total_escolas,
            total_hospitais,
            total_crimes,
            score_renda,
            score_escolas,
            score_hospitais,
            score_criminalidade,
            (
                (
                    score_renda * %s +
                    score_escolas * %s +
                    score_hospitais * %s +
                    score_criminalidade * %s
                ) / %s
            ) as score
        from scoreado
        where 1 = 1
    """

    params = [
        body.renda_min,
        body.renda_max,

        body.renda_min,
        body.renda_max,
        body.renda_min,
        body.renda_max,

        body.renda_min,
        body.renda_max,
        body.renda_min,
        body.renda_min,
        body.renda_max,
        body.renda_max,
        body.renda_min if body.renda_min is not None else 0.0,
        body.renda_max if body.renda_max is not None else 0.0,

        body.renda_min,
        body.renda_min if body.renda_min is not None else 0.0,

        body.renda_max,
        body.renda_max if body.renda_max is not None else 0.0,

        peso_renda,
        peso_escolas,
        peso_hospitais,
        peso_criminalidade,
        soma_pesos,
    ]

    if body.busca:
        sql += " and municipio_localidade ilike %s"
        params.append(f"%{body.busca}%")

    sql += " order by score desc, municipio_localidade asc limit %s"
    params.append(body.limite)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

