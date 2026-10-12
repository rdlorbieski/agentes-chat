import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

CORPO_FITAME = """<!-- fitame-sha: api=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa web=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb user=cccccccccccccccccccccccccccccccccccccccc -->
Versão analisada (branch `main`):

- `api` `aaaaaaaa` (commit de 2026-10-12, primeira análise)

**Horas planejadas:** 28 de 30 h · **Custo estimado da campanha:** US$ 6.10

## 1. Desativar peças que sumiram da Nuvemshop · 10 h

**Por que agora:** peças apagadas continuam recomendadas.

## 2. Revogar credenciais do Google versionadas · 6 h

**Por que agora:** refresh token no repositório.

## 3. Escopo de lojista nas validações · 12 h

**Por que agora:** lojista vê clientes de outro.

## Fora desta rodada

- `painel-lojista-2`: depende de decisão de produto.

<details><summary>Todos os achados por área (3)</summary>

### integracao-nuvemshop

Resumo da área.

- **`integracao-nuvemshop-1`** Peça apagada continua ativa (tipo: bug; severidade 4; confiança 5; 10 h)
  - Impacto: consumidor recebe tamanho que não existe.
- **`integracao-nuvemshop-2`** Duplicata de peça sem cor (tipo: bug; severidade 3; confiança 3; 4 h)
  - Impacto: catálogo duplicado.

### painel-lojista

- **`painel-lojista-2`** Papel marca sem tela (tipo: risco; severidade 2; confiança 4; 8 h)
  - Impacto: marca não acessa o painel.

</details>

Execução: https://github.com/rdlorbieski/fitame-agentes/actions/runs/1"""


def issue(numero, corpo=CORPO_FITAME, estado="open", criada="2026-10-12T15:00:00Z", titulo=None):
    return {
        "number": numero,
        "title": titulo or f"Prioridades Fita.me · campanha {numero}",
        "body": corpo,
        "state": estado,
        "created_at": criada,
        "html_url": f"https://github.com/rdlorbieski/fitame-agentes/issues/{numero}",
    }


@pytest.fixture(autouse=True)
def sem_secrets_reais(monkeypatch):
    """Os testes nunca leem o .streamlit/secrets.toml de quem está rodando."""
    import chatbot.config

    monkeypatch.setattr(chatbot.config, "_secret", lambda nome: None)
    for nome in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "APP_USUARIO", "APP_SENHA", "MODELO",
                 "ESFORCO", "REPO_FITAME", "REPO_CIGA", "DB_PATH"):
        monkeypatch.delenv(nome, raising=False)


@pytest.fixture
def issue_fitame():
    return issue(3)
