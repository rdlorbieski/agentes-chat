"""Conversas salvas em SQLite: mensagens e transcrições de reunião de cada uma."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS conversas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto TEXT NOT NULL,
    campanha INTEGER,
    titulo TEXT NOT NULL,
    criada_em TEXT NOT NULL,
    atualizada_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS conversas_por_projeto ON conversas (projeto, atualizada_em);

CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversa_id INTEGER NOT NULL REFERENCES conversas (id) ON DELETE CASCADE,
    papel TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
    conteudo TEXT NOT NULL,
    aviso TEXT NOT NULL DEFAULT '',
    legenda TEXT NOT NULL DEFAULT '',
    criada_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcricoes (
    conversa_id INTEGER NOT NULL REFERENCES conversas (id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    PRIMARY KEY (conversa_id, nome)
);
"""

TAMANHO_TITULO = 60


def _agora():
    # Microssegundos: duas conversas mexidas no mesmo segundo ainda ficam na ordem certa.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def titulo_para(texto):
    """Título curto a partir da primeira pergunta ou do nome do arquivo."""
    texto = " ".join(texto.split())
    if len(texto) <= TAMANHO_TITULO:
        return texto
    return texto[: TAMANHO_TITULO - 1].rstrip() + "…"


class Banco:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conectar()) as conexao, conexao:
            conexao.execute("PRAGMA journal_mode=WAL")
            conexao.executescript(ESQUEMA)

    def _conectar(self):
        conexao = sqlite3.connect(self.caminho, timeout=10)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        return conexao

    def _executar(self, sql, parametros=()):
        with closing(self._conectar()) as conexao, conexao:
            return conexao.execute(sql, parametros).lastrowid

    def _consultar(self, sql, parametros=()):
        with closing(self._conectar()) as conexao:
            return [dict(linha) for linha in conexao.execute(sql, parametros)]

    # Conversas

    def criar_conversa(self, projeto, campanha, titulo):
        agora = _agora()
        return self._executar(
            "INSERT INTO conversas (projeto, campanha, titulo, criada_em, atualizada_em)"
            " VALUES (?, ?, ?, ?, ?)",
            (projeto, campanha, titulo_para(titulo), agora, agora),
        )

    def conversa(self, conversa_id):
        linhas = self._consultar("SELECT * FROM conversas WHERE id = ?", (conversa_id,))
        return linhas[0] if linhas else None

    def conversas(self, projeto, limite=50):
        """Da mais recente para a mais antiga."""
        return self._consultar(
            "SELECT * FROM conversas WHERE projeto = ? ORDER BY atualizada_em DESC, id DESC LIMIT ?",
            (projeto, limite),
        )

    def renomear(self, conversa_id, titulo):
        titulo = titulo_para(titulo)
        if titulo:
            self._executar("UPDATE conversas SET titulo = ? WHERE id = ?", (titulo, conversa_id))

    def excluir(self, conversa_id):
        self._executar("DELETE FROM conversas WHERE id = ?", (conversa_id,))

    # Mensagens

    def mensagens(self, conversa_id):
        return [
            {"role": m["papel"], "content": m["conteudo"], "aviso": m["aviso"], "legenda": m["legenda"]}
            for m in self._consultar(
                "SELECT * FROM mensagens WHERE conversa_id = ? ORDER BY id", (conversa_id,)
            )
        ]

    def adicionar_troca(self, conversa_id, pergunta, resposta, aviso="", legenda=""):
        """Grava a pergunta e a resposta juntas: uma pergunta sem resposta não fica salva."""
        agora = _agora()
        with closing(self._conectar()) as conexao, conexao:
            conexao.executemany(
                "INSERT INTO mensagens (conversa_id, papel, conteudo, aviso, legenda, criada_em)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (conversa_id, "user", pergunta, "", "", agora),
                    (conversa_id, "assistant", resposta, aviso, legenda, agora),
                ],
            )
            conexao.execute(
                "UPDATE conversas SET atualizada_em = ? WHERE id = ?", (agora, conversa_id)
            )

    # Transcrições

    def transcricoes(self, conversa_id):
        return {
            t["nome"]: t["conteudo"]
            for t in self._consultar(
                "SELECT nome, conteudo FROM transcricoes WHERE conversa_id = ? ORDER BY rowid",
                (conversa_id,),
            )
        }

    def adicionar_transcricao(self, conversa_id, nome, conteudo):
        self._executar(
            "INSERT INTO transcricoes (conversa_id, nome, conteudo) VALUES (?, ?, ?)"
            " ON CONFLICT (conversa_id, nome) DO UPDATE SET conteudo = excluded.conteudo",
            (conversa_id, nome, conteudo),
        )
        self._executar("UPDATE conversas SET atualizada_em = ? WHERE id = ?", (_agora(), conversa_id))

    def remover_transcricao(self, conversa_id, nome):
        self._executar(
            "DELETE FROM transcricoes WHERE conversa_id = ? AND nome = ?", (conversa_id, nome)
        )
