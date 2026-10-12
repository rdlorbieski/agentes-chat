"""Chatbot dos agentes: converse com os relatórios do Fita.me e do CIGA."""

import hmac
from datetime import datetime

import anthropic
import streamlit as st

from chatbot import transcricao
from chatbot.claude import ESFORCO_PADRAO, MODELO_PADRAO, ErroClaude, Uso, responder
from chatbot.config import config, projetos
from chatbot.github import ErroGitHub, GitHub
from chatbot.prompt import montar_system

TIPOS_TRANSCRICAO = ["txt", "srt", "vtt", "md"]
SUGESTOES = [
    "Quais achados de severidade alta ficaram fora das 3 tarefas, e por quê?",
    "Resuma em linguagem simples o que cada especialista encontrou nesta campanha.",
    "O que mudou nas prioridades em relação à campanha anterior?",
    "Com base na transcrição da reunião, quais prioridades você sugere?",
]

st.set_page_config(page_title="Agentes · chat", page_icon="💬", layout="wide")


def exigir_senha():
    senha = config("APP_SENHA")
    if not senha:
        st.error("Configure o secret APP_SENHA para liberar o acesso ao chat.")
        st.stop()
    if st.session_state.get("autenticado"):
        return
    st.title("Agentes · chat")
    with st.form("login"):
        digitada = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        if hmac.compare_digest(digitada.encode(), senha.encode()):
            st.session_state.autenticado = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


@st.cache_data(ttl=600, show_spinner="Lendo as campanhas no GitHub...")
def carregar_projeto(repo):
    github = GitHub(config("GITHUB_TOKEN"))
    return {
        "campanhas": github.campanhas(repo),
        "readme": github.arquivo(repo, "README.md"),
        "conhecido": github.arquivo(repo, "contexto/conhecido.md"),
    }


@st.cache_resource
def cliente_claude():
    chave = config("ANTHROPIC_API_KEY")
    if not chave:
        return None
    return anthropic.Anthropic(api_key=chave)


def estado(nome, padrao):
    """Valor guardado na sessão do navegador, criado na primeira vez."""
    if nome not in st.session_state:
        st.session_state[nome] = padrao
    return st.session_state[nome]


def barra_lateral(lista_projetos):
    with st.sidebar:
        st.header("Agentes · chat")
        chave = st.radio(
            "Projeto",
            list(lista_projetos),
            format_func=lambda k: lista_projetos[k].nome,
            horizontal=True,
        )
        projeto = lista_projetos[chave]
        st.caption(f"Relatórios de `{projeto.repo}`")

        try:
            dados = carregar_projeto(projeto.repo)
        except ErroGitHub as erro:
            st.error(str(erro))
            st.stop()
        if not dados["campanhas"]:
            st.warning("Nenhuma campanha publicada ainda neste repositório.")
            st.stop()

        campanha = st.selectbox(
            "Campanha",
            dados["campanhas"],
            format_func=lambda c: c.rotulo,
            key=f"campanha_{chave}",
        )
        if st.button("Atualizar do GitHub", width="stretch"):
            carregar_projeto.clear()
            st.rerun()

        st.divider()
        transcricoes = area_de_transcricoes(chave)

        st.divider()
        conversa = estado("conversas", {}).setdefault(chave, [])
        if st.button("Nova conversa", width="stretch", disabled=not conversa):
            conversa.clear()
            st.rerun()
        if conversa:
            st.download_button(
                "Baixar a conversa (.md)",
                data=exportar(projeto, campanha, conversa),
                file_name=f"conversa-{chave}-{datetime.now():%Y%m%d-%H%M}.md",
                mime="text/markdown",
                width="stretch",
            )
    return projeto, dados, campanha, transcricoes, conversa


def area_de_transcricoes(chave):
    st.subheader("Reuniões")
    todas = estado("transcricoes", {}).setdefault(chave, {})
    contador = estado("contador_upload", {}).setdefault(chave, 0)
    arquivos = st.file_uploader(
        "Envie transcrições (.txt, .srt, .vtt)",
        type=TIPOS_TRANSCRICAO,
        accept_multiple_files=True,
        key=f"upload_{chave}_{contador}",
    )
    if arquivos:
        for arquivo in arquivos:
            todas[arquivo.name] = transcricao.preparar(arquivo.name, arquivo.getvalue())
        # Troca a chave do campo para esvaziá-lo: os arquivos ficam guardados na sessão.
        st.session_state.contador_upload[chave] = contador + 1
        st.rerun()

    for nome, texto in list(todas.items()):
        coluna_nome, coluna_botao = st.columns([5, 1])
        coluna_nome.caption(f"📄 {nome} · cerca de {len(texto) // 4:,} tokens".replace(",", "."))
        if coluna_botao.button("✕", key=f"remover_{chave}_{nome}", help="Tirar da conversa"):
            del todas[nome]
            st.rerun()
    return todas


def exportar(projeto, campanha, conversa):
    linhas = [f"# Conversa sobre {projeto.nome} · {campanha.titulo}", ""]
    for mensagem in conversa:
        quem = "Você" if mensagem["role"] == "user" else "Assistente"
        linhas += [f"## {quem}", "", mensagem["content"], ""]
    return "\n".join(linhas)


def resumo_da_campanha(campanha):
    st.subheader(campanha.titulo)
    detalhes = [f"Publicada em {campanha.data}", f"{campanha.total_achados} achados"]
    if campanha.horas_planejadas:
        detalhes.append(f"{campanha.horas_planejadas} planejadas")
    st.caption(" · ".join(detalhes) + f" · [ver a issue]({campanha.url})")
    if campanha.tarefas:
        with st.expander("As 3 tarefas escolhidas pelo planejador"):
            for tarefa in campanha.tarefas:
                st.markdown(f"{tarefa.numero}. {tarefa.titulo} · **{tarefa.horas} h**")
    if not campanha.lista_completa:
        st.warning(
            "Nesta campanha a lista completa de achados não coube na issue: o chat só "
            "conhece o plano e os achados descartados."
        )


def conversar(projeto, dados, campanha, transcricoes, conversa):
    cliente = cliente_claude()
    if cliente is None:
        st.error("Configure o secret ANTHROPIC_API_KEY para conversar.")
        st.stop()

    for mensagem in conversa:
        with st.chat_message(mensagem["role"]):
            st.markdown(mensagem["content"])
            if mensagem.get("aviso"):
                st.warning(mensagem["aviso"])
            if mensagem.get("legenda"):
                st.caption(mensagem["legenda"])

    pergunta = st.chat_input(f"Pergunte sobre os agentes do {projeto.nome}...")
    # Uma sugestão clicada chega aqui na execução seguinte, já sem a lista na tela.
    pergunta = pergunta or st.session_state.pop("pergunta_sugerida", None)
    if not conversa and not pergunta:
        st.markdown("**Sugestões para começar**")
        for indice, sugestao in enumerate(SUGESTOES):
            st.button(
                sugestao,
                key=f"sugestao_{indice}",
                on_click=st.session_state.__setitem__,
                args=("pergunta_sugerida", sugestao),
            )
    if not pergunta:
        return

    conversa.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    anteriores = [c for c in dados["campanhas"] if c.numero != campanha.numero]
    system = montar_system(
        projeto, campanha, anteriores, dados["readme"], dados["conhecido"], transcricoes
    )
    uso = Uso()
    with st.chat_message("assistant"):
        try:
            texto = st.write_stream(
                responder(
                    cliente,
                    system,
                    # Só papel e texto: a API não aceita os campos extras da tela.
                    [{"role": m["role"], "content": m["content"]} for m in conversa],
                    modelo=config("MODELO", MODELO_PADRAO),
                    esforco=config("ESFORCO", ESFORCO_PADRAO),
                    uso=uso,
                )
            )
        except ErroClaude as erro:
            conversa.pop()
            st.error(str(erro))
            return

    legenda = f"{uso.entrada + uso.cache_lido + uso.cache_escrito:,} tokens lidos · {uso.saida:,} escritos"
    if uso.custo_usd is not None:
        legenda += f" · ≈ US$ {uso.custo_usd:.3f}"
    texto = texto if isinstance(texto, str) else "".join(texto)
    conversa.append(
        {
            "role": "assistant",
            "content": texto or "(sem resposta)",
            "aviso": uso.aviso,
            "legenda": legenda.replace(",", "."),
        }
    )
    # Redesenha a tela para a barra lateral mostrar o botão de baixar a conversa.
    st.rerun()


def main():
    exigir_senha()
    projeto, dados, campanha, transcricoes, conversa = barra_lateral(projetos())
    resumo_da_campanha(campanha)
    conversar(projeto, dados, campanha, transcricoes, conversa)


main()
