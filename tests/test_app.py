"""A tela inteira, com GitHub e Claude falsos: nada sai da máquina."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from chatbot.campanhas import ler_campanha
from chatbot.github import GitHub

from conftest import RAIZ, issue

SENHA = "senha-de-teste"


class _StreamFalso:
    def __init__(self, erro=None):
        self.erro = erro

    def __enter__(self):
        if self.erro:
            raise self.erro
        return self

    def __exit__(self, *_):
        return False

    @property
    def text_stream(self):
        yield "Resposta "
        yield "de teste."

    def get_final_message(self):
        uso = SimpleNamespace(
            input_tokens=20, output_tokens=5, cache_read_input_tokens=1000, cache_creation_input_tokens=0
        )
        return SimpleNamespace(usage=uso, stop_reason="end_turn")


class _ClaudeFalso:
    chamadas = []
    erro = None

    def __init__(self, api_key):
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        _ClaudeFalso.chamadas.append(kwargs)
        return _StreamFalso(_ClaudeFalso.erro)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("APP_SENHA", SENHA)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-falsa")
    monkeypatch.setenv("GITHUB_TOKEN", "token-falso")
    monkeypatch.setattr(anthropic, "Anthropic", _ClaudeFalso)

    lidos = []

    def campanhas(self, repo, limite=20):
        lidos.append(repo)
        return [
            ler_campanha(issue(3)),
            ler_campanha(issue(2, estado="closed", criada="2026-10-05T15:00:00Z")),
        ]

    monkeypatch.setattr(GitHub, "campanhas", campanhas)
    monkeypatch.setattr(GitHub, "arquivo", lambda self, repo, caminho: f"conteúdo de {caminho}")

    _ClaudeFalso.chamadas = []
    _ClaudeFalso.erro = None
    st.cache_data.clear()
    st.cache_resource.clear()

    tela = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30)
    tela.repos_lidos = lidos
    return tela


def _entrar(tela):
    tela.run()
    tela.text_input[0].input(SENHA)
    tela.button[0].click()
    tela.run()
    assert not tela.exception, tela.exception
    return tela


def test_pede_senha_e_recusa_a_errada(app):
    app.run()
    assert not app.chat_input
    app.text_input[0].input("errada")
    app.button[0].click()
    app.run()
    assert "Senha incorreta." in [e.value for e in app.error]
    assert not app.chat_input


def test_mostra_a_campanha_e_responde(app):
    tela = _entrar(app)
    assert tela.subheader[0].value == "Prioridades Fita.me · campanha 3"
    assert tela.repos_lidos == ["rdlorbieski/fitame-agentes"]

    tela.chat_input[0].set_value("Quais achados ficaram de fora?").run()
    assert not tela.exception, tela.exception

    textos = [m.value for m in tela.markdown]
    assert "Resposta de teste." in textos

    chamada = _ClaudeFalso.chamadas[-1]
    assert chamada["model"] == "claude-opus-5-5"
    assert chamada["output_config"] == {"effort": "medium"}
    assert chamada["fallbacks"] == "default"
    assert chamada["messages"] == [{"role": "user", "content": "Quais achados ficaram de fora?"}]
    assert len(chamada["system"]) == 2
    assert "conteúdo de contexto/conhecido.md" in chamada["system"][1]["text"]

    # A segunda pergunta leva a primeira troca no histórico.
    tela.chat_input[0].set_value("E o que mais?").run()
    historico = _ClaudeFalso.chamadas[-1]["messages"]
    assert [m["role"] for m in historico] == ["user", "assistant", "user"]
    assert historico[1]["content"] == "Resposta de teste."
    assert all(set(m) == {"role", "content"} for m in historico)
    assert "Baixar a conversa (.md)" in [b.label for b in tela.get("download_button")]


def test_sugestao_vira_pergunta_e_some_da_tela(app):
    tela = _entrar(app)
    sugestao = next(b for b in tela.button if b.key == "sugestao_0")
    sugestao.click().run()
    assert not tela.exception, tela.exception

    assert _ClaudeFalso.chamadas[-1]["messages"][0]["content"].startswith("Quais achados")
    assert not [b for b in tela.button if (b.key or "").startswith("sugestao_")]


def test_transcricao_vira_um_bloco_a_mais(app):
    tela = _entrar(app)
    tela.session_state["transcricoes"] = {"fitame": {"reuniao.srt": "Rodolfo: foco na Nuvemshop."}}
    tela.run()
    tela.chat_input[0].set_value("O que a reunião decidiu?").run()

    system = _ClaudeFalso.chamadas[-1]["system"]
    assert len(system) == 3
    assert "Rodolfo: foco na Nuvemshop." in system[2]["text"]


def test_troca_de_projeto_le_o_outro_repositorio(app):
    tela = _entrar(app)
    tela.radio[0].set_value("ciga").run()
    assert not tela.exception, tela.exception
    assert tela.repos_lidos[-1] == "rdlorbieski/ciga-agentes"

    tela.chat_input[0].set_value("Oi").run()
    assert "projeto CIGA" in _ClaudeFalso.chamadas[-1]["system"][0]["text"]


def test_erro_do_claude_aparece_e_nao_fica_no_historico(app):
    tela = _entrar(app)
    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    _ClaudeFalso.erro = anthropic.AuthenticationError(
        "chave inválida", response=httpx2.Response(401, request=requisicao), body=None
    )
    tela.chat_input[0].set_value("Oi").run()

    assert any("ANTHROPIC_API_KEY foi recusada" in e.value for e in tela.error)
    assert tela.session_state["conversas"]["fitame"] == []
