import pytest

from chatbot.armazenamento import Banco, titulo_para


@pytest.fixture
def banco(tmp_path):
    return Banco(tmp_path / "dados" / "conversas.db")


def test_conversa_com_troca_e_transcricao(banco):
    conversa = banco.criar_conversa("fitame", 3, "Quais achados ficaram de fora?")
    banco.adicionar_troca(conversa, "Quais achados ficaram de fora?", "Dois.", legenda="10 tokens")
    banco.adicionar_transcricao(conversa, "reuniao.srt", "Rodolfo: foco na Nuvemshop.")

    assert banco.mensagens(conversa) == [
        {"role": "user", "content": "Quais achados ficaram de fora?", "aviso": "", "legenda": ""},
        {"role": "assistant", "content": "Dois.", "aviso": "", "legenda": "10 tokens"},
    ]
    assert banco.transcricoes(conversa) == {"reuniao.srt": "Rodolfo: foco na Nuvemshop."}
    assert banco.conversa(conversa)["campanha"] == 3


def test_lista_por_projeto_da_mais_recente(banco):
    antiga = banco.criar_conversa("fitame", 3, "antiga")
    nova = banco.criar_conversa("fitame", 3, "nova")
    banco.criar_conversa("ciga", 2, "do ciga")
    banco.adicionar_troca(antiga, "de novo", "ok")  # mexer na antiga a traz para o topo

    titulos = [c["titulo"] for c in banco.conversas("fitame")]
    assert titulos[0] == "antiga" and set(titulos) == {"antiga", "nova"}
    assert [c["id"] for c in banco.conversas("ciga")] != [nova]


def test_renomear_e_excluir_apaga_mensagens_e_transcricoes(banco):
    conversa = banco.criar_conversa("fitame", 3, "x")
    banco.adicionar_troca(conversa, "p", "r")
    banco.adicionar_transcricao(conversa, "a.txt", "texto")

    banco.renomear(conversa, "Reunião de segunda")
    assert banco.conversa(conversa)["titulo"] == "Reunião de segunda"
    banco.renomear(conversa, "   ")  # nome vazio não apaga o título
    assert banco.conversa(conversa)["titulo"] == "Reunião de segunda"

    banco.excluir(conversa)
    assert banco.conversa(conversa) is None
    assert banco.mensagens(conversa) == []
    assert banco.transcricoes(conversa) == {}


def test_transcricao_com_mesmo_nome_substitui(banco):
    conversa = banco.criar_conversa("ciga", 2, "x")
    banco.adicionar_transcricao(conversa, "a.txt", "versão 1")
    banco.adicionar_transcricao(conversa, "a.txt", "versão 2")
    banco.remover_transcricao(conversa, "b.txt")
    assert banco.transcricoes(conversa) == {"a.txt": "versão 2"}


def test_dados_sobrevivem_a_reabrir_o_banco(tmp_path):
    caminho = tmp_path / "conversas.db"
    conversa = Banco(caminho).criar_conversa("fitame", 3, "persistente")
    assert Banco(caminho).conversa(conversa)["titulo"] == "persistente"


def test_titulo_longo_e_cortado():
    titulo = titulo_para("palavra " * 30)
    assert len(titulo) <= 60 and titulo.endswith("…")
