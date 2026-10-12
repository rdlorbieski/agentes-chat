"""Chamada ao Claude com streaming, para mostrar a resposta enquanto ela é escrita."""

from dataclasses import dataclass

import anthropic

MODELO_PADRAO = "claude-opus-5-5"
ESFORCO_PADRAO = "medium"

# Modelos que aceitam o fallback automático do servidor quando o pedido é recusado.
_COM_FALLBACK = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"}

# US$ por milhão de tokens: entrada, saída, leitura do cache, escrita no cache (5 min).
_PRECOS = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}


class ErroClaude(Exception):
    """Falha ao chamar o Claude, com uma mensagem que dá para mostrar na tela."""


@dataclass
class Uso:
    entrada: int = 0
    saida: int = 0
    cache_lido: int = 0
    cache_escrito: int = 0
    custo_usd: float | None = None
    aviso: str = ""


def _custo(modelo, uso):
    precos = _PRECOS.get(modelo)
    if not precos:
        return None
    entrada, saida, lido, escrito = precos
    return (
        uso.entrada * entrada
        + uso.saida * saida
        + uso.cache_lido * lido
        + uso.cache_escrito * escrito
    ) / 1_000_000


def responder(cliente, system, historico, modelo=MODELO_PADRAO, esforco=ESFORCO_PADRAO, uso=None):
    """Gera os pedaços de texto da resposta. Ao terminar, preenche `uso`."""
    extras = {}
    if modelo in _COM_FALLBACK:
        # Se o modelo recusar por política, o servidor tenta outro modelo na mesma chamada.
        extras = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    try:
        with cliente.beta.messages.stream(
            model=modelo,
            max_tokens=64000,
            system=system,
            messages=historico,
            output_config={"effort": esforco},
            **extras,
        ) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
    except anthropic.AuthenticationError as erro:
        raise ErroClaude("A chave ANTHROPIC_API_KEY foi recusada. Confira os secrets do app.") from erro
    except anthropic.PermissionDeniedError as erro:
        raise ErroClaude(f"A chave não tem permissão para usar {modelo}.") from erro
    except anthropic.RateLimitError as erro:
        raise ErroClaude("Limite de uso da API atingido. Espere um pouco e tente de novo.") from erro
    except anthropic.APIStatusError as erro:
        raise ErroClaude(f"A API do Claude devolveu erro {erro.status_code}: {erro.message}") from erro
    except anthropic.APIConnectionError as erro:
        raise ErroClaude("Não foi possível conectar à API do Claude.") from erro

    if uso is not None:
        u = final.usage
        uso.entrada = u.input_tokens or 0
        uso.saida = u.output_tokens or 0
        uso.cache_lido = u.cache_read_input_tokens or 0
        uso.cache_escrito = u.cache_creation_input_tokens or 0
        uso.custo_usd = _custo(modelo, uso)
        if final.stop_reason == "refusal":
            uso.aviso = "O modelo recusou responder a este pedido."
        elif final.stop_reason == "max_tokens":
            uso.aviso = "A resposta foi cortada por ter ficado longa demais."
