# agentes-chat

Chat para conversar com os relatórios dos agentes de qualidade do
**Fita.me** (`fitame-agentes`) e do **CIGA** (`ciga-agentes`).

Endereço: **https://chat-agentes.lorbieski.com.br**

- Escolha o projeto e a campanha (cada issue de prioridades é uma campanha).
- Pergunte sobre **qualquer achado** de qualquer especialista, não só as 3
  tarefas escolhidas pelo planejador. Compare com campanhas anteriores.
- Envie transcrições de reunião (`.txt`, `.srt`, `.vtt`) e peça para o chat
  definir ou rever prioridades com base no que foi conversado.
- As conversas ficam salvas (SQLite), com as transcrições de cada uma: reabra,
  renomeie, exclua ou baixe em Markdown pela barra lateral.

O chat **só lê** o GitHub. Ele não publica issue e não altera nenhum
repositório. Quando a reunião registra algo resolvido ou decidido, ele oferece
um trecho pronto para você colar no `contexto/conhecido.md` do repositório de
agentes.

## O que o chat recebe

A cada pergunta, o Claude recebe:

1. A campanha escolhida inteira: o plano, os achados descartados e a lista de
   todos os achados de todos os especialistas, com severidade, confiança,
   horas e impacto.
2. As tarefas das campanhas anteriores (até 20).
3. O `README.md` (o que cada agente olha) e o `contexto/conhecido.md` do
   repositório de agentes.
4. As transcrições salvas na conversa aberta.
5. O histórico da conversa aberta.

Ele **não** lê o código do Fita.me nem do CIGA: conhece só os trechos que os
agentes citaram no relatório, e diz quando uma resposta depende de conferir
o código. Se a lista de achados de uma campanha não coube na issue (corpo
acima de 60 mil caracteres), o chat avisa que só conhece o plano.

## Acesso

Login simples, só para o chat não ficar aberto na internet: usuário e senha
vêm de `APP_USUARIO` e `APP_SENHA` no `.env`. Sem eles, vale **`admin` /
`chat-agentes`**. Troque no `.env` da VPS. O login vale para a aba aberta:
recarregar a página pede de novo.

## Deploy na VPS

Mesmo modelo do `fitame-validator-user`: um container na network `edge`, sem
porta pública, com o Caddy da VPS fazendo o HTTPS e encaminhando o domínio.

| | |
|---|---|
| Domínio | `chat-agentes.lorbieski.com.br` |
| Container | `lorbieski-chat-agentes`, porta interna `8501` |
| Conversas | volume Docker `conversas`, montado em `/app/data` |

### Primeira vez

1. **DNS:** crie um registro `A` de `chat-agentes.lorbieski.com.br` para o IP
   da VPS.
2. **Caddy:** cole o bloco de [`infra/Caddyfile.trecho`](infra/Caddyfile.trecho)
   no `Caddyfile` do Caddy da VPS e reinicie o Caddy
   (`docker restart edge_caddy`, no modelo do `infra-edge`). O certificado
   HTTPS sai sozinho no primeiro acesso.
3. **Código e segredos**, na VPS:

```bash
git clone git@github.com:rdlorbieski/agentes-chat.git
cd agentes-chat
cp .env.example .env
nano .env
```

   No `.env`, preencha:
   - `ANTHROPIC_API_KEY`: chave criada em https://console.anthropic.com, de
     preferência num workspace com limite de gasto mensal.
   - `GITHUB_TOKEN`: token criado em
     https://github.com/settings/personal-access-tokens/new, com acesso só a
     `fitame-agentes` e `ciga-agentes` e as permissões **Issues** e
     **Contents** em *Read-only*.
   - `APP_USUARIO` e `APP_SENHA`: o login do chat.

4. **Subir:**

```bash
bash deploy_prod.sh
```

### Atualizar

Depois de um push na `main`, na VPS:

```bash
cd agentes-chat && bash deploy_prod.sh
```

As conversas ficam no volume `conversas` e não se perdem no deploy. Para
fazer uma cópia do banco:

```bash
docker cp lorbieski-chat-agentes:/app/data/conversas.db ./conversas-$(date +%F).db
```

## Custos

Pagos na API do Claude, por pergunta. Com o padrão (`claude-opus-5-5`,
esforço `medium`) e uma campanha de uns 25 mil tokens:

- **Primeira pergunta** (ou depois de 5 minutos parado): cerca de US$ 0,15 a
  0,20, porque o relatório é gravado no cache.
- **Perguntas seguintes, dentro de 5 minutos:** cerca de US$ 0,03 a 0,05 cada,
  com o relatório lido do cache a 5% do preço normal. O que pesa é a resposta
  e o raciocínio do modelo, cobrados como saída.
- **Transcrição de reunião:** uma reunião de 1 hora soma uns 15 mil tokens.

O custo estimado de cada resposta aparece embaixo dela. Para gastar cerca da
metade, use `MODELO=claude-sonnet-5-5` no `.env`. Se o modelo recusar um
pedido por política de segurança, o servidor tenta outro modelo na mesma
chamada (`fallbacks: "default"`).

## Rodar no seu computador

Com Docker, igual à VPS mas com a porta aberta em http://localhost:8501:

```bash
cp .env.example .env
docker compose --profile local up --build
```

Sem Docker:

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
.venv/Scripts/python -m streamlit run app.py
```

Testes (não chamam o GitHub nem o Claude e não leem os seus segredos):

```bash
.venv/Scripts/python -m pytest -q
```

## Estrutura

| Arquivo | O que faz |
|---|---|
| `app.py` | A tela: login, projeto, campanha, reuniões, conversas e o chat |
| `chatbot/armazenamento.py` | SQLite com conversas, mensagens e transcrições |
| `chatbot/github.py` | Lê as issues de prioridades e os arquivos do repositório de agentes |
| `chatbot/campanhas.py` | Extrai tarefas, horas e achados de cada issue |
| `chatbot/transcricao.py` | Limpa `.srt`, `.vtt` e `.txt` (tempos, numeração, falas repetidas) |
| `chatbot/prompt.py` | Instruções e montagem do contexto, na ordem que aproveita o cache |
| `chatbot/claude.py` | Chamada ao Claude com streaming, erros e custo estimado |
| `chatbot/config.py` | Configuração e os dois projetos |
| `Dockerfile`, `docker-compose.yml`, `deploy_prod.sh` | Deploy na VPS |
| `infra/Caddyfile.trecho` | Bloco do Caddy para o domínio |

Para acrescentar um terceiro projeto, inclua-o em `projetos()` em
`chatbot/config.py`. Basta o repositório de agentes publicar issues com a
label `prioridades` no mesmo formato.
