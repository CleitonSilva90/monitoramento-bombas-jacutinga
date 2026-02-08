import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import math
import json
import os
from datetime import datetime
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh
from supabase import create_client
import io

# --- 1. CONEXÃO BANCO (SUPABASE) ---
URL_SUPABASE = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

# --- 2. MEMÓRIA GLOBAL (CACHE) ---
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

# --- 3. PROCESSADOR DE API (VERSÃO ATUALIZADA PARA O RENDER) ---
# Substituímos st.experimental_get_query_params() por st.query_params
params = st.query_params.to_dict()

if 'id' in params:
    try:
        id_b = params['id']
        def safe_f(key):
            return float(params.get(key, 0))

        vx, vy, vz = safe_f('vx'), safe_f('vy'), safe_f('vz')
        mancal, oleo, p_bar = safe_f('mancal'), safe_f('oleo'), safe_f('pressao')
        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        # Grava no Supabase
        supabase.table("telemetria_atual").upsert({
            "id_bomba": id_b, "mancal": mancal, "oleo": oleo,
            "vx": vx, "vy": vy, "vz": vz, "rms": v_rms,
            "pressao_bar": p_bar, "ultima_atualizacao": datetime.utcnow().isoformat()
        }).execute()

        supabase.table("historico_bombas").insert({
            "id_bomba": id_b, "mancal": mancal, "oleo": oleo,
            "rms": v_rms, "pressao_bar": p_bar
        }).execute()

        st.write("OK")
        st.stop()
    except Exception as e:
        st.write(f"Erro API: {e}")
        st.stop()

# --- 4. SINCRONIZAÇÃO E UI ---
def sincronizar_dados():
    try:
        res = supabase.table("telemetria_atual").select("*").execute()
        agora = datetime.now()
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
    except: pass

st.set_page_config(page_title="Monitor de Ativos Jacutinga", layout="wide")
st_autorefresh(interval=3000, key="refresh_global")
sincronizar_dados()

# --- 5. LÓGICA DE ALERTAS ---
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

# --- 6. SIDEBAR ---
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

# --- 7. ABAS ---
if aba == "Dashboard":
    col_tit, col_sts = st.columns([0.7, 0.3])
    with col_tit: st.markdown(f"## 🚀 {dados_atual['nome']} - {dados_atual['local']}")
    with col_sts:
        st.markdown(f"<div style='background-color:{'#28a745' if not tem_alerta else '#ff4b4b'}; color:white; padding:10px; border-radius:10px; text-align:center;'>{'✅ NORMAL' if not tem_alerta else '⚠️ ALERTA'}</div>", unsafe_allow_html=True)
    
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Temp. Mancal", f"{dados_atual['mancal']:.1f} °C")
    c2.metric("🌡️ Temp. Óleo", f"{dados_atual['oleo']:.1f} °C")
    c3.metric("📳 Vibração RMS", f"{dados_atual['rms']:.3f} mm/s²")
    c4.metric("💧 Pressão Saída", f"{dados_atual['pressao_bar'] * 10.197:.1f} MCA")

    st.markdown("### 📊 Indicadores")
    cg1, cg2, cg3 = st.columns(3)
    cg1.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['rms'], title={'text': "Vibração (RMS)"}, gauge={'axis':{'range':[0,5]},'threshold':{'line':{'color':"red",'width':4},'value':st.session_state.limites['vib_rms']}})), use_container_width=True)
    cg2.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['pressao_bar'], title={'text': "Pressão (Bar)"}, gauge={'axis':{'range':[0,12]}})), use_container_width=True)
    cg3.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['mancal'], title={'text': "Temp. Mancal (°C)"}, gauge={'axis':{'range':[0,100]}})), use_container_width=True)

elif aba == "Gráficos":
    st.markdown(f"## 📈 Tendências - {dados_atual['nome']}")
    res_h = supabase.table("historico_bombas").select("*").eq("id_bomba", id_sel).order("data_hora", desc=True).limit(50).execute()
    if res_h.data:
        df = pd.DataFrame(res_h.data)
        df['data_hora'] = pd.to_datetime(df['data_hora'])
        df['Pressao_MCA'] = df['pressao_bar'] * 10.197
        st.plotly_chart(px.line(df, x="data_hora", y="rms", title="Vibração (mm/s²)"), use_container_width=True)
        c_g1, c_g2 = st.columns(2)
        c_g1.plotly_chart(px.line(df, x="data_hora", y=["mancal", "oleo"], title="Térmico (°C)"), use_container_width=True)
        c_g2.plotly_chart(px.area(df, x="data_hora", y="Pressao_MCA", title="Pressão (MCA)"), use_container_width=True)

elif aba == "Alertas":
    st.markdown("### 🔔 Central de Alertas")
    alt = [a for a in dados_atual['alertas'] if not a['Reconhecido']]
    for i, a in enumerate(alt):
        with st.container(border=True):
            st.error(f"{a['Sensor']}: {a['Mensagem']} em {a['Hora']} (Valor: {a['Valor']})")
            if st.button("✔ Reconhecer", key=f"ack_{i}"): a['Reconhecido'] = True; st.rerun()

elif aba == "Configurações":
    if not st.session_state.autenticado:
        if st.text_input("Senha Admin", type="password") == "admin123":
            if st.button("Liberar"): st.session_state.autenticado = True; st.rerun()
    else:
        with st.form("limites"):
            l = st.session_state.limites
            col1, col2 = st.columns(2)
            n_mancal = col1.number_input("Temp. Mancal Máx (°C)", value=float(l['temp_mancal']))
            n_oleo = col2.number_input("Temp. Óleo Máx (°C)", value=float(l['temp_oleo']))
            col3, col4 = st.columns(2)
            n_rms = col3.number_input("Vibração Máx (mm/s²)", value=float(l['vib_rms']), format="%.3f")
            n_p_max = col4.number_input("Pressão Máxima (Bar)", value=float(l['pressao_max_bar']))
            n_p_min = col4.number_input("Pressão Mínima (Bar)", value=float(l['pressao_min_bar']))
            if st.form_submit_button("💾 Salvar"):
                l.update({'temp_mancal': n_mancal, 'temp_oleo': n_oleo, 'vib_rms': n_rms, 'pressao_max_bar': n_p_max, 'pressao_min_bar': n_p_min})
                st.success("Salvo!")
