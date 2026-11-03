"""Gera os textos bagunçados (data/menus, data/exemplos_fewshot) a partir dos gabaritos.

Uso: uv run python scripts/gerar_textos.py
"""

import json
from pathlib import Path

from project_nov26_p2_cardapios.ruido import renderizar
from project_nov26_p2_cardapios.schema import Cardapio

RAIZ = Path(__file__).resolve().parents[1]
SEED_BASE = 2026


def main() -> None:
    pares = [
        (g, RAIZ / "data/menus" / f"{g.stem}.txt")
        for g in sorted((RAIZ / "data/gabarito").glob("*.json"))
    ]
    pares += [
        (g, g.with_suffix(".txt")) for g in sorted((RAIZ / "data/exemplos_fewshot").glob("*.json"))
    ]
    for i, (gabarito, destino) in enumerate(pares):
        dados = json.loads(gabarito.read_text())
        Cardapio.model_validate(dados)  # gabarito precisa ser válido pelo esquema
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(renderizar(dados, seed=SEED_BASE + i))
    print(f"{len(pares)} textos gerados")


if __name__ == "__main__":
    main()
