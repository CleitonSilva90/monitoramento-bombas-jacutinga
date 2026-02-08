import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import math
import os
import json
from datetime import datetime
from supabase import create_client
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURAÇÃO SUPABASE ---
URL_SUPABASE = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

# --- 2. CONFIGURAÇÃO INICIAL STREAMLIT ---
st.set_page_config(page_title="Monitor de Ativos Jacutinga", layout="wide")

# --- 3. MEMÓRIA E CONFIGURAÇÕES ---
def carregar_limites():
    if 'limites' not in st.session_state:
        st.session_state.limites = {
            'temp_mancal': 70.0, 
            'temp_oleo': 65.0, 
            'vib_rms': 2.8,
            'pressao_max': 10.0
        }

carregar_limites()

@st.cache_resource
def obter_memoria_global():
    base = {"mancal": 0.0, "oleo": 0.0, "rms": 0.0, "pressao_bar": 0.0, "online": False}
    return {
        "jacutinga_b01": {**base, "nome": "Bomba 01", "local": "Jacutinga"},
        "jacutinga_b02": {**base, "nome": "Bomba 02", "local": "Jacutinga"},
        "jacutinga_b03": {**base, "nome": "Bomba 03", "local": "Jacutinga"}
    }

memoria = obter_memoria_global()

# --- 4. PROCESSADOR DE API (RECEBIMENTO DO ESP32) ---
query_params = st.query_params
if "id" in query_params:
    try:
        id_b = query_params.get("id")
        def safe_f(v):
            try: return float(v[0] if isinstance(v, list) else v)
            except: return 0.0

        vx = safe_f(query_params.get('vx', 0))
        vy = safe_f(query_params.get('vy', 0))
        vz = safe_f(query_params.get('vz', 0))
        mancal = safe_f(query_params.get('mancal', 0))
        oleo = safe_f(query_params.get('oleo', 0))
        p_bar = safe_f(query_params.get('pressao', 0))
        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        # Atualiza Status Atual no Banco (Upsert)
        supabase.table("telemetria_atual").upsert({
            "id_bomba": id_b, "mancal": mancal, "oleo": oleo,
            "vx": vx, "vy": vy, "vz": vz, "rms": v_rms,
            "pressao_bar": p_bar, "ultima_atualizacao": "now()"
        }).execute()

        # Insere no Histórico no Banco (Insert)
        supabase.table("historico_bombas").insert({
            "id_bomba": id_b, "mancal": mancal, "oleo": oleo,
            "rms": v_rms, "pressao_bar": p_bar
        }).execute()

        st.write("✅ OK - Banco Atualizado")
        st.stop()
    except Exception as e:
        st.write(f"❌ Erro: {e}")
        st.stop()

# --- 5. SINCRONIZAÇÃO (LEITURA DO BANCO PARA O DASHBOARD) ---
def sincronizar_dados():
    try:
        res = supabase.table("telemetria_atual").select("*").execute()
        for item in res.data:
            id_b = item['id_bomba']
            if id_b in memoria:
                memoria[id_b].update({
                    "mancal": item['mancal'], "oleo": item['oleo'],
                    "rms": item['rms'], "pressao_bar": item['pressao_bar'],
                    "online": True
                })
    except: pass

st_autorefresh(interval=3000, key="refresh_global")
sincronizar_dados()

# --- 6. INTERFACE SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>⚙️ Monitor Ativos</h2>", unsafe_allow_html=True)
    st.divider()
    id_sel = st.selectbox("📍 Selecionar Ativo:", list(memoria.keys()), 
                          format_func=lambda x: f"{memoria[x]['nome']}")
    
    aba = option_menu(None, ["Dashboard", "Gráficos", "Configurações"], 
        icons=["speedometer2", "graph-up", "gear"], 
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#004a8d"}})

dados_atual = memoria[id_sel]

# --- 7. DASHBOARD ---
if aba == "Dashboard":
    st.markdown(f"## 🚀 {dados_atual['nome']} - Status Real-Time")
    st.divider()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Temp. Mancal", f"{dados_atual['mancal']:.1f} °C")
    c2.metric("🌡️ Temp. Óleo", f"{dados_atual['oleo']:.1f} °C")
    c3.metric("📳 Vibração RMS", f"{dados_atual['rms']:.3f} mm/s²")
    c4.metric("💧 Pressão", f"{dados_atual['pressao_bar']:.1f} Bar")

    col_g1, col_g2, col_g3 = st.columns(3)
    
    # Gauge Vibração - Ajustado width='stretch' para evitar avisos
    fig_v = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['rms'], title={'text': "Vibração (mm/s²)"},
        gauge={'axis':{'range':[0,5]}, 'bar':{'color':"orange"}, 
               'threshold':{'line':{'color':"red",'width':4},'value':st.session_state.limites['vib_rms']}}))
    col_g1.plotly_chart(fig_v, width='stretch')

    # Gauge Pressão
    fig_p = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['pressao_bar'], title={'text': "Pressão (Bar)"},
        gauge={'axis':{'range':[0,12]}, 'bar':{'color':"#0097d7"}}))
    col_g2.plotly_chart(fig_p, width='stretch')

    # Gauge Temperatura
    fig_t = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['mancal'], title={'text': "Temp. Mancal (°C)"},
        gauge={'axis':{'range':[0,100]}, 'bar':{'color':"red"},
               'threshold':{'line':{'color':"black",'width':4},'value':st.session_state.limites['temp_mancal']}}))
    col_g3.plotly_chart(fig_t, width='stretch')

# --- 8. GRÁFICOS (HISTÓRICO REAL DO BANCO) ---
elif aba == "Gráficos":
    st.markdown(f"## 📈 Histórico de Dados - {dados_atual['nome']}")
    # Busca os últimos 50 registros do banco para os gráficos
    res_hist = supabase.table("historico_bombas").select("*").eq("id_bomba", id_sel).order("data_hora", desc=True).limit(50).execute()
    
    if res_hist.data:
        df = pd.DataFrame(res_hist.data)
        df['data_hora'] = pd.to_datetime(df['data_hora'])
        
        st.subheader("Vibração RMS ao longo do tempo")
        st.line_chart(df.set_index('data_hora')['rms'], width='stretch')
        
        st.subheader("Temperaturas (Mancal e Óleo)")
        st.line_chart(df.set_index('data_hora')[['mancal', 'oleo']], width='stretch')
        
        st.subheader("Pressão (Bar)")
        st.area_chart(df.set_index('data_hora')['pressao_bar'], width='stretch')
    else:
        st.info("Nenhum dado histórico encontrado no banco para este ativo.")

# --- 9. CONFIGURAÇÕES ---
elif aba == "Configurações":
    st.markdown("## ⚙️ Configuração de Limites de Alerta")
    with st.form("form_limites"):
        v_max = st.number_input("Limite Vibração RMS (mm/s²)", value=st.session_state.limites['vib_rms'])
        t_max = st.number_input("Limite Temp. Mancal (°C)", value=st.session_state.limites['temp_mancal'])
        o_max = st.number_input("Limite Temp. Óleo (°C)", value=st.session_state.limites['temp_oleo'])
        
        if st.form_submit_button("Salvar Configurações"):
            st.session_state.limites.update({
                'vib_rms': v_max,
                'temp_mancal': t_max,
                'temp_oleo': o_max
            })
            st.success("Limites atualizados com sucesso!")
