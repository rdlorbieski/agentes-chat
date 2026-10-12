"""Lê as issues de prioridades publicadas pelas campanhas dos agentes.

As issues são montadas por scripts/montar_relatorio.py nos dois repositórios de
agentes: plano com as 3 tarefas, achados descartados e, num bloco <details>,
todos os achados de todos os especialistas.
"""

import re
from dataclasses import dataclass, field

_TAREFA = re.compile(r"^## (\d+)\. (.+?) · ([\d.,]+) h\s*$", re.MULTILINE)
_ACHADO = re.compile(r"^- \*\*`([^`]+)`\*\*", re.MULTILINE)
_HORAS = re.compile(r"\*\*Horas planejadas:\*\* ([\d.,]+) de ([\d.,]+) h")
_COMENTARIO = re.compile(r"<!--.*?-->", re.DOTALL)
_SUMARIO = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)


@dataclass
class Tarefa:
    numero: int
    titulo: str
    horas: str


@dataclass
class Campanha:
    numero: int
    titulo: str
    criada_em: str
    aberta: bool
    url: str
    corpo: str
    tarefas: list = field(default_factory=list)
    total_achados: int = 0
    horas_planejadas: str = ""
    lista_completa: bool = True

    @property
    def data(self):
        return self.criada_em[:10]

    @property
    def rotulo(self):
        situacao = "atual" if self.aberta else "anterior"
        return f"#{self.numero} · {self.data} · {situacao}"


def ler_campanha(issue):
    """Converte uma issue da API do GitHub numa Campanha."""
    corpo = issue.get("body") or ""
    horas = _HORAS.search(corpo)
    return Campanha(
        numero=issue["number"],
        titulo=issue.get("title") or "",
        criada_em=issue.get("created_at") or "",
        aberta=issue.get("state") == "open",
        url=issue.get("html_url") or "",
        corpo=corpo,
        tarefas=[
            Tarefa(int(numero), titulo.strip(), horas_tarefa)
            for numero, titulo, horas_tarefa in _TAREFA.findall(corpo)
        ],
        total_achados=len(_ACHADO.findall(corpo)),
        horas_planejadas=f"{horas.group(1)} de {horas.group(2)} h" if horas else "",
        lista_completa="ficou grande demais para a issue" not in corpo,
    )


def corpo_para_o_modelo(corpo):
    """Corpo da issue sem marcadores HTML, com os achados abertos como uma seção comum."""
    texto = _COMENTARIO.sub("", corpo)
    texto = _SUMARIO.sub(lambda m: f"## {m.group(1).strip()}", texto)
    texto = texto.replace("<details>", "").replace("</details>", "")
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def resumo_curto(campanha):
    """Uma linha por tarefa, para listar campanhas anteriores sem o corpo inteiro."""
    linhas = [f"- {campanha.titulo} ({campanha.data}, issue #{campanha.numero})"]
    linhas += [f"  {t.numero}. {t.titulo} ({t.horas} h)" for t in campanha.tarefas]
    return "\n".join(linhas)
