# agentes-chat

Chat para conversar com os relatórios dos agentes de qualidade do
**Fita.me** (`fitame-agentes`) e do **CIGA** (`ciga-agentes`).

- Escolha o projeto e a campanha (cada issue de prioridades é uma campanha).
- Pergunte sobre **qualquer achado** de qualquer especialista, não só as 3
  tarefas escolhidas pelo planejador. Compare com campanhas anteriores.
- Envie transcrições de reunião (`.txt`, `.srt`, `.vtt`) e peça para o chat
  definir ou rever prioridades com base no que foi conversado.
- Baixe a conversa em Markdown.

O chat **só lê**. Ele não publica issue, não altera repositório e não guarda
nada: a conversa e as transcrições ficam só na aba do navegador e somem ao
recarregar a página (baixe a conversa antes, se quiser guardar). Quando a
reunião registra algo resolvido ou decidido, o chat oferece um trecho pronto
para você colar no `contexto/conhecido.md` do repositório de agentes.

## O que o chat recebe

A cada pergunta, o Claude recebe:

1. A campanha escolhida inteira: o plano, os achados descartados e a lista de
   todos os achados de todos os especialistas, com severidade, confiança,
   horas e impacto.
2. As tarefas das campanhas anteriores (até 20).
3. O `README.md` (o que cada agente olha) e o `contexto/conhecido.md` do
   repositório de agentes.
4. As transcrições enviadas nesta conversa.

Ele **não** lê o código do Fita.me nem do CIGA: conhece só os trechos que os
agentes citaram no relatório, e diz quando uma resposta depende de conferir
o código. Se a lista de achados de uma campanha não coube na issue (corpo
acima de 60 mil caracteres), o chat avisa que só conhece o plano.

## Publicar no Streamlit Community Cloud (uma vez)

### 1. Enviar este repositório para o GitHub

Crie um repositório **privado** vazio (ex.: `agentes-chat`) e rode:

```bash
cd /c/Users/Usuario/PycharmProjects/agentes-chat
git add -A
git commit -m "Chat dos agentes"
git remote add origin git@github.com:rdlorbieski/agentes-chat.git
git push -u origin main
```

### 2. Criar o token de leitura do GitHub

Em https://github.com/settings/personal-access-tokens/new:

- **Repository access:** *Only select repositories*, marque `fitame-agentes`
  e `ciga-agentes`.
- **Permissions → Repository permissions:** adicione **Issues** e
  **Contents**, os dois em *Read-only*.

### 3. Criar a chave da API do Claude

Em https://console.anthropic.com, crie um workspace só para o chat, com
**limite de gasto mensal** (ex.: US$ 20), e uma chave de API nesse
workspace. O chat é pago por uso (veja Custos).

### 4. Publicar

1. Entre em https://share.streamlit.io com a sua conta do GitHub e autorize o
   acesso aos repositórios privados.
2. **Create app → Deploy a public app from GitHub**: repositório
   `rdlorbieski/agentes-chat`, branch `main`, arquivo `app.py`.
3. Em **Advanced settings**: Python **3.12**, e no campo **Secrets** cole o
   conteúdo de `.streamlit/secrets.toml.example` com os valores de verdade:
   o token do passo 2, a chave do passo 3 e uma senha longa em `APP_SENHA`.
4. **Deploy.**

### 5. Fechar o acesso

O app sai com um endereço `https://...streamlit.app`. Para ninguém além de
você abrir:

- Em **Settings → Sharing** do app, escolha *Only specific people can view
  this app* e adicione o seu e-mail. O Streamlit pede login antes de mostrar
  o app.
- Além disso, o próprio app pede a senha `APP_SENHA`.

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
metade, use `MODELO = "claude-sonnet-5-5"` nos secrets. Se o modelo recusar um
pedido por política de segurança, o servidor tenta outro modelo na mesma
chamada (`fallbacks: "default"`).

## Rodar no seu computador

```bash
cd /c/Users/Usuario/PycharmProjects/agentes-chat
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Preencha o `.streamlit/secrets.toml` e rode:

```bash
.venv/Scripts/python -m streamlit run app.py
```

Testes (não chamam o GitHub nem o Claude):

```bash
.venv/Scripts/python -m pytest -q
```

## Estrutura

| Arquivo | O que faz |
|---|---|
| `app.py` | A tela: senha, projeto, campanha, transcrições e o chat |
| `chatbot/github.py` | Lê as issues de prioridades e os arquivos do repositório de agentes |
| `chatbot/campanhas.py` | Extrai tarefas, horas e achados de cada issue |
| `chatbot/transcricao.py` | Limpa `.srt`, `.vtt` e `.txt` (tempos, numeração, falas repetidas) |
| `chatbot/prompt.py` | Instruções e montagem do contexto, na ordem que aproveita o cache |
| `chatbot/claude.py` | Chamada ao Claude com streaming, erros e custo estimado |
| `chatbot/config.py` | Secrets e os dois projetos |

Para acrescentar um terceiro projeto, inclua-o em `projetos()` em
`chatbot/config.py`. Basta o repositório de agentes publicar issues com a
label `prioridades` no mesmo formato.
