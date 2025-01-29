from pathlib import Path
from datetime import datetime
import time
import queue

from streamlit_webrtc import WebRtcMode, webrtc_streamer
import streamlit as st

import pydub
import openai
from dotenv import load_dotenv, find_dotenv

PASTA_ARQUIVOS = Path(__file__).parent / "arquivos"
PASTA_ARQUIVOS.mkdir(exist_ok=True)

_ = load_dotenv(find_dotenv())


def salva_arquivo(caminho_arquivo, conteudo):
    with open(caminho_arquivo, "w") as f:
        f.write(conteudo)


def le_arquivo(caminho_arquivo):
    if caminho_arquivo.exists():
        with open(caminho_arquivo, encoding="latin-1") as f:
            return f.read()
    else:
        return ""


def listar_reunioes():
    lista_reunioes = PASTA_ARQUIVOS.glob("*")
    lista_reunioes = list(lista_reunioes)
    lista_reunioes.sort(reverse=True)
    reunioes_dict = {}
    for pasta_reuniao in lista_reunioes:
        data_reuniao = pasta_reuniao.stem
        ano, mes, dia, hora, min, seg = data_reuniao.split("_")
        reunioes_dict[data_reuniao] = f"{ano}/{mes}/{dia} {hora}:{min}:{seg}"
    return reunioes_dict


# OPENAI UTILS =====================
client = openai.OpenAI()


def transcreve_audio(caminho_audio, language="pt", response_format="text"):
    with open(caminho_audio, "rb") as arquivo_audio:
        transcricao = client.audio.transcriptions.create(
            model="whisper-1",
            language=language,
            response_format=response_format,
            file=arquivo_audio,
        )
    return transcricao


def chat_openai(
    mensagem,
    modelo="gpt-3.5-turbo-1106",
):
    mensagens = [{"role": "user", "content": mensagem}]
    resposta = client.chat.completions.create(
        model=modelo,
        messages=mensagens,
    )
    return resposta.choices[0].message.content


# TAB GRAVA REUNIÃO =====================


def adiciona_chunck_audio(frames_de_audio, audio_chunck):
    for frame in frames_de_audio:
        sound = pydub.AudioSegment(
            data=frame.to_ndarray().tobytes(),
            sample_width=frame.format.bytes,
            frame_rate=frame.sample_rate,
            channels=len(frame.layout.channels),
        )
        audio_chunck += sound
    return audio_chunck


def tab_grava_reuniao():
    webrtx_ctx = webrtc_streamer(
        key="recebe_audio",
        mode=WebRtcMode.SENDONLY,
        audio_receiver_size=1024,
        media_stream_constraints={"video": False, "audio": True},
    )

    if not webrtx_ctx.state.playing:
        return

    container = st.empty()
    container.markdown("Comece a falar")
    pasta_reuniao = PASTA_ARQUIVOS / datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    pasta_reuniao.mkdir()

    ultima_trancricao = time.time()
    audio_completo = pydub.AudioSegment.empty()
    audio_chunck = pydub.AudioSegment.empty()
    transcricao = ""

    while True:
        if webrtx_ctx.audio_receiver:
            try:
                frames_de_audio = webrtx_ctx.audio_receiver.get_frames(timeout=1)
            except queue.Empty:
                time.sleep(0.1)
                continue
            audio_completo = adiciona_chunck_audio(frames_de_audio, audio_completo)
            audio_chunck = adiciona_chunck_audio(frames_de_audio, audio_chunck)
            if len(audio_chunck) > 0:
                audio_completo.export(pasta_reuniao / "audio.mp3")
                agora = time.time()
                if agora - ultima_trancricao > 5:
                    ultima_trancricao = agora
                    audio_chunck.export(pasta_reuniao / "audio_temp.mp3")
                    transcricao_chunck = transcreve_audio(
                        pasta_reuniao / "audio_temp.mp3"
                    )
                    transcricao += transcricao_chunck
                    salva_arquivo(pasta_reuniao / "transcricao.txt", transcricao)
                    container.markdown(transcricao)
                    audio_chunck = pydub.AudioSegment.empty()
        else:
            break


# TAB SELEÇÃO REUNIÃO =====================
def tab_selecao_reuniao():
    reunioes_dict = listar_reunioes()
    if len(reunioes_dict) > 0:
        reuniao_selecionada = st.selectbox(
            "Selecione uma reunião", list(reunioes_dict.values())
        )
        st.divider()
        reuniao_data = [
            key for key, value in reunioes_dict.items() if value == reuniao_selecionada
        ][0]
        pasta_reuniao = PASTA_ARQUIVOS / reuniao_data
        if not (pasta_reuniao / "titulo.txt").exists():
            st.warning("Adicione um título")
            titulo_reuniao = st.text_input("Título da reunião")
            st.button(
                "Salvar", on_click=salvar_titulo, args=(pasta_reuniao, titulo_reuniao)
            )
        else:
            titulo = le_arquivo(pasta_reuniao / "titulo.txt")
            transcricao = le_arquivo(pasta_reuniao / "transcricao.txt")
            st.markdown(f"## {titulo}")
            st.markdown(f"Transcricao: {transcricao}")


def salvar_titulo(pasta_reuniao, titulo):
    salva_arquivo(pasta_reuniao / "titulo.txt", titulo)


# MAIN =====================
def main():
    st.header("Bem-vindo ao MeetGPT 🎙️", divider=True)
    tab_gravar, tab_selecao = st.tabs(["Gravar Reunião", "Ver transcrições salvas"])
    with tab_gravar:
        tab_grava_reuniao()
    with tab_selecao:
        tab_selecao_reuniao()


if __name__ == "__main__":
    main()
