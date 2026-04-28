import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/ai", tags=["ai"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class AiQuestionRequest(BaseModel):
    pais: str
    municipio: Optional[str] = None
    pergunta: str
    idioma_app: str
    renda_min: Optional[float] = None
    renda_max: Optional[float] = None
    peso_renda: Optional[float] = None
    peso_escolas: Optional[float] = None
    peso_hospitais: Optional[float] = None
    peso_criminalidade: Optional[float] = None
    renda: Optional[float] = None
    escolas: Optional[float] = None
    hospitais: Optional[float] = None
    criminalidade: Optional[float] = None
    score: Optional[float] = None


class AiQuestionResponse(BaseModel):
    resposta: str


def resolve_language_name(language_code: str) -> str:
    normalized = (language_code or "pt").strip().lower()
    return {
        "pt": "Portuguese",
        "en": "English",
        "es": "Spanish",
    }.get(normalized, "Portuguese")


@router.post("/pergunta", response_model=AiQuestionResponse)
def perguntar_ia(payload: AiQuestionRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nao configurada.")

    app_language = resolve_language_name(payload.idioma_app)

    contexto = f"""
App language: {app_language}
Country: {payload.pais}
Municipality mentioned: {payload.municipio or "not specified"}
User question: {payload.pergunta}

Current search context:
- normalized rent min: {payload.renda_min}
- normalized rent max: {payload.renda_max}
- rent weight: {payload.peso_renda}
- schools weight: {payload.peso_escolas}
- hospitals weight: {payload.peso_hospitais}
- crime weight: {payload.peso_criminalidade}

Available local metrics:
- score: {payload.score}
- rent: {payload.renda}
- schools: {payload.escolas}
- hospitals: {payload.hospitais}
- crime: {payload.criminalidade}
""".strip()

    instructions = """
You are Scopey, the assistant inside the RentScope app.

Your job is to help the user with:
- municipalities and places to live
- score interpretation
- filters and weights
- rent, schools, hospitals, and crime
- choropleth map reading
- price history
- app usage

Rules:
- Always answer in the app language provided in the context.
- If the user sends only a greeting or a very short message with no clear request, answer naturally, briefly, and warmly.
- Do not mention any specific city, municipality, or country unless the user mentioned it or explicitly asked about it.
- Use the provided context when it is relevant, but do not force context into every answer.
- If some data is missing, answer generally without inventing facts.
- Do not ask unnecessary follow-up questions.
- Keep the answer concise, clear, and natural.
- Prefer short paragraphs instead of lists unless a list is clearly useful.
""".strip()

    try:
        response = client.responses.create(
            model="gpt-5.4",
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": contexto},
            ],
        )

        return AiQuestionResponse(resposta=response.output_text.strip())

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar IA: {str(exc)}")
