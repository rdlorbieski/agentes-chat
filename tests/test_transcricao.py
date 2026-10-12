from chatbot.transcricao import decodificar, limpar_legenda, preparar

SRT = """1
00:00:01,000 --> 00:00:04,000
Rodolfo: vamos priorizar a Nuvemshop.

2
00:00:04,500 --> 00:00:06,000
Rodolfo: vamos priorizar a Nuvemshop.

3
00:00:06,500 --> 00:00:09,000
Gabriel: o token do Google já foi revogado.
"""

VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000 align:start
<v Ana>Precisamos de testes no painel.</v>

00:00:03.500 --> 00:00:05.000
<v Ana>Precisamos de testes no painel.</v>
"""


def test_srt_fica_so_com_as_falas_sem_repetir():
    assert limpar_legenda(SRT) == (
        "Rodolfo: vamos priorizar a Nuvemshop.\nGabriel: o token do Google já foi revogado."
    )


def test_vtt_tira_cabecalho_tempos_e_tags():
    assert limpar_legenda(VTT) == "Precisamos de testes no painel."


def test_preparar_escolhe_pela_extensao():
    assert preparar("reuniao.SRT", SRT.encode()).startswith("Rodolfo:")
    texto = "Pauta\r\n\r\n\r\n\r\nItem 1"
    assert preparar("ata.txt", texto.encode()) == "Pauta\n\nItem 1"


def test_decodifica_utf8_com_bom_e_windows():
    assert decodificar("﻿reunião".encode("utf-8")) == "reunião"
    assert decodificar("reunião".encode("cp1252")) == "reunião"
