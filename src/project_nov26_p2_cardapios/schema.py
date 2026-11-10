"""Esquema de saída da extração."""

from typing import Literal

from pydantic import BaseModel, Field

# Conjunto fechado de alergênicos: qualquer outro valor é rejeitado pelo Pydantic
Alergeno = Literal[
    "gluten", "lactose", "ovo", "amendoim", "castanhas", "soja", "peixe", "frutos_do_mar"
]
# Conjunto fechado de categorias de item
Categoria = Literal[
    "entrada", "prato_principal", "lanche", "pizza", "sobremesa", "bebida", "combo", "outro"
]


class Item(BaseModel):
    # Um item do cardápio (prato, bebida, combo...)
    nome: str = Field(min_length=1)  # Nome obrigatório e não vazio
    preco: float | None = Field(
        default=None,
        ge=0,
        description="None = cardápio não informa",  # ge=0 bloqueia negativos
    )
    categoria: Categoria  # Obrigatória e dentro do Literal acima
    descricao: str | None = None  # Ingredientes/descrição, opcional
    alergenos: list[Alergeno] | None = Field(
        default=None,
        # None = não informado pelo cardápio; [] = declarado como sem alergênicos
        description="None = cardápio não informa; [] = cardápio declara que não há alergênicos",
    )
    vegetariano: bool | None = None  # True/False só se o cardápio marca; senão None


class Cardapio(BaseModel):
    # Cardápio completo: nome do restaurante e lista de itens
    restaurante: str = Field(min_length=1)  # Nome obrigatório e não vazio
    itens: list[Item] = Field(min_length=1)  # Precisa ter pelo menos um item
