"""Cliente de LLM independente de provedor (API compatível com a OpenAI).

Respostas ficam em cache em disco: reexecutar a avaliação não gasta requisições
e o resultado é reproduzível.
"""

import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

load_dotenv()  # Carrega variáveis do arquivo .env para o os.environ

# URL base da API (padrão: OpenRouter); troca de provedor por variável de ambiente
BASE_URL = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
# Modelo padrão, sobrescrevível por LLM_MODEL
MODELO_PADRAO = os.environ.get("LLM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
# Pasta do cache em disco das respostas
CACHE = Path(os.environ.get("LLM_CACHE_DIR", ".cache/llm"))


def _client() -> OpenAI:
    # Cria o cliente OpenAI apontando para a BASE_URL com a chave da API
    return OpenAI(base_url=BASE_URL, api_key=os.environ["OPENROUTER_API_KEY"])


def chamar_llm(
    mensagens: list[dict],
    modelo: str = MODELO_PADRAO,
    max_tentativas: int = 6,
    **kwargs,
) -> dict:
    """Retorna {texto, latencia_s, tokens_entrada, tokens_saida, cache}."""
    # Chave do cache: hash SHA-256 de (mensagens, modelo, kwargs) serializados de forma estável
    chave = hashlib.sha256(json.dumps([mensagens, modelo, kwargs], sort_keys=True).encode())
    arquivo = CACHE / f"{chave.hexdigest()}.json"
    if arquivo.exists():  # Se já existe no cache, devolve sem chamar a API
        return {**json.loads(arquivo.read_text()), "cache": True}

    for tentativa in range(max_tentativas):  # Laço de retry com espera crescente
        try:
            inicio = time.perf_counter()  # Marca o início para medir a latência
            resp = _client().chat.completions.create(
                model=modelo,
                messages=mensagens,
                temperature=0,  # Temperatura zero: saída mais determinística
                **kwargs,
            )
            texto = resp.choices[0].message.content  # Texto da primeira escolha
            if not texto:  # Resposta vazia conta como erro para tentar de novo
                raise ValueError("resposta vazia")
            resultado = {
                "texto": texto,
                "latencia_s": round(time.perf_counter() - inicio, 3),  # Tempo da chamada
                # Tokens reportados pelo provedor (None se ele não informar uso)
                "tokens_entrada": resp.usage.prompt_tokens if resp.usage else None,
                "tokens_saida": resp.usage.completion_tokens if resp.usage else None,
            }
            break  # Sucesso: sai do laço de retry
        except (RateLimitError, APIConnectionError, APIStatusError, ValueError):
            if tentativa == max_tentativas - 1:  # Última tentativa: propaga o erro
                raise
            time.sleep(min(2 ** (tentativa + 1), 60))  # 2, 4, 8, 16, 32 s

    CACHE.mkdir(parents=True, exist_ok=True)  # Cria a pasta do cache se não existir
    arquivo.write_text(json.dumps(resultado, ensure_ascii=False))  # Salva no cache
    return {**resultado, "cache": False}  # Resposta nova (não veio do cache)
