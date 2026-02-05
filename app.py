import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, request
from flask_cors import CORS
import threading
import time
import math
import json
import os
from datetime import datetime
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh
import io

# --- 1. FUNÇÕES DE PERSISTÊNCIA ---
ARQUIVO_CONFIG = 'config_bombas.json'

def carregar_configuracoes():
    padrao = {
        'temp_mancal': 70.0, 'temp_oleo': 65.0, 'vib_rms': 2.8,
        'pressao_max_bar': 10.0, 'pressao_min_bar': 2.0
    }
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, 'r') as f:
                return json.load(f)
        except:
            return padrao
    return padrao

def salvar_configuracoes_arquivo(novos_dados):
    with open(ARQUIVO_CONFIG, 'w') as f:
        json.dump(novos_dados, f)

# --- 2. MEMÓRIA GLOBAL (CACHE RESOURCE) ---
@st.cache_resource
def obter_memoria_global():
    base = {
        "mancal": 0.0, "oleo": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "rms": 0.0, 
        "pressao_bar": 0.0, "historico": [], "alertas": [], 
        "ultimo_visto": None, "online": False
    }
    return {
        "jacutinga_b01": {**base, "nome": "Bomba 01", "local": "Jacutinga"},
        "jacutinga_b02": {**base, "nome": "Bomba 02", "local": "Jacutinga"},
        "jacutinga_b03": {**base, "nome": "Bomba 03", "local": "Jacutinga"}
    }

memoria = obter_memoria_global()

if 'limites' not in st.session_state:
    st.session_state.limites = carregar_configuracoes()

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- 3. PROCESSADOR DE DADOS ---
def processar_entrada(params):
    try:
        id_b = params.get('id')
        # Se vier do Streamlit query_params, pode vir como lista
        if isinstance(id_b, list): id_b = id_b[0]
        
        if id_b in memoria:
            def safe_f(v):
                if isinstance(v, list): v = v[0]
                try: return float(v)
                except: return 0.0

            vx = safe_f(params.get('vx', 0))
            vy = safe_f(params.get('vy', 0))
            vz = safe_f(params.get('vz', 0))
            mancal = safe_f(params.get('mancal', 0))
            oleo = safe_f(params.get('oleo', 0))
            p_bar = safe_f(params.get('pressao', 0))
            
            v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

            memoria[id_b].update({
                'vx': vx, 'vy': vy, 'vz': vz, 'rms': v_rms, 
                'mancal': mancal, 'oleo': oleo, 'pressao_bar': p_bar,
                'ultimo_visto': time.time(), 'online': True
            })
            
            agora = datetime.now()
            ponto = {
                "Data_Hora": agora.strftime("%d/%m/%Y %H:%M:%S"), 
                "Hora": agora.strftime("%H:%M:%S"),
                "RMS_Vibracao": round(v_rms, 3), 
                "Vib_X": vx, "Vib_Y": vy, "Vib_Z": vz,
                "Temp_Mancal": mancal, "Temp_Oleo": oleo,
                "Pressao_Bar": p_bar, "Pressao_MCA": round(p_bar * 10.197, 2)
            }
            memoria[id_b]['historico'].append(ponto)
            if len(memoria[id_b]['historico']) > 1000:
                memoria[id_b]['historico'].pop(0)
            return True
    except Exception as e:
        return False
    return False

# Captura de dados via URL (Ideal para Nuvem/Render)
if st.query_params:
    processar_entrada(st.query_params.to_dict())

# Servidor Flask (Para compatibilidade local)
app_flask = Flask(__name__)
CORS(app_flask)
@app_flask.route('/update', methods=['GET'])
def update():
    if processar_entrada(request.args.to_dict()):
        return "OK", 200
    return "Erro", 400

if 'thread_ativa' not in st.session_state:
    def rodar_flask():
        try:
            # Roda na porta 8080. Se falhar, o Streamlit não morre.
            app_flask.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        except:
            pass
    threading.Thread(target=rodar_flask, daemon=True).start()
    st.session_state['thread_ativa'] = True

# --- 4. INTERFACE ---
st.set_page_config(page_title="Monitor Jacutinga", layout="wide")
st_autorefresh(interval=3000, key="refresh_global")

with st.sidebar:
    st.header("Monitoramento")
    id_sel = st.selectbox("Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']}")
    st.divider()
    aba = option_menu(None, ["Dashboard", "Gráficos", "Alertas", "Configurações"], 
                      icons=["speedometer2", "graph-up", "bell", "gear"], default_index=0)

dados_atual = memoria[id_sel]

if aba == "Dashboard":
    st.title(f"🚀 {dados_atual['nome']}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌡️ Mancal", f"{dados_atual['mancal']:.1f} °C")
    col2.metric("🌡️ Óleo", f"{dados_atual['oleo']:.1f} °C")
    col3.metric("📳 Vibração", f"{dados_atual['rms']:.3f} mm/s²")
    col4.metric("💧 Pressão", f"{dados_atual['pressao_bar'] * 10.197:.1f} MCA")
    
    # Gráficos de Indicador
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        fig_v = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['rms'], title={'text': "RMS Vibração"},
                                       gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "orange"}}))
        st.plotly_chart(fig_v, use_container_width=True)
    with c_g2:
        fig_p = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['pressao_bar'], title={'text': "Pressão (Bar)"},
                                       gauge={'axis': {'range': [0, 15]}, 'bar': {'color': "blue"}}))
        st.plotly_chart(fig_p, use_container_width=True)

elif aba == "Gráficos":
    st.subheader("Tendências em Tempo Real")
    if dados_atual['historico']:
        df = pd.DataFrame(dados_atual['historico'])
        st.plotly_chart(px.line(df, x="Hora", y=["Vib_X", "Vib_Y", "Vib_Z"], title="Vibração (Eixos)"))
        st.plotly_chart(px.line(df, x="Hora", y="Pressao_Bar", title="Pressão (Bar)"))
    else:
        st.info("Aguardando dados...")

elif aba == "Alertas":
    st.subheader("🔔 Histórico de Alertas")
    for a in dados_atual['alertas']:
        st.warning(f"{a['Hora']} - {a['Mensagem']} (Valor: {a['Valor']})")

elif aba == "Configurações":
    st.subheader("Ajustes de Limites")
    with st.form("config"):
        lim_mancal = st.number_input("Limite Mancal (°C)", value=st.session_state.limites['temp_mancal'])
        lim_vib = st.number_input("Limite Vibração (RMS)", value=st.session_state.limites['vib_rms'])
        if st.form_submit_button("Salvar"):
            st.session_state.limites['temp_mancal'] = lim_mancal
            st.session_state.limites['vib_rms'] = lim_vib
            salvar_configuracoes_arquivo(st.session_state.limites)
            st.success("Configurações Atualizadas!")
