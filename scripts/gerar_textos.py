"""Gera os textos bagunçados (data/menus, data/exemplos_fewshot) a partir dos gabaritos.

Uso: uv run python scripts/gerar_textos.py
"""

import json
from pathlib import Path

from project_nov26_p2_cardapios.ruido import renderizar
from project_nov26_p2_cardapios.schema import Cardapio

RAIZ = Path(__file__).resolve().parents[1]  # Raiz do projeto (pasta acima de scripts/)
SEED_BASE = 2026  # Semente base; cada arquivo recebe SEED_BASE + índice


def main() -> None:
    # Pares (gabarito, arquivo de texto de destino) para os cardápios de teste
    pares = [
        (g, RAIZ / "data/menus" / f"{g.stem}.txt")
        for g in sorted((RAIZ / "data/gabarito").glob("*.json"))
    ]
    # Mesmo processo para os exemplos few-shot, que ficam na pasta data/exemplos_fewshot
    pares += [
        (g, g.with_suffix(".txt")) for g in sorted((RAIZ / "data/exemplos_fewshot").glob("*.json"))
    ]
    for i, (gabarito, destino) in enumerate(pares):
        dados = json.loads(gabarito.read_text())
        Cardapio.model_validate(dados)  # gabarito precisa ser válido pelo esquema
        destino.parent.mkdir(parents=True, exist_ok=True)  # Cria a pasta de destino se faltar
        destino.write_text(renderizar(dados, seed=SEED_BASE + i))  # Gera e grava o texto
    print(f"{len(pares)} textos gerados")


if __name__ == "__main__":  # Só executa main() quando o arquivo é rodado diretamente
    main()
