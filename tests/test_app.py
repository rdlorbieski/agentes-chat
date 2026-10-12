"""A tela inteira, com GitHub e Claude falsos: nada sai da máquina."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from chatbot.armazenamento import Banco
from chatbot.campanhas import ler_campanha
from chatbot.github import GitHub

from conftest import RAIZ, issue

USUARIO = "rodolfo"
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
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_USUARIO", USUARIO)
    monkeypatch.setenv("APP_SENHA", SENHA)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-falsa")
    monkeypatch.setenv("GITHUB_TOKEN", "token-falso")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "conversas.db"))
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
    tela.banco = Banco(tmp_path / "conversas.db")
    return tela


def _entrar(tela):
    tela.run()
    tela.text_input[0].input(USUARIO)
    tela.text_input[1].input(SENHA)
    tela.button[0].click()
    tela.run()
    assert not tela.exception, tela.exception
    return tela


def _botao(tela, chave=None, rotulo=None):
    return next(b for b in tela.button if (chave and b.key == chave) or (rotulo and b.label == rotulo))


def _titulos_na_lista(tela):
    return [b.label for b in tela.button if (b.key or "").startswith("abrir_")]


def test_pede_login_e_recusa_o_errado(app):
    app.run()
    assert not app.chat_input
    app.text_input[0].input(USUARIO)
    app.text_input[1].input("errada")
    app.button[0].click()
    app.run()
    assert "Usuário ou senha incorretos." in [e.value for e in app.error]
    assert not app.chat_input


def test_login_padrao_sem_configuracao(app, monkeypatch):
    monkeypatch.delenv("APP_USUARIO")
    monkeypatch.delenv("APP_SENHA")
    app.run()
    app.text_input[0].input("admin")
    app.text_input[1].input("chat-agentes")
    app.button[0].click()
    app.run()
    assert app.chat_input


def test_responde_e_salva_a_conversa(app):
    tela = _entrar(app)
    assert tela.subheader[0].value == "Prioridades Fita.me · campanha 3"
    assert tela.repos_lidos == ["rdlorbieski/fitame-agentes"]

    tela.chat_input[0].set_value("Quais achados ficaram de fora?").run()
    assert not tela.exception, tela.exception
    assert "Resposta de teste." in [m.value for m in tela.markdown]

    chamada = _ClaudeFalso.chamadas[-1]
    assert chamada["model"] == "claude-opus-5-5"
    assert chamada["output_config"] == {"effort": "medium"}
    assert chamada["fallbacks"] == "default"
    assert chamada["messages"] == [{"role": "user", "content": "Quais achados ficaram de fora?"}]
    assert len(chamada["system"]) == 2
    assert "conteúdo de contexto/conhecido.md" in chamada["system"][1]["text"]

    [conversa] = tela.banco.conversas("fitame")
    assert conversa["titulo"] == "Quais achados ficaram de fora?"
    assert conversa["campanha"] == 3
    assert [m["role"] for m in tela.banco.mensagens(conversa["id"])] == ["user", "assistant"]
    assert _titulos_na_lista(tela) == ["Quais achados ficaram de fora?"]

    # A segunda pergunta continua a mesma conversa, com a primeira troca no histórico.
    tela.chat_input[0].set_value("E o que mais?").run()
    historico = _ClaudeFalso.chamadas[-1]["messages"]
    assert [m["role"] for m in historico] == ["user", "assistant", "user"]
    assert historico[1]["content"] == "Resposta de teste."
    assert all(set(m) == {"role", "content"} for m in historico)
    assert len(tela.banco.conversas("fitame")) == 1
    assert len(tela.banco.mensagens(conversa["id"])) == 4
    assert "Baixar esta conversa (.md)" in [b.label for b in tela.get("download_button")]


def test_sugestao_vira_pergunta_e_some_da_tela(app):
    tela = _entrar(app)
    _botao(tela, chave="sugestao_0").click().run()
    assert not tela.exception, tela.exception

    assert _ClaudeFalso.chamadas[-1]["messages"][0]["content"].startswith("Quais achados")
    assert not [b for b in tela.button if (b.key or "").startswith("sugestao_")]


def test_reabre_conversa_antiga_na_campanha_dela(app):
    antiga = app.banco.criar_conversa("fitame", 2, "Sobre a campanha 2")
    app.banco.adicionar_troca(antiga, "Pergunta antiga", "Resposta antiga")
    app.banco.adicionar_transcricao(antiga, "reuniao.srt", "Rodolfo: foco na Nuvemshop.")
    tela = _entrar(app)

    _botao(tela, chave=f"abrir_{antiga}").click().run()
    assert not tela.exception, tela.exception
    assert "Resposta antiga" in [m.value for m in tela.markdown]
    assert tela.selectbox[0].value.numero == 2

    tela.chat_input[0].set_value("E agora?").run()
    chamada = _ClaudeFalso.chamadas[-1]
    assert [m["content"] for m in chamada["messages"]] == ["Pergunta antiga", "Resposta antiga", "E agora?"]
    assert len(chamada["system"]) == 3
    assert "Rodolfo: foco na Nuvemshop." in chamada["system"][2]["text"]
    assert "campanha 2" in chamada["system"][1]["text"]


def test_nova_conversa_comeca_vazia(app):
    antiga = app.banco.criar_conversa("fitame", 3, "Antiga")
    app.banco.adicionar_troca(antiga, "Pergunta antiga", "Resposta antiga")
    tela = _entrar(app)
    _botao(tela, chave=f"abrir_{antiga}").click().run()
    _botao(tela, rotulo="＋ Nova conversa").click().run()

    assert "Resposta antiga" not in [m.value for m in tela.markdown]
    tela.chat_input[0].set_value("Outra coisa").run()
    assert _ClaudeFalso.chamadas[-1]["messages"] == [{"role": "user", "content": "Outra coisa"}]
    assert len(tela.banco.conversas("fitame")) == 2


def test_renomeia_e_exclui_conversa(app):
    conversa = app.banco.criar_conversa("fitame", 3, "Nome velho")
    app.banco.adicionar_troca(conversa, "p", "r")
    tela = _entrar(app)
    _botao(tela, chave=f"abrir_{conversa}").click().run()

    tela.text_input(key=f"titulo_{conversa}").input("Nome novo")
    _botao(tela, chave=f"renomear_{conversa}").click().run()
    assert tela.banco.conversa(conversa)["titulo"] == "Nome novo"
    assert _titulos_na_lista(tela) == ["Nome novo"]

    _botao(tela, chave=f"excluir_{conversa}").click().run()
    assert not tela.exception, tela.exception
    assert tela.banco.conversa(conversa) is None
    assert tela.session_state["conversa_atual"]["fitame"] is None
    assert _titulos_na_lista(tela) == []


def test_troca_de_projeto_mostra_so_as_conversas_dele(app):
    app.banco.criar_conversa("fitame", 3, "Do Fita.me")
    app.banco.criar_conversa("ciga", 3, "Do CIGA")
    tela = _entrar(app)
    assert _titulos_na_lista(tela) == ["Do Fita.me"]

    tela.radio[0].set_value("ciga").run()
    assert not tela.exception, tela.exception
    assert tela.repos_lidos[-1] == "rdlorbieski/ciga-agentes"
    assert _titulos_na_lista(tela) == ["Do CIGA"]

    tela.chat_input[0].set_value("Oi").run()
    assert "projeto CIGA" in _ClaudeFalso.chamadas[-1]["system"][0]["text"]


def test_erro_do_claude_aparece_e_nada_e_salvo(app):
    tela = _entrar(app)
    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    _ClaudeFalso.erro = anthropic.AuthenticationError(
        "chave inválida", response=httpx2.Response(401, request=requisicao), body=None
    )
    tela.chat_input[0].set_value("Oi").run()

    assert any("ANTHROPIC_API_KEY foi recusada" in e.value for e in tela.error)
    assert tela.banco.conversas("fitame") == []
