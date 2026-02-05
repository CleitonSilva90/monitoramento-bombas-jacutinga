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

# --- 2. MEMÓRIA GLOBAL (CRÍTICO PARA FUNCIONAR) ---
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

# --- 3. SERVIDOR FLASK (INTEGRADO) ---
app_flask = Flask(__name__)
CORS(app_flask)

@app_flask.route('/update', methods=['GET'])
def update():
    # Acessa a memória global definida no Streamlit
    try:
        id_b = request.args.get('id', 'jacutinga_b01')
        
        # Converte valores com segurança
        mancal = float(request.args.get('mancal', 0))
        oleo = float(request.args.get('oleo', 0))
        vx = float(request.args.get('vx', 0))
        vy = float(request.args.get('vy', 0))
        vz = float(request.args.get('vz', 0))
        p_bar = float(request.args.get('pressao', 0))
        
        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        if id_b in memoria:
            # ATUALIZAÇÃO DIRETA NA MEMÓRIA
            memoria[id_b].update({
                'mancal': mancal, 'oleo': oleo, 'vx': vx, 'vy': vy, 'vz': vz,
                'rms': v_rms, 'pressao_bar': p_bar,
                'ultimo_visto': time.time(), 'online': True
            })
            
            # Histórico
            agora = datetime.now()
            ponto = {
                "Hora": agora.strftime("%H:%M:%S"),
                "RMS_Vibracao": round(v_rms, 3), 
                "Vib_X": vx, "Vib_Y": vy, "Vib_Z": vz,
                "Temp_Mancal": mancal, "Temp_Oleo": oleo,
                "Pressao_Bar": p_bar, "Pressao_MCA": round(p_bar * 10.197, 2)
            }
            memoria[id_b]['historico'].append(ponto)
            if len(memoria[id_b]['historico']) > 100: memoria[id_b]['historico'].pop(0)
            
            return "OK", 200
    except Exception as e:
        return str(e), 500
    return "ID Inexistente", 400

# Inicia o servidor Flask apenas uma vez
if 'thread_ativa' not in st.session_state:
    t = threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False), daemon=True)
    t.start()
    st.session_state['thread_ativa'] = True

# --- 4. FUNÇÕES DE APOIO ---
def atualizar_status_conexao():
    agora = time.time()
    for id_b in memoria:
        visto = memoria[id_b].get('ultimo_visto')
        if visto and (agora - visto > 15): # Se ficar 15s sem sinal, cai
            memoria[id_b]['online'] = False

def verificar_alertas(id_b):
    dados = memoria[id_b]
    lim = st.session_state.limites
    agora_f = datetime.now().strftime("%H:%M")
    
    # Lógica de alertas simplificada para performance
    if dados['mancal'] > lim['temp_mancal']:
        if not any(a['Sensor'] == "Mancal" and not a['Reconhecido'] for a in dados['alertas']):
            dados['alertas'].insert(0, {"Sensor": "Mancal", "Mensagem": "ALTA TEMP", "Hora": agora_f, "Valor": dados['mancal'], "Status": "CRÍTICO", "Reconhecido": False})
    return any(not a['Reconhecido'] for a in dados['alertas'])

# --- 5. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Jacutinga IoT", layout="wide")
st_autorefresh(interval=2000, key="refresh_global") # Atualiza a tela a cada 2s
atualizar_status_conexao()

with st.sidebar:
    st.header("⚙️ Menu")
    id_sel = st.selectbox("Ativo:", list(memoria.keys()), format_func=lambda x: memoria[x]['nome'])
    
    for id_b, d in memoria.items():
        st.sidebar.write(f"{'🟢' if d['online'] else '🔴'} {d['nome']}")

    aba = option_menu(None, ["Dashboard", "Gráficos", "Alertas", "Configurações"], 
                     icons=["speedometer2", "graph-up", "bell", "gear"], default_index=0)

dados_atual = memoria[id_sel]
tem_alerta = verificar_alertas(id_sel)

if aba == "Dashboard":
    st.title(f"📊 {dados_atual['nome']}")
    
    # DEBUG: Remova esta linha após testar (Ela mostra se os dados estão chegando no fundo do app)
    # st.write(f"Última atualização: {datetime.fromtimestamp(dados_atual['ultimo_visto']) if dados_atual['ultimo_visto'] else 'Nunca'}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Mancal", f"{dados_atual['mancal']:.1f} °C")
    c2.metric("🌡️ Óleo", f"{dados_atual['oleo']:.1f} °C")
    c3.metric("📳 RMS", f"{dados_atual['rms']:.3f}")
    c4.metric("💧 Pressão", f"{dados_atual['pressao_bar']:.1f} Bar")

    st.divider()
    
    # Gráficos Gauge
    col_g1, col_g2, col_g3 = st.columns(3)
    lay_g = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(t=30, b=0))

    with col_g1:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['mancal'], title={'text': "Temp. Mancal"}, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "red"}}))
        fig.update_layout(lay_g)
        st.plotly_chart(fig, width="stretch")

    with col_g2:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['pressao_bar'], title={'text': "Pressão (Bar)"}, gauge={'axis': {'range': [0, 12]}}))
        fig.update_layout(lay_g)
        st.plotly_chart(fig, width="stretch")

    with col_g3:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['rms'], title={'text': "Vibração (RMS)"}, gauge={'axis': {'range': [0, 5]}}))
        fig.update_layout(lay_g)
        st.plotly_chart(fig, width="stretch")

elif aba == "Gráficos":
    if not dados_atual['historico']:
        st.warning("Sem dados históricos no momento.")
    else:
        df = pd.DataFrame(dados_atual['historico'])
        st.plotly_chart(px.line(df, x="Hora", y="RMS_Vibracao", title="Tendência de Vibração"), width="stretch")
        st.plotly_chart(px.line(df, x="Hora", y="Temp_Mancal", title="Tendência de Temperatura"), width="stretch")

elif aba == "Alertas":
    st.subheader("⚠️ Alertas Ativos")
    for a in [al for al in dados_atual['alertas'] if not al['Reconhecido']]:
        st.error(f"**{a['Sensor']}**: {a['Mensagem']} ({a['Valor']} em {a['Hora']})")
        if st.button(f"Reconhecer {a['Sensor']}"):
            a['Reconhecido'] = True
            st.rerun()

elif aba == "Configurações":
    st.subheader("Ajustes de Limites")
    with st.form("conf"):
        st.session_state.limites['temp_mancal'] = st.number_input("Limite Temp (°C)", value=st.session_state.limites['temp_mancal'])
        st.session_state.limites['vib_rms'] = st.number_input("Limite RMS", value=st.session_state.limites['vib_rms'])
        if st.form_submit_button("Salvar"):
            salvar_configuracoes_arquivo(st.session_state.limites)
            st.success("Configurações Atualizadas!")
