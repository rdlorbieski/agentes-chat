"""Configuração lida das variáveis de ambiente ou dos secrets do Streamlit."""

import os
from dataclasses import dataclass


def _secret(nome):
    """Valor do .streamlit/secrets.toml, ou None se o arquivo ou a chave não existir."""
    try:
        import streamlit as st

        return st.secrets.get(nome)
    except Exception:  # noqa: BLE001 - sem secrets.toml o Streamlit levanta erros variados
        return None


def config(nome, padrao=None):
    """Variável de ambiente primeiro; depois os secrets do Streamlit; depois o padrão."""
    valor = os.environ.get(nome) or _secret(nome)
    return str(valor) if valor else padrao


@dataclass(frozen=True)
class Projeto:
    chave: str
    nome: str
    repo: str
    descricao: str


def projetos():
    """Os projetos que o chatbot conhece. O repositório de cada um pode ser trocado nos secrets."""
    return {
        "fitame": Projeto(
            chave="fitame",
            nome="Fita.me",
            repo=config("REPO_FITAME", "rdlorbieski/fitame-agentes"),
            descricao=(
                "O Fita.me recomenda o tamanho de roupa certo para cada consumidor (FitScore), "
                "a partir das medidas do corpo dele e das medidas de cada tamanho da peça. Tem "
                "três repositórios: a API em Django (api), o painel do lojista (web) e o app do "
                "consumidor (user). O catálogo pode ser importado da Nuvemshop."
            ),
        ),
        "ciga": Projeto(
            chave="ciga",
            nome="CIGA",
            repo=config("REPO_CIGA", "rdlorbieski/ciga-agentes"),
            descricao=(
                "O CIGA recebe leis municipais publicadas no Diário Oficial dos Municípios de SC, "
                "identifica quais leis anteriores cada uma altera, revoga ou cita, e gera o texto "
                "consolidado das leis alteradas."
            ),
        ),
    }
