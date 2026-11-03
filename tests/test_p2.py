import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from project_nov26_p2_cardapios import extrator
from project_nov26_p2_cardapios.metricas import avaliar, casar_itens, normalizar
from project_nov26_p2_cardapios.ruido import renderizar
from project_nov26_p2_cardapios.schema import Cardapio, Item

RAIZ = Path(__file__).resolve().parents[1]


def item(nome, preco=10.0, categoria="lanche", alergenos=None):
    return Item(nome=nome, preco=preco, categoria=categoria, alergenos=alergenos)


# --- esquema -------------------------------------------------------------------


def test_schema_rejeita_categoria_e_preco_invalidos():
    with pytest.raises(ValidationError):
        Item(nome="X", preco=-1, categoria="lanche")
    with pytest.raises(ValidationError):
        Item(nome="X", preco=1, categoria="hamburguer")
    with pytest.raises(ValidationError):
        Item(nome="X", preco=1, categoria="lanche", alergenos=["trigo"])


def test_gabaritos_validos_e_textos_gerados():
    for g in sorted((RAIZ / "data/gabarito").glob("*.json")):
        Cardapio.model_validate_json(g.read_text())
        assert (RAIZ / "data/menus" / f"{g.stem}.txt").exists()


# --- ruído ---------------------------------------------------------------------


def test_renderizar_e_deterministico_e_preserva_informacao():
    dados = json.loads((RAIZ / "data/gabarito/menu_02.json").read_text())
    texto = renderizar(dados, seed=1)
    assert texto == renderizar(dados, seed=1)
    for it in dados["itens"]:
        assert normalizar(it["nome"]) in normalizar(texto)


# --- métricas ------------------------------------------------------------------


def test_casamento_tolera_variacao_de_escrita():
    pares = casar_itens([item("X Tudo"), item("Suco")], [item("X-Tudo"), item("Refrigerante")])
    assert [(e.nome, g.nome) for e, g in pares] == [("X Tudo", "X-Tudo")]


def test_avaliar_caso_conhecido():
    gabarito = Cardapio(
        restaurante="R",
        itens=[
            item("Pizza", 50.0, "pizza", ["gluten", "lactose"]),
            item("Suco", None, "bebida", []),
        ],
    )
    extraido = Cardapio(
        restaurante="R",
        itens=[
            item("Pizza", 50.0, "pizza", ["gluten"]),  # faltou lactose
            item("Suco", 8.0, "bebida", []),  # preço inventado
            item("Bolo", 9.0, "sobremesa"),  # item inexistente
        ],
    )
    m = avaliar(extraido, gabarito)
    assert m["recall_nomes"] == 1.0
    assert m["precisao_nomes"] == pytest.approx(2 / 3)
    assert m["acuracia_preco"] == 0.5
    assert (m["alergenos_vp"], m["alergenos_fp"], m["alergenos_fn"]) == (1, 0, 1)


def test_avaliar_extracao_invalida():
    gabarito = Cardapio(restaurante="R", itens=[item("Pizza")])
    m = avaliar(None, gabarito)
    assert m["json_valido"] is False
    assert m["f1_nomes"] == 0


# --- extrator (LLM falso) --------------------------------------------------------


def test_extrator_tenta_de_novo_com_o_erro_de_validacao(monkeypatch):
    respostas = iter(
        [
            '{"restaurante": "R", "itens": [{"nome": "A", "categoria": "Hamburguer"}]}',
            '```json\n{"restaurante": "R", "itens": [{"nome": "A", "categoria": "lanche"}]}\n```',
        ]
    )
    recebidas = []

    def llm_falso(mensagens, modelo):
        recebidas.append(mensagens)
        return {
            "texto": next(respostas),
            "latencia_s": 0.1,
            "tokens_entrada": 10,
            "tokens_saida": 5,
        }

    monkeypatch.setattr(extrator, "chamar_llm", llm_falso)
    cardapio, meta = extrator.extrair("A ... 10")
    assert cardapio.itens[0].categoria == "lanche"
    assert meta["tentativas"] == 2
    assert "inválido" in recebidas[1][-1]["content"]
