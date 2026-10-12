"""Monta o system prompt: instruções, dados do projeto e transcrições de reunião.

A ordem importa para o cache do prompt. Os blocos mais estáveis vêm primeiro
(instruções, depois os dados da campanha), e as transcrições, que mudam quando
você envia um arquivo novo, ficam por último. Assim, subir uma transcrição só
refaz o cache do último bloco.
"""

from .campanhas import corpo_para_o_modelo, resumo_curto

INSTRUCOES = """\
Você é o assistente do responsável técnico pelo projeto {nome}. {descricao}

Um sistema de agentes analisa cada versão nova do código do {nome}: vários
especialistas procuram falhas, cada um na sua área, e um planejador escolhe as
3 tarefas prioritárias que cabem no orçamento de horas. O resultado de cada
análise (uma "campanha") é publicado como uma issue. Você recebe abaixo a
campanha escolhida na tela, com o plano e a lista completa de achados de todos
os especialistas, as campanhas anteriores resumidas, a descrição dos agentes e
o arquivo em que o time registra o que já foi resolvido, o que está em
andamento e o que ainda depende de decisão.

Você conversa com o responsável técnico sobre esse material. Ele pode
perguntar sobre qualquer achado, não só as 3 tarefas escolhidas, pedir
comparações entre campanhas e enviar transcrições de reuniões.

Como responder:
- Responda em português, direto ao ponto.
- Baseie-se no material recebido. Cite os achados pelo id (por exemplo
  `integracao-nuvemshop-2`) e as tarefas pelo número e título, para ele achar
  na issue.
- Separe o que está no relatório do que é avaliação sua. Você não tem acesso
  ao código além dos trechos citados no relatório: quando a resposta depender
  do código, diga o que precisaria ser conferido e onde.
- Se a informação não estiver no material, diga que não está. Não invente
  achados, horas, arquivos ou decisões.
- Quando houver transcrição de reunião, use-a como a fonte do que o time
  decidiu, priorizou ou descartou. Aponte quando a reunião contradiz o
  relatório (algo dado como resolvido que o relatório ainda aponta, por
  exemplo).

Quando ele pedir para definir ou rever prioridades:
- Use o orçamento que ele indicar. Se não indicar, use o mesmo da campanha
  (3 tarefas, somando no máximo as horas planejadas dela) e diga que usou.
- Considere todos os achados, não só os 3 escolhidos pelo planejador, e o que
  a reunião decidiu.
- Para cada tarefa: título, achados relacionados (ids), horas estimadas e o
  motivo da prioridade em uma ou duas frases. Mostre a soma das horas.
- Liste em seguida o que ficou de fora e por quê, de forma curta.
- Se a reunião registrou algo resolvido, em andamento ou uma decisão, ofereça
  no fim um trecho pronto para colar no arquivo contexto/conhecido.md do
  repositório de agentes, no mesmo formato das seções dele, para que a próxima
  campanha leve isso em conta.
- Você não publica nada e não altera nenhum repositório: tudo fica nesta
  conversa. Não diga que publicou, salvou ou enviou algo.
"""


def _bloco(texto, cache=False):
    bloco = {"type": "text", "text": texto}
    if cache:
        bloco["cache_control"] = {"type": "ephemeral"}
    return bloco


def montar_system(projeto, campanha, anteriores, descricao_agentes, conhecido, transcricoes):
    """Lista de blocos do system prompt. `transcricoes` é um dict nome -> texto."""
    partes = [
        f"# Campanha escolhida: {campanha.titulo}",
        f"Issue #{campanha.numero}, publicada em {campanha.data}: {campanha.url}",
        "",
        corpo_para_o_modelo(campanha.corpo),
    ]
    if not campanha.lista_completa:
        partes += [
            "",
            "Atenção: nesta campanha a lista completa de achados não coube na issue. "
            "Você só tem o plano e os achados descartados; avise isso se perguntarem "
            "sobre outros achados.",
        ]
    if anteriores:
        partes += ["", "# Campanhas anteriores (só as tarefas escolhidas)", ""]
        partes += [resumo_curto(c) for c in anteriores]
    partes += [
        "",
        "# Os agentes (README do repositório de agentes)",
        "",
        descricao_agentes.strip() or "(não foi possível ler o README)",
        "",
        "# O que o time já sabe (contexto/conhecido.md)",
        "",
        conhecido.strip() or "(arquivo não encontrado)",
    ]

    blocos = [
        _bloco(INSTRUCOES.format(nome=projeto.nome, descricao=projeto.descricao)),
        _bloco("\n".join(partes), cache=True),
    ]

    if transcricoes:
        texto = ["# Transcrições de reunião enviadas nesta conversa"]
        for nome, conteudo in transcricoes.items():
            texto += ["", f"## Arquivo: {nome}", "", conteudo]
        blocos.append(_bloco("\n".join(texto), cache=True))
    return blocos
