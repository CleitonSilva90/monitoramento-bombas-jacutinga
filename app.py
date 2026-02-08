import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import math
import os
import io
from datetime import datetime
from supabase import create_client
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURAÇÃO SUPABASE ---
# SUBSTITUA PELAS SUAS CHAVES DO PAINEL API DO SUPABASE
URL_SUPABASE = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

# --- 2. CONFIGURAÇÃO INICIAL STREAMLIT ---
st.set_page_config(page_title="Monitor de Ativos Jacutinga", layout="wide")

# --- 3. MEMÓRIA E PERSISTÊNCIA ---
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
        except: return padrao
    return padrao

@st.cache_resource
def obter_memoria_global():
    base = {
        "mancal": 0.0, "oleo": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "rms": 0.0, 
        "pressao_bar": 0.0, "alertas": [], "online": False
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

        # Gravação no Banco (Upsert para status atual)
        supabase.table("telemetria_atual").upsert({
            "id_bomba": id_b,
            "mancal": mancal, "oleo": oleo,
            "vx": vx, "vy": vy, "vz": vz, "rms": v_rms,
            "pressao_bar": p_bar,
            "ultima_atualizacao": "now()"
        }).execute()

        # Gravação no Histórico (Para gráficos)
        supabase.table("historico_bombas").insert({
            "id_bomba": id_b,
            "mancal": mancal, "oleo": oleo,
            "rms": v_rms, "pressao_bar": p_bar
        }).execute()

        st.write("✅ OK")
        st.stop()
    except Exception as e:
        st.write(f"❌ Erro: {e}")
        st.stop()

# --- 5. SINCRONIZAÇÃO (LEITURA DO BANCO PARA O DASHBOARD) ---
def sincronizar_dados():
    try:
        res = supabase.table("telemetria_atual").select("*").execute()
        agora = datetime.now()
        for item in res.data:
            id_b = item['id_bomba']
            if id_b in memoria:
                memoria[id_b].update({
                    "mancal": item['mancal'], "oleo": item['oleo'],
                    "vx": item['vx'], "vy": item['vy'], "vz": item['vz'],
                    "rms": item['rms'], "pressao_bar": item['pressao_bar'],
                    "online": True
                })
    except: pass

st_autorefresh(interval=3000, key="refresh_global")
sincronizar_dados()

# --- 6. INTERFACE SIDEBAR ---
with st.sidebar:
    st.markdown("<div style='text-align: center;'><img src='https://cdn-icons-png.flaticon.com/512/3105/3105807.png' width='80'></div>", unsafe_allow_html=True)
    st.divider()
    id_sel = st.selectbox("📍 Selecionar Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']} - {memoria[x]['local']}")
    
    aba = option_menu(None, ["Dashboard", "Gráficos", "Alertas", "Configurações"], 
        icons=["speedometer2", "graph-up", "bell-fill", "gear-fill"], default_index=0,
        styles={"nav-link-selected": {"background-color": "#004a8d"}})

dados_atual = memoria[id_sel]

# --- 7. DASHBOARD ---
if aba == "Dashboard":
    st.markdown(f"## 🚀 {dados_atual['nome']} - {dados_atual['local']}")
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Temp. Mancal", f"{dados_atual['mancal']:.1f} °C")
    c2.metric("🌡️ Temp. Óleo", f"{dados_atual['oleo']:.1f} °C")
    c3.metric("📳 Vibração RMS", f"{dados_atual['rms']:.3f} mm/s²")
    c4.metric("💧 Pressão Saída", f"{dados_atual['pressao_bar'] * 10.197:.1f} MCA")

    col_g1, col_g2, col_g3 = st.columns(3)
    # Gauge Vibração
    fig_v = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['rms'], title={'text': "Vibração RMS"},
        gauge={'axis':{'range':[0,5]}, 'bar':{'color':"orange"}, 'threshold':{'line':{'color':"red",'width':4},'value':st.session_state.limites['vib_rms']}}))
    col_g1.plotly_chart(fig_v, use_container_width=True)

    # Gauge Pressão
    fig_p = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['pressao_bar'], title={'text': "Pressão (Bar)"},
        gauge={'axis':{'range':[0,12]}, 'bar':{'color':"#0097d7"}}))
    col_g2.plotly_chart(fig_p, use_container_width=True)

    # Gauge Temperatura
    fig_t = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['mancal'], title={'text': "Temp. Mancal"},
        gauge={'axis':{'range':[0,100]}, 'bar':{'color':"red"}}))
    col_g3.plotly_chart(fig_t, use_container_width=True)

# --- 8. GRÁFICOS (BUSCA HISTÓRICO REAL DO BANCO) ---
elif aba == "Gráficos":
    st.markdown(f"## 📈 Tendências Históricas - {dados_atual['nome']}")
    res_hist = supabase.table("historico_bombas").select("*").eq("id_bomba", id_sel).order("data_hora", desc=True).limit(100).execute()
    
    if res_hist.data:
        df = pd.DataFrame(res_hist.data)
        df['data_hora'] = pd.to_datetime(df['data_hora'])
        
        st.plotly_chart(px.line(df, x="data_hora", y="rms", title="Vibração RMS (mm/s²)"), use_container_width=True)
        st.plotly_chart(px.line(df, x="data_hora", y=["mancal", "oleo"], title="Temperaturas (°C)"), use_container_width=True)
        st.plotly_chart(px.area(df, x="data_hora", y="pressao_bar", title="Pressão (Bar)"), use_container_width=True)
    else:
        st.info("Aguardando telemetria inicial...")

# --- ABA DE CONFIGURAÇÕES (MANTIDA) ---
elif aba == "Configurações":
    st.markdown("## ⚙️ Ajuste de Limites")
    with st.form("config"):
        lim = st.session_state.limites
        n_v = st.number_input("Vibração Máxima (mm/s²)", value=float(lim['vib_rms']))
        n_m = st.number_input("Temp Mancal Máxima (°C)", value=float(lim['temp_mancal']))
        if st.form_submit_button("Salvar"):
            st.session_state.limites.update({'vib_rms': n_v, 'temp_mancal': n_m})
            st.success("Configurações salvas!")
