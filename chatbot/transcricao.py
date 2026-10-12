"""Limpa transcrições de reunião (.srt, .vtt, .txt) antes de mandá-las ao modelo.

Legendas repetem números de sequência, marcas de tempo e, com frequência, a
mesma frase em blocos seguidos. Nada disso ajuda a entender a reunião e tudo
isso custa tokens.
"""

import re

_TEMPO = re.compile(
    r"^\s*\d{1,2}:\d{2}(:\d{2})?[.,]\d{1,3}\s*-->\s*\d{1,2}:\d{2}(:\d{2})?[.,]\d{1,3}.*$"
)
_SEQUENCIA = re.compile(r"^\s*\d+\s*$")
_TAG_VTT = re.compile(r"</?[^>]+>")


def decodificar(dados):
    """Texto do arquivo, aceitando UTF-8 (com ou sem BOM) e o padrão antigo do Windows."""
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("utf-8", errors="replace")


def limpar_legenda(texto):
    """Só as falas de um .srt ou .vtt, uma por linha, sem repetições seguidas."""
    falas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha == "WEBVTT" or linha.startswith(("NOTE", "STYLE", "Kind:", "Language:")):
            continue
        if _TEMPO.match(linha) or _SEQUENCIA.match(linha):
            continue
        linha = _TAG_VTT.sub("", linha).strip()
        if linha and (not falas or falas[-1] != linha):
            falas.append(linha)
    return "\n".join(falas)


def preparar(nome, dados):
    """Texto pronto para o modelo a partir do nome e do conteúdo do arquivo enviado."""
    texto = decodificar(dados)
    if nome.lower().endswith((".srt", ".vtt")):
        return limpar_legenda(texto)
    return re.sub(r"\n{3,}", "\n\n", texto.replace("\r\n", "\n")).strip()
