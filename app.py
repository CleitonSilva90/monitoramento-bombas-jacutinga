import streamlit as st
import math
from datetime import datetime
from supabase import create_client

# =====================================================
# 1. CONEXÃO BANCO (SUPABASE)
# =====================================================
URL_SUPABASE = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

# =====================================================
# 2.🔥 API – PRIMEIRA COISA EXECUTADA (STREAMLIT NOVO)
# =====================================================
params = dict(st.query_params)

if 'id' in params:
    try:
        id_b = params['id']

        def safe_f(k):
            return float(params.get(k, '0'))

        vx = safe_f('vx')
        vy = safe_f('vy')
        vz = safe_f('vz')
        mancal = safe_f('mancal')
        oleo = safe_f('oleo')
        p_bar = safe_f('pressao')

        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        supabase.table("telemetria_atual").upsert({
            "id_bomba": id_b,
            "mancal": mancal,
            "oleo": oleo,
            "vx": vx,
            "vy": vy,
            "vz": vz,
            "rms": v_rms,
            "pressao_bar": p_bar,
            "ultima_atualizacao": "now()"
        }).execute()

        supabase.table("historico_bombas").insert({
            "id_bomba": id_b,
            "mancal": mancal,
            "oleo": oleo,
            "rms": v_rms,
            "pressao_bar": p_bar
        }).execute()

        st.write("OK")
        st.stop()

    except Exception as e:
        st.write(f"Erro API: {e}")
        st.stop()


# =====================================================
# 3. IMPORTAÇÕES DO DASHBOARD (INALTERADAS)
# =====================================================
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import json
import os
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh
import io

# =====================================================
# 4. MEMÓRIA GLOBAL (CACHE) — INALTERADA
# =====================================================
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
    st.session_state.limites = {
        'temp_mancal': 70.0, 'temp_oleo': 65.0, 'vib_rms': 2.8,
        'pressao_max_bar': 10.0, 'pressao_min_bar': 2.0
    }

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# =====================================================
# 5. SINCRONIZAÇÃO BANCO → UI (INALTERADA)
# =====================================================
def sincronizar_dados():
    try:
        res = supabase.table("telemetria_atual").select("*").execute()
        for item in res.data:
            id_b = item['id_bomba']
            if id_b in memoria:
                att_str = item['ultima_atualizacao'].replace('T', ' ').split('+')[0]
                try:
                    ultima_att = datetime.strptime(att_str, '%Y-%m-%d %H:%M:%S.%f')
                except:
                    ultima_att = datetime.strptime(att_str, '%Y-%m-%d %H:%M:%S')

                online = (datetime.utcnow() - ultima_att).total_seconds() < 60
                memoria[id_b].update({
                    "mancal": item['mancal'], "oleo": item['oleo'], "rms": item['rms'],
                    "vx": item['vx'], "vy": item['vy'], "vz": item['vz'],
                    "pressao_bar": item['pressao_bar'], "online": online
                })
    except:
        pass

st.set_page_config(page_title="Monitor de Ativos Jacutinga", layout="wide")
st_autorefresh(interval=3000, key="refresh_global")
sincronizar_dados()

# =====================================================
# 6. ALERTAS (INALTERADO)
# =====================================================
def verificar_alertas(id_b):
    dados = memoria[id_b]
    lim = st.session_state.limites
    agora_f = datetime.now().strftime("%d/%m/%Y %H:%M")
    novos = []
    if dados['pressao_bar'] > lim['pressao_max_bar']: novos.append(("Pressão", "ALTA", dados['pressao_bar']))
    if 0.1 < dados['pressao_bar'] < lim['pressao_min_bar']: novos.append(("Pressão", "BAIXA", dados['pressao_bar']))
    if dados['mancal'] > lim['temp_mancal']: novos.append(("Mancal", "ALTA", dados['mancal']))
    if dados['rms'] > lim['vib_rms']: novos.append(("Vibração", "ALTA", dados['rms']))
    for s, msg, v in novos:
        if not any(a['Mensagem'] == msg and a['Sensor'] == s and not a['Reconhecido'] for a in dados['alertas']):
            dados['alertas'].insert(0, {"Sensor": s, "Mensagem": msg, "Hora": agora_f, "Valor": round(v,2), "Reconhecido": False})
    return any(not a['Reconhecido'] for a in dados['alertas'])

# =====================================================
# 7. SIDEBAR, ABAS E DASHBOARD (100% ORIGINAL)
# =====================================================
with st.sidebar:
    st.markdown("<div style='text-align: center;'><img src='https://cdn-icons-png.flaticon.com/512/3105/3105807.png' width='80'></div>", unsafe_allow_html=True)
    st.divider()
    id_sel = st.selectbox("📍 Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']}")
    for id_b, d in memoria.items():
        st.write(f"{'🟢' if d['online'] else '🔴'} **{d['nome']}**")
    st.divider()
    aba = option_menu(None, ["Dashboard", "Gráficos", "Alertas", "Configurações"],
        icons=["speedometer2", "graph-up", "bell-fill", "gear-fill"], default_index=0)

tem_alerta = verificar_alertas(id_sel)
dados_atual = memoria[id_sel]

# === O RESTO DO SEU CÓDIGO CONTINUA IGUAL ===
# (Dashboard, Gráficos, Alertas, Configurações)
