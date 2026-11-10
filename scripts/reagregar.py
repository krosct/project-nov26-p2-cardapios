"""Refaz reports/resumo.json a partir dos CSVs por cardápio, sem chamar a API.

Uso: uv run python scripts/reagregar.py
Útil quando só a forma de agregar muda (os CSVs vêm de scripts/evaluate.py).
"""

import csv
import json
from pathlib import Path

from project_nov26_p2_cardapios.metricas import resumir_configuracao

RAIZ = Path(__file__).resolve().parents[1]
CONFIGS = ("zero_shot", "few_shot", "zero_shot_modelo_pequeno")
CAMPOS_TEXTO = {"menu"}


def ler(config: str) -> list[dict]:
    with open(RAIZ / f"reports/resultados_{config}.csv") as f:
        linhas = []
        for r in csv.DictReader(f):
            linha = {}
            for k, v in r.items():
                if k in CAMPOS_TEXTO:
                    linha[k] = v
                elif v in ("True", "False"):
                    linha[k] = v == "True"
                else:
                    linha[k] = float(v) if "." in v else int(v)
            linhas.append(linha)
    return linhas


def main() -> None:
    antigo = json.loads((RAIZ / "reports/resumo.json").read_text())
    resumo = {k: antigo[k] for k in ("modelo", "modelo_pequeno")}
    resumo["agregacao"] = (
        "micro por item nas métricas de campo; fração/média por cardápio nas demais"
    )
    for config in CONFIGS:
        resumo[config] = {k: round(v, 3) for k, v in resumir_configuracao(ler(config)).items()}
    (RAIZ / "reports/resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    print(json.dumps(resumo, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
