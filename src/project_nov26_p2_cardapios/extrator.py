"""Extração: texto de cardápio → `Cardapio` validado, com nova tentativa em caso de erro."""

import json
import re

from pydantic import ValidationError

from project_nov26_p2_cardapios.llm import MODELO_PADRAO, chamar_llm
from project_nov26_p2_cardapios.schema import Cardapio

# Instruções de sistema: regras de extração; o esquema JSON é anexado no fim
INSTRUCOES = """Você extrai cardápios de restaurantes para JSON.

Regras:
- Devolva SOMENTE um JSON válido no esquema abaixo, sem texto antes ou depois.
- Um item por produto vendido. Não invente itens.
- preco: número em reais (ex.: 32.9). Se o cardápio não informa o preço, use null.
- categoria: uma das opções do esquema, deduzida da seção ou do nome do item.
- descricao: os ingredientes/descrição que aparecem no cardápio, ou null.
- alergenos: SOMENTE se o cardápio DECLARA alergênicos para o item. Converta sinônimos
  (leite/laticínios → lactose; trigo → gluten; camarão/frutos do mar → frutos_do_mar;
  nozes/castanha → castanhas; shoyu → soja; ovos → ovo).
  Se o cardápio declara que o item não tem alergênicos, use [].
  Se o cardápio não diz nada sobre alergênicos, use null — NÃO deduza pelos ingredientes.
- vegetariano: true/false somente se o cardápio marca itens vegetarianos; senão null.

Esquema:
"""


def montar_prompt(texto: str, exemplos: list[tuple[str, dict]] | None = None) -> list[dict]:
    # Gera o JSON Schema do Pydantic, que vira parte do prompt de sistema
    esquema = json.dumps(Cardapio.model_json_schema(), ensure_ascii=False)
    mensagens = [{"role": "system", "content": INSTRUCOES + esquema}]
    for texto_ex, json_ex in exemplos or []:  # Few-shot: pares (texto, JSON) de exemplo
        mensagens += [
            {"role": "user", "content": texto_ex},
            {"role": "assistant", "content": json.dumps(json_ex, ensure_ascii=False)},
        ]
    mensagens.append({"role": "user", "content": texto})  # Cardápio real a ser extraído
    return mensagens


def limpar_cercas(texto: str) -> str:
    """Remove cercas de código (```json ... ```) que alguns modelos adicionam."""
    # Captura o conteúdo entre as cercas; se não houver cercas, usa o texto inteiro
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, flags=re.DOTALL)
    return (m.group(1) if m else texto).strip()


def extrair(
    texto: str,
    exemplos: list[tuple[str, dict]] | None = None,
    modelo: str = MODELO_PADRAO,
    max_tentativas: int = 3,
) -> tuple[Cardapio | None, dict]:
    """Retorna (cardápio ou None, metadados: tentativas, latência e tokens acumulados)."""
    mensagens = montar_prompt(texto, exemplos)
    # Acumuladores de métricas somados a cada tentativa
    meta = {"tentativas": 0, "latencia_s": 0.0, "tokens_entrada": 0, "tokens_saida": 0}
    for _ in range(max_tentativas):  # Laço de nova tentativa com o erro de validação
        r = chamar_llm(mensagens, modelo)  # Chamada ao LLM (usa cache quando possível)
        meta["tentativas"] += 1
        meta["latencia_s"] += r["latencia_s"]
        meta["tokens_entrada"] += r["tokens_entrada"] or 0  # None vira 0 na soma
        meta["tokens_saida"] += r["tokens_saida"] or 0
        try:
            # Valida a resposta contra o esquema; sucesso encerra a função
            return Cardapio.model_validate_json(limpar_cercas(r["texto"])), meta
        except ValidationError as erro:
            # Anexa a resposta inválida e o erro, pedindo um JSON corrigido na próxima rodada
            mensagens = mensagens + [
                {"role": "assistant", "content": r["texto"]},
                {
                    "role": "user",
                    "content": f"O JSON é inválido:\n{erro}\nDevolva somente o JSON corrigido.",
                },
            ]
    return None, meta  # Esgotou as tentativas sem JSON válido
