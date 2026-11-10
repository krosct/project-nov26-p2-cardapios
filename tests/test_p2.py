import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from project_nov26_p2_cardapios import extrator
from project_nov26_p2_cardapios.metricas import avaliar, casar_itens, normalizar
from project_nov26_p2_cardapios.ruido import renderizar
from project_nov26_p2_cardapios.schema import Cardapio, Item

RAIZ = Path(__file__).resolve().parents[1]  # Raiz do projeto (pasta acima de tests/)


def item(nome, preco=10.0, categoria="lanche", alergenos=None):
    # Atalho para criar um Item de teste com valores padrão
    return Item(nome=nome, preco=preco, categoria=categoria, alergenos=alergenos)


# --- esquema -------------------------------------------------------------------


def test_schema_rejeita_categoria_e_preco_invalidos():
    # Preço negativo, categoria fora do Literal e alergênico fora do Literal devem falhar
    with pytest.raises(ValidationError):
        Item(nome="X", preco=-1, categoria="lanche")
    with pytest.raises(ValidationError):
        Item(nome="X", preco=1, categoria="hamburguer")
    with pytest.raises(ValidationError):
        Item(nome="X", preco=1, categoria="lanche", alergenos=["trigo"])


def test_gabaritos_validos_e_textos_gerados():
    # Todo gabarito deve validar no esquema e ter o texto bagunçado correspondente
    for g in sorted((RAIZ / "data/gabarito").glob("*.json")):
        Cardapio.model_validate_json(g.read_text())
        assert (RAIZ / "data/menus" / f"{g.stem}.txt").exists()


# --- ruído ---------------------------------------------------------------------


def test_renderizar_e_deterministico_e_preserva_informacao():
    # Mesma seed gera o mesmo texto, e todo nome de item do gabarito aparece no texto
    dados = json.loads((RAIZ / "data/gabarito/menu_02.json").read_text())
    texto = renderizar(dados, seed=1)
    assert texto == renderizar(dados, seed=1)
    for it in dados["itens"]:
        assert normalizar(it["nome"]) in normalizar(texto)


# --- métricas ------------------------------------------------------------------


def test_casamento_tolera_variacao_de_escrita():
    # "X Tudo" casa com "X-Tudo" (hífen é normalizado); "Suco" não casa com "Refrigerante"
    pares = casar_itens([item("X Tudo"), item("Suco")], [item("X-Tudo"), item("Refrigerante")])
    assert [(e.nome, g.nome) for e, g in pares] == [("X Tudo", "X-Tudo")]


def test_avaliar_caso_conhecido():
    # Caso com resultado calculado à mão: cada métrica tem o valor esperado
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
    assert m["recall_nomes"] == 1.0  # Achou os dois itens do gabarito
    assert m["precisao_nomes"] == pytest.approx(2 / 3)  # Um dos três extraídos é inventado
    assert m["acuracia_preco"] == 0.5  # Pizza acerta preço; Suco não
    assert (m["alergenos_vp"], m["alergenos_fp"], m["alergenos_fn"]) == (1, 0, 1)


def test_avaliar_extracao_invalida():
    # Extração None (JSON inválido) deve zerar as métricas, sem quebrar
    gabarito = Cardapio(restaurante="R", itens=[item("Pizza")])
    m = avaliar(None, gabarito)
    assert m["json_valido"] is False
    assert m["f1_nomes"] == 0


# --- extrator (LLM falso) --------------------------------------------------------


def test_extrator_tenta_de_novo_com_o_erro_de_validacao(monkeypatch):
    # Primeira resposta tem categoria inválida; a segunda vem com cercas de código e é válida
    respostas = iter(
        [
            '{"restaurante": "R", "itens": [{"nome": "A", "categoria": "Hamburguer"}]}',
            '```json\n{"restaurante": "R", "itens": [{"nome": "A", "categoria": "lanche"}]}\n```',
        ]
    )
    recebidas = []  # Guarda as mensagens enviadas em cada chamada

    def llm_falso(mensagens, modelo):
        # Substitui chamar_llm: devolve a próxima resposta pré-definida, sem rede
        recebidas.append(mensagens)
        return {
            "texto": next(respostas),
            "latencia_s": 0.1,
            "tokens_entrada": 10,
            "tokens_saida": 5,
        }

    monkeypatch.setattr(extrator, "chamar_llm", llm_falso)  # Troca o LLM real pelo falso
    cardapio, meta = extrator.extrair("A ... 10")
    assert cardapio.itens[0].categoria == "lanche"  # Segunda tentativa foi aceita
    assert meta["tentativas"] == 2
    assert "inválido" in recebidas[1][-1]["content"]  # O erro foi devolvido ao modelo


def test_resumo_agrega_por_item_e_nao_por_cardapio():
    from project_nov26_p2_cardapios.metricas import resumir_configuracao

    base = {
        "json_valido": True, "tentativas": 1, "itens_extraidos": 0, "alergenos_vp": 0,
        "alergenos_fp": 0, "alergenos_fn": 0, "acuracia_preco": 1.0,
        "acuracia_status_alergenos": 1.0,
        "latencia_s": 1.0, "tokens_entrada": 1, "tokens_saida": 1,
    }  # fmt: skip
    # Cardápio grande (9 itens, 9 certos) e pequeno (1 item, 0 certo): macro daria 0,5; micro, 0,9
    grande = {**base, "itens_casados": 9, "itens_gabarito": 9, "itens_extraidos": 9,
              "acuracia_categoria": 1.0}  # fmt: skip
    pequeno = {**base, "itens_casados": 1, "itens_gabarito": 1, "itens_extraidos": 1,
               "acuracia_categoria": 0.0}  # fmt: skip
    assert resumir_configuracao([grande, pequeno])["acuracia_categoria"] == 0.9
