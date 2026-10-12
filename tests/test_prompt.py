from chatbot.campanhas import ler_campanha
from chatbot.config import projetos
from chatbot.prompt import montar_system

from conftest import CORPO_FITAME, issue


def _system(transcricoes=None):
    atual = ler_campanha(issue(3))
    anterior = ler_campanha(issue(2, estado="closed", criada="2026-10-05T15:00:00Z"))
    return montar_system(
        projetos()["fitame"], atual, [anterior], "# fitame-agentes", "## Em andamento", transcricoes or {}
    )


def test_ordem_dos_blocos_e_cache():
    blocos = _system({"reuniao.srt": "Rodolfo: prioridade é a Nuvemshop."})

    assert len(blocos) == 3
    assert "Fita.me" in blocos[0]["text"] and "cache_control" not in blocos[0]
    assert blocos[1]["cache_control"] == {"type": "ephemeral"}
    assert "integracao-nuvemshop-2" in blocos[1]["text"]
    assert "# Campanhas anteriores" in blocos[1]["text"]
    assert "## Em andamento" in blocos[1]["text"]
    assert blocos[2]["cache_control"] == {"type": "ephemeral"}
    assert "## Arquivo: reuniao.srt" in blocos[2]["text"]


def test_sem_transcricao_nao_cria_bloco():
    assert len(_system()) == 2


def test_dados_nao_mudam_entre_chamadas():
    # O cache do prompt depende de o prefixo ser idêntico byte a byte.
    assert _system() == _system()


def test_avisa_quando_a_lista_de_achados_nao_coube():
    corpo = CORPO_FITAME + "\nA lista completa de achados ficou grande demais para a issue."
    campanha = ler_campanha(issue(4, corpo=corpo))
    blocos = montar_system(projetos()["fitame"], campanha, [], "", "", {})
    assert "não coube na issue" in blocos[1]["text"]
