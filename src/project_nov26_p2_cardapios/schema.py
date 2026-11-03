"""Esquema de saída da extração."""

from typing import Literal

from pydantic import BaseModel, Field

Alergeno = Literal[
    "gluten", "lactose", "ovo", "amendoim", "castanhas", "soja", "peixe", "frutos_do_mar"
]
Categoria = Literal[
    "entrada", "prato_principal", "lanche", "pizza", "sobremesa", "bebida", "combo", "outro"
]


class Item(BaseModel):
    nome: str = Field(min_length=1)
    preco: float | None = Field(default=None, ge=0, description="None = cardápio não informa")
    categoria: Categoria
    descricao: str | None = None
    alergenos: list[Alergeno] | None = Field(
        default=None,
        description="None = cardápio não informa; [] = cardápio declara que não há alergênicos",
    )
    vegetariano: bool | None = None


class Cardapio(BaseModel):
    restaurante: str = Field(min_length=1)
    itens: list[Item] = Field(min_length=1)
