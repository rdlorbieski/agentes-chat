"""Chatbot dos agentes: converse com os relatórios do Fita.me e do CIGA."""

import hmac
from datetime import datetime

import anthropic
import streamlit as st

from chatbot import transcricao
from chatbot.armazenamento import Banco
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


# Acesso


def exigir_login():
    """Usuário e senha simples, só para o chat não ficar aberto na internet."""
    if st.session_state.get("autenticado"):
        return
    usuario_certo = config("APP_USUARIO", "admin")
    senha_certa = config("APP_SENHA", "chat-agentes")

    st.title("Agentes · chat")
    with st.form("login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        usuario_ok = hmac.compare_digest(usuario.strip().encode(), usuario_certo.encode())
        senha_ok = hmac.compare_digest(senha.encode(), senha_certa.encode())
        if usuario_ok and senha_ok:
            st.session_state.autenticado = True
            st.rerun()
        st.error("Usuário ou senha incorretos.")
    st.stop()


# Recursos


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


@st.cache_resource
def abrir_banco(caminho):
    return Banco(caminho)


def banco():
    return abrir_banco(config("DB_PATH", "data/conversas.db"))


# Conversa atual de cada projeto, guardada na sessão do navegador


def conversa_atual(chave):
    return st.session_state.setdefault("conversa_atual", {}).get(chave)


def escolher_conversa(chave, conversa_id, campanha=None):
    st.session_state.setdefault("conversa_atual", {})[chave] = conversa_id
    if campanha is not None:
        # Reabre a conversa na campanha em que ela foi feita.
        st.session_state.setdefault("abrir_campanha", {})[chave] = campanha


def excluir_conversa(chave, conversa_id):
    banco().excluir(conversa_id)
    if conversa_atual(chave) == conversa_id:
        escolher_conversa(chave, None)


def renomear_conversa(conversa_id, campo):
    banco().renomear(conversa_id, st.session_state.get(campo, ""))


# Barra lateral


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

        chave_campanha = f"campanha_{chave}"
        pedida = st.session_state.get("abrir_campanha", {}).pop(chave, None)
        if pedida is not None:
            encontrada = next((c for c in dados["campanhas"] if c.numero == pedida), None)
            if encontrada:
                st.session_state[chave_campanha] = encontrada
        campanha = st.selectbox(
            "Campanha", dados["campanhas"], format_func=lambda c: c.rotulo, key=chave_campanha
        )
        if st.button("Atualizar do GitHub", width="stretch"):
            carregar_projeto.clear()
            st.rerun()

        st.divider()
        area_de_transcricoes(chave, campanha)

        st.divider()
        lista_de_conversas(projeto, chave, campanha)
    return projeto, dados, campanha


def area_de_transcricoes(chave, campanha):
    st.subheader("Reuniões")
    conversa_id = conversa_atual(chave)
    contador = st.session_state.setdefault("contador_upload", {}).setdefault(chave, 0)
    arquivos = st.file_uploader(
        "Envie transcrições (.txt, .srt, .vtt) para esta conversa",
        type=TIPOS_TRANSCRICAO,
        accept_multiple_files=True,
        key=f"upload_{chave}_{contador}",
    )
    if arquivos:
        if conversa_id is None:
            # Enviar uma reunião já abre uma conversa, para a transcrição ficar salva nela.
            conversa_id = banco().criar_conversa(chave, campanha.numero, f"Reunião: {arquivos[0].name}")
            escolher_conversa(chave, conversa_id)
        for arquivo in arquivos:
            banco().adicionar_transcricao(
                conversa_id, arquivo.name, transcricao.preparar(arquivo.name, arquivo.getvalue())
            )
        # Troca a chave do campo para esvaziá-lo: os arquivos já estão no banco.
        st.session_state.contador_upload[chave] = contador + 1
        st.rerun()

    if conversa_id is None:
        return
    for nome, texto in banco().transcricoes(conversa_id).items():
        coluna_nome, coluna_botao = st.columns([5, 1])
        coluna_nome.caption(f"📄 {nome} · cerca de {len(texto) // 4:,} tokens".replace(",", "."))
        if coluna_botao.button("✕", key=f"remover_{conversa_id}_{nome}", help="Tirar da conversa"):
            banco().remover_transcricao(conversa_id, nome)
            st.rerun()


def lista_de_conversas(projeto, chave, campanha):
    st.subheader("Conversas")
    atual = conversa_atual(chave)
    st.button(
        "＋ Nova conversa",
        width="stretch",
        disabled=atual is None,
        on_click=escolher_conversa,
        args=(chave, None),
    )

    conversas = banco().conversas(chave)
    if not conversas:
        st.caption("As conversas ficam salvas aqui.")
    for conversa in conversas:
        coluna_titulo, coluna_menu = st.columns([6, 1])
        coluna_titulo.button(
            conversa["titulo"],
            key=f"abrir_{conversa['id']}",
            type="primary" if conversa["id"] == atual else "secondary",
            width="stretch",
            help=f"Campanha #{conversa['campanha']} · atualizada em {conversa['atualizada_em'][:10]}",
            on_click=escolher_conversa,
            args=(chave, conversa["id"], conversa["campanha"]),
        )
        with coluna_menu.popover("⋮"):
            campo = f"titulo_{conversa['id']}"
            st.text_input("Nome", value=conversa["titulo"], key=campo)
            st.button(
                "Renomear",
                key=f"renomear_{conversa['id']}",
                on_click=renomear_conversa,
                args=(conversa["id"], campo),
            )
            st.button(
                "Excluir conversa",
                key=f"excluir_{conversa['id']}",
                type="primary",
                on_click=excluir_conversa,
                args=(chave, conversa["id"]),
            )

    if atual is not None:
        mensagens = banco().mensagens(atual)
        if mensagens:
            st.download_button(
                "Baixar esta conversa (.md)",
                data=exportar(projeto, campanha, mensagens),
                file_name=f"conversa-{chave}-{datetime.now():%Y%m%d-%H%M}.md",
                mime="text/markdown",
                width="stretch",
            )


def exportar(projeto, campanha, mensagens):
    linhas = [f"# Conversa sobre {projeto.nome} · {campanha.titulo}", ""]
    for mensagem in mensagens:
        quem = "Você" if mensagem["role"] == "user" else "Assistente"
        linhas += [f"## {quem}", "", mensagem["content"], ""]
    return "\n".join(linhas)


# Área principal


def resumo_da_campanha(chave, campanha):
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

    conversa_id = conversa_atual(chave)
    conversa = banco().conversa(conversa_id) if conversa_id else None
    if conversa and conversa["campanha"] not in (None, campanha.numero):
        st.info(
            f"Esta conversa começou na campanha #{conversa['campanha']}. As próximas "
            f"respostas usam a campanha selecionada (#{campanha.numero})."
        )


def conversar(projeto, chave, dados, campanha):
    cliente = cliente_claude()
    if cliente is None:
        st.error("Configure ANTHROPIC_API_KEY para conversar.")
        st.stop()

    conversa_id = conversa_atual(chave)
    if conversa_id is not None and banco().conversa(conversa_id) is None:
        escolher_conversa(chave, None)  # excluída em outra aba
        conversa_id = None
    mensagens = banco().mensagens(conversa_id) if conversa_id else []

    for mensagem in mensagens:
        with st.chat_message(mensagem["role"]):
            st.markdown(mensagem["content"])
            if mensagem.get("aviso"):
                st.warning(mensagem["aviso"])
            if mensagem.get("legenda"):
                st.caption(mensagem["legenda"])

    pergunta = st.chat_input(f"Pergunte sobre os agentes do {projeto.nome}...")
    # Uma sugestão clicada chega aqui na execução seguinte, já sem a lista na tela.
    pergunta = pergunta or st.session_state.pop("pergunta_sugerida", None)
    if not mensagens and not pergunta:
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

    with st.chat_message("user"):
        st.markdown(pergunta)

    transcricoes = banco().transcricoes(conversa_id) if conversa_id else {}
    anteriores = [c for c in dados["campanhas"] if c.numero != campanha.numero]
    system = montar_system(
        projeto, campanha, anteriores, dados["readme"], dados["conhecido"], transcricoes
    )
    # Só papel e texto: a API não aceita os campos extras guardados para a tela.
    historico = [{"role": m["role"], "content": m["content"]} for m in mensagens]
    historico.append({"role": "user", "content": pergunta})

    uso = Uso()
    with st.chat_message("assistant"):
        try:
            texto = st.write_stream(
                responder(
                    cliente,
                    system,
                    historico,
                    modelo=config("MODELO", MODELO_PADRAO),
                    esforco=config("ESFORCO", ESFORCO_PADRAO),
                    uso=uso,
                )
            )
        except ErroClaude as erro:
            st.error(str(erro))
            return

    legenda = f"{uso.entrada + uso.cache_lido + uso.cache_escrito:,} tokens lidos · {uso.saida:,} escritos"
    if uso.custo_usd is not None:
        legenda += f" · ≈ US$ {uso.custo_usd:.3f}"
    texto = texto if isinstance(texto, str) else "".join(texto)

    if conversa_id is None:
        conversa_id = banco().criar_conversa(chave, campanha.numero, pergunta)
        escolher_conversa(chave, conversa_id)
    banco().adicionar_troca(
        conversa_id, pergunta, texto or "(sem resposta)", uso.aviso, legenda.replace(",", ".")
    )
    # Redesenha a tela para a lista de conversas e o botão de baixar ficarem em dia.
    st.rerun()


def main():
    exigir_login()
    projeto, dados, campanha = barra_lateral(projetos())
    resumo_da_campanha(projeto.chave, campanha)
    conversar(projeto, projeto.chave, dados, campanha)


main()
