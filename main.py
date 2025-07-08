import streamlit as st
import pandas as pd
import random
import uuid
import json
import boto3
from datetime import datetime

s3 = boto3.resource('s3',    
                    aws_access_key_id = st.secrets["aws_access_key_id"],
                    aws_secret_access_key = st.secrets["aws_secret_access_key"]
                    )
# Função para carregar dados do Excel
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path)
        return df
    except FileNotFoundError:
        st.error(f"Erro: O arquivo '{file_path}' não foi encontrado.")
        return pd.DataFrame()

# Função para salvar dados no S3
def upload_to_s3(data, bucket_name, file_name):
    try:
        s3object = s3.Object('parlavoice', file_name)
        s3object.put(
            Body=json.dumps(data, ensure_ascii=False, indent=4))
        
        st.success(f"Dados salvos com sucesso no S3: {bucket_name}/{file_name}")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar dados no S3: {e}")
        return False

# Página 1: Formulário de Informações do Celular
def page_one():
    st.title("Formulário de Informações do Celular")

    with st.form("celular_form"):
        modelo_celular = st.text_input("Modelo do Celular", key="modelo_celular")
        sistema_operacional = st.selectbox("Sistema Operacional", ["Android", "iOS"], key="sistema_operacional")
        versao_so = st.text_input("Versão do Sistema Operacional", key="versao_so")
        
        estados_brasil = [
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", 
            "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
        ]
        estado_origem = st.selectbox("Estado de Origem", estados_brasil, key="estado_origem")
        
        sexo = st.radio("Sexo", ["M", "F"], key="sexo")
        idade = st.number_input("Idade", min_value=0, max_value=120, value=18, key="idade")
        
        submitted = st.form_submit_button("Próximo")
        
        if submitted:
            st.session_state.form_data = {
                "modelo_celular": modelo_celular,
                "sistema_operacional": sistema_operacional,
                "versao_so": versao_so,
                "estado_origem": estado_origem,
                "sexo": sexo,
                "idade": idade
            }
            st.session_state.page = "page_two"
            st.rerun()

# Página 2: Teste de Fala
def page_two():
    st.title("Teste de Transcrição")
    st.markdown("## Leia exatamente o texto abaixo usando o microfone do seu teclado")

    # Carregar dados do Excel
    df = load_data("./textos_para_fala.xlsx") # Certifique-se de que este arquivo existe
    if df.empty:
        st.warning("Não foi possível carregar os textos para o teste de fala.")
        return

    if 'current_text' not in st.session_state:
        st.session_state.current_text = ""
        st.session_state.current_speed = ""
        st.session_state.transcriptions = []
        st.session_state.round_count = 0
        st.session_state.unique_id = str(uuid.uuid4()) # ID único para o teste

    velocidades = ["Falar Pausadamente", "Falar Normal", "Falar Rápido"]

    def new_round():
        st.session_state.current_text = random.choice(df["Texto"].tolist())
        st.session_state.current_speed = random.choice(velocidades)
        if "transcription_input" in st.session_state:
            del st.session_state["transcription_input"]

        st.session_state["transcription_input"] = "" # Limpa o campo de transcrição
        st.session_state.round_count += 1

    if st.session_state.current_text == "":
        new_round()

    st.markdown(f"## <p style='text-align: center;'>{st.session_state.current_text}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; font-size: 1.8em; color: gray;'>Velocidade: {st.session_state.current_speed}</p>", unsafe_allow_html=True)

    transcription = st.text_area("Transcreva o áudio aqui:", key="transcription_input", value=st.session_state.get("transcription_input", ""))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Gravar e Próxima Rodada"):
            if transcription:
                st.session_state.transcriptions.append({
                    "round": st.session_state.round_count,
                    "model_text": st.session_state.current_text,
                    "user_transcription": transcription,
                    "speech_speed": st.session_state.current_speed,
                    "timestamp": datetime.now().isoformat()
                })
                new_round()
                st.rerun()
            else:
                st.warning("Por favor, transcreva o texto antes de ir para a próxima rodada.")
    with col2:
        if st.button("Finalizar Teste e Submeter"):
            # Coletar todos os dados para o JSON
            final_data = {
                "test_id": st.session_state.unique_id,
                "form_data": st.session_state.get("form_data", {}),
                "transcription_rounds": st.session_state.transcriptions,
                "test_completion_timestamp": datetime.now().isoformat()
            }

            # Salvar no S3
            bucket_name = "parla-speech-test-data" # Substitua pelo nome do seu bucket S3
            file_name = f"{st.session_state.unique_id}.json"
            
            if upload_to_s3(final_data, bucket_name, file_name):
                st.success("Teste finalizado e dados submetidos com sucesso!")
                st.session_state.clear() # Limpa o estado para um novo teste
                st.session_state.page = "page_one" # Volta para a primeira página
                st.rerun()
            else:
                st.error("Falha ao submeter os dados. Tente novamente.")

    st.markdown(f"---")
    st.write(f"Rodadas completadas: {len(st.session_state.transcriptions)}")

def main():
    if 'page' not in st.session_state:
        st.session_state.page = "page_one"

    if st.session_state.page == "page_one":
        page_one()
    elif st.session_state.page == "page_two":
        page_two()

if __name__ == "__main__":
    main()
