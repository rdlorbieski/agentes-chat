from chatbot.campanhas import corpo_para_o_modelo, ler_campanha, resumo_curto


def test_le_tarefas_achados_e_horas(issue_fitame):
    campanha = ler_campanha(issue_fitame)

    assert [t.titulo for t in campanha.tarefas] == [
        "Desativar peças que sumiram da Nuvemshop",
        "Revogar credenciais do Google versionadas",
        "Escopo de lojista nas validações",
    ]
    assert [t.horas for t in campanha.tarefas] == ["10", "6", "12"]
    assert campanha.total_achados == 3
    assert campanha.horas_planejadas == "28 de 30 h"
    assert campanha.aberta
    assert campanha.lista_completa
    assert campanha.rotulo == "#3 · 2026-10-12 · atual"


def test_corpo_para_o_modelo_tira_html_e_mantem_achados(issue_fitame):
    texto = corpo_para_o_modelo(issue_fitame["body"])

    assert "<!--" not in texto
    assert "<details>" not in texto and "</details>" not in texto
    assert "## Todos os achados por área (3)" in texto
    assert "`integracao-nuvemshop-2`" in texto


def test_campanha_com_lista_cortada(issue_fitame):
    issue_fitame["body"] += (
        "\nA lista completa de achados ficou grande demais para a issue; está no artefato da execução."
    )
    assert not ler_campanha(issue_fitame).lista_completa


def test_issue_sem_corpo_nao_quebra():
    campanha = ler_campanha({"number": 1, "body": None, "state": "closed"})
    assert campanha.tarefas == [] and campanha.total_achados == 0


def test_resumo_curto_lista_as_tarefas(issue_fitame):
    resumo = resumo_curto(ler_campanha(issue_fitame))
    assert "issue #3" in resumo
    assert "2. Revogar credenciais do Google versionadas (6 h)" in resumo
