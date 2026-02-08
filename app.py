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
        "pressao_bar": 0.0, "alertas": [], "online": False, "ultimo_visto": None
    }
    return {
        "jacutinga_b01": {**base, "nome": "Bomba 01", "local": "Jacutinga"},
        "jacutinga_b02": {**base, "nome": "Bomba 02", "local": "Jacutinga"},
        "jacutinga_b03": {**base, "nome": "Bomba 03", "local": "Jacutinga"}
    }

memoria = obter_memoria_global()

# Mantendo seus limites padrão originais
if 'limites' not in st.session_state:
    st.session_state.limites = {
        'temp_mancal': 70.0, 'temp_oleo': 65.0, 'vib_rms': 2.8,
        'pressao_max_bar': 10.0, 'pressao_min_bar': 2.0
    }

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- 3. PROCESSADOR DE API (ENTRADA DO ESP32) ---
query_params = st.query_params

if 'id' in query_params:
    try:
        id_b = query_params['id']
        
        def safe_f(key):
            v = query_params.get(key, "0")
            return float(v[0] if isinstance(v, list) else v)

        vx = safe_f('vx')
        vy = safe_f('vy')
        vz = safe_f('vz')
        mancal = safe_f('mancal')
        oleo = safe_f('oleo')
        p_bar = safe_f('pressao')
        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        # 1. Update no Status Atual (para o Dashboard)
        supabase.table("telemetria_atual").upsert({
            "id_bomba": id_b, "mancal": mancal, "oleo": oleo,
            "vx": vx, "vy": vy, "vz": vz, "rms": v_rms,
            "pressao_bar": p_bar, "ultima_atualizacao": "now()"
        }).execute()

        # 2. Insert no Histórico (para os Gráficos)
        supabase.table("historico_bombas").insert({
            "id_bomba": id_b, "mancal": mancal, "oleo": oleo,
            "rms": v_rms, "pressao_bar": p_bar
        }).execute()

        st.write("OK")
        st.stop()
    except Exception as e:
        st.write(f"Erro API: {e}")
        st.stop()

# --- 4. SINCRONIZAÇÃO BANCO -> MEMÓRIA ---
def sincronizar_dados():
    try:
        res = supabase.table("telemetria_atual").select("*").execute()
        agora = datetime.now()
        for item in res.data:
            id_b = item['id_bomba']
            if id_b in memoria:
                # Trata o timestamp do banco
                att_str = item['ultima_atualizacao'].replace('T', ' ').split('+')[0]
                ultima_att = datetime.strptime(att_str, '%Y-%m-%d %H:%M:%S.%f' if '.' in att_str else '%Y-%m-%d %H:%M:%S')
                
                # Se recebeu dado nos últimos 60s, está online
                est_online = (agora - ultima_att).total_seconds() < 60
                
                memoria[id_b].update({
                    "mancal": item['mancal'], "oleo": item['oleo'], 
                    "vx": item['vx'], "vy": item['vy'], "vz": item['vz'],
                    "rms": item['rms'], "pressao_bar": item['pressao_bar'],
                    "online": est_online, "ultimo_visto": (agora - ultima_att).total_seconds()
                })
    except: pass

# --- 5. CONFIGURAÇÃO DA PÁGINA E AUTO-REFRESH ---
st.set_page_config(page_title="Monitor de Ativos Jacutinga", layout="wide")
st_autorefresh(interval=3000, key="refresh_global")
sincronizar_dados()

# --- 6. LÓGICA DE ALERTAS ---
def verificar_alertas(id_b):
    dados = memoria[id_b]
    lim = st.session_state.limites
    agora_f = datetime.now().strftime("%d/%m/%Y %H:%M")
    novos = []
    
    if dados['pressao_bar'] > lim['pressao_max_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO ALTA", dados['pressao_bar']))
    elif 0.1 < dados['pressao_bar'] < lim['pressao_min_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO BAIXA", dados['pressao_bar']))
    if dados['mancal'] > lim['temp_mancal']:
        novos.append(("Temp. Mancal", "CRÍTICO", "LIMITE EXCEDIDO", dados['mancal']))
    if dados['rms'] > lim['vib_rms']:
        novos.append(("Vibração", "CRÍTICO", "VIBRAÇÃO ELEVADA", dados['rms']))

    for sensor, status, msg, valor in novos:
        if not any(a['Mensagem'] == msg and not a['Reconhecido'] for a in dados['alertas']):
            dados['alertas'].insert(0, {
                "Equipamento": dados['nome'], "Sensor": sensor, "Mensagem": msg, 
                "Hora": agora_f, "Valor": round(valor, 2), "Status": status, "Reconhecido": False
            })
    return any(not a['Reconhecido'] for a in dados['alertas'])

# --- 7. SIDEBAR E MENU ---
with st.sidebar:
    st.markdown("<div style='text-align: center;'><img src='https://cdn-icons-png.flaticon.com/512/3105/3105807.png' width='80'></div>", unsafe_allow_html=True)
    st.divider()
    id_sel = st.selectbox("📍 Selecionar Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']} - {memoria[x]['local']}")
    
    st.markdown("### 🌐 Status de Conexão")
    for id_b, d in memoria.items():
        cor = "🟢" if d['online'] else "🔴"
        visto = f"({int(d['ultimo_visto'])}s)" if d['ultimo_visto'] is not None else "(sem dados)"
        st.write(f"{cor} **{d['nome']}** {visto}")

    st.divider()
    aba = option_menu(None, ["Dashboard", "Gráficos", "Alertas", "Configurações"], 
        icons=["speedometer2", "graph-up", "bell-fill", "gear-fill"], 
        default_index=0, styles={"nav-link-selected": {"background-color": "#004a8d"}})

tem_alerta = verificar_alertas(id_sel)
dados_atual = memoria[id_sel]

# --- 8. RENDERIZAÇÃO DAS ABAS ---

if aba == "Dashboard":
    col_tit, col_sts = st.columns([0.7, 0.3])
    with col_tit:
        st.markdown(f"## 🚀 {dados_atual['nome']} - {dados_atual['local']}")
    with col_sts:
        if not dados_atual['online']:
            st.markdown("<div style='background-color:#555; color:white; padding:10px; border-radius:10px; text-align:center;'>⚪ OFFLINE</div>", unsafe_allow_html=True)
        elif tem_alerta:
            st.markdown("<div style='background-color:#ff4b4b; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>⚠️ ALERTA</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='background-color:#28a745; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>✅ NORMAL</div>", unsafe_allow_html=True)
    
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Temp. Mancal", f"{dados_atual['mancal']:.1f} °C")
    c2.metric("🌡️ Temp. Óleo", f"{dados_atual['oleo']:.1f} °C")
    c3.metric("📳 Vibração RMS", f"{dados_atual['rms']:.3f} mm/s²")
    c4.metric("💧 Pressão Saída", f"{dados_atual['pressao_bar'] * 10.197:.1f} MCA")

    st.markdown("### 📊 Indicadores de Performance")
    col_g1, col_g2, col_g3 = st.columns(3)
    lim = st.session_state.limites
    
    with col_g1:
        fig_v = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['rms'], title={'text': "Vibração RMS"},
            gauge={'axis':{'range':[0,5]}, 'bar':{'color':"orange"}, 'threshold':{'line':{'color':"red",'width':4},'value':lim['vib_rms']}}))
        st.plotly_chart(fig_v, use_container_width=True)

    with col_g2:
        fig_p = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['pressao_bar'], title={'text': "Pressão (Bar)"},
            gauge={'axis':{'range':[0,12]}, 'bar':{'color':"#0097d7"}}))
        st.plotly_chart(fig_p, use_container_width=True)

    with col_g3:
        fig_t = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['mancal'], title={'text': "Temp. Mancal (°C)"},
            gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#ff4b4b"}}))
        st.plotly_chart(fig_t, use_container_width=True)

elif aba == "Gráficos":
    st.markdown(f"## 📈 Tendências - {dados_atual['nome']}")
    res_h = supabase.table("historico_bombas").select("*").eq("id_bomba", id_sel).order("data_hora", desc=True).limit(100).execute()
    
    if not res_h.data:
        st.info("⏳ Aguardando dados históricos...")
    else:
        df = pd.DataFrame(res_h.data)
        df['data_hora'] = pd.to_datetime(df['data_hora'])
        # Ajustando nomes para bater com seu original
        df['Pressao_MCA'] = df['pressao_bar'] * 10.197

        st.markdown("### 📳 Análise de Vibração")
        st.plotly_chart(px.line(df, x="data_hora", y="rms", title="Vibração RMS (mm/s²)"), use_container_width=True)

        st.divider()
        cg1, cg2 = st.columns(2)
        with cg1:
            st.plotly_chart(px.line(df, x="data_hora", y=["mancal", "oleo"], title="Temperaturas (°C)"), use_container_width=True)
        with cg2:
            st.plotly_chart(px.area(df, x="data_hora", y="Pressao_MCA", title="Pressão (MCA)", color_discrete_sequence=["#0097d7"]), use_container_width=True)

elif aba == "Alertas":
    st.markdown("### 🔔 Central de Alertas")
    alt = [a for a in dados_atual['alertas'] if not a['Reconhecido']]
    if not alt: st.success("Sistema operando sem pendências.")
    else:
        for i, a in enumerate(alt):
            with st.container(border=True):
                c_st, c_tx, c_btn = st.columns([0.15, 0.65, 0.2])
                c_st.error(a['Status'])
                c_tx.write(f"**{a['Sensor']}**: {a['Mensagem']} em {a['Hora']} (Valor: {a['Valor']})")
                if c_btn.button("✔ Reconhecer", key=f"ack_{i}"):
                    a['Reconhecido'] = True
                    st.rerun()

elif aba == "Configurações":
    st.markdown("## ⚙️ Configurações do Sistema")
    if not st.session_state.autenticado:
        senha = st.text_input("Senha Admin:", type="password")
        if st.button("Liberar Acesso"):
            if senha == "admin123": st.session_state.autenticado = True; st.rerun()
            else: st.error("Acesso Negado")
    else:
        if st.button("Encerrar Sessão 🔓"): st.session_state.autenticado = False; st.rerun()
        
        with st.form("limites_operacionais"):
            atuais = st.session_state.limites
            c_l1, c_l2 = st.columns(2)
            n_mancal = c_l1.number_input("Temp. Mancal Máx (°C)", value=float(atuais['temp_mancal']))
            n_rms = c_l2.number_input("Vibração Máx (mm/s²)", value=float(atuais['vib_rms']), format="%.3f")
            
            if st.form_submit_button("💾 Salvar Configurações"):
                st.session_state.limites.update({'temp_mancal': n_mancal, 'vib_rms': n_rms})
                st.success("Limites atualizados com sucesso!")

        st.divider()
        st.subheader("📊 Exportação de Dados")
        res_exp = supabase.table("historico_bombas").select("*").eq("id_bomba", id_sel).order("data_hora", desc=True).execute()
        if res_exp.data:
            df_exp = pd.DataFrame(res_exp.data)
            towrite = io.BytesIO()
            df_exp.to_excel(towrite, index=False, engine='openpyxl')
            st.download_button(label="📥 Baixar Histórico em Excel", data=towrite.getvalue(), file_name=f"relatorio_{id_sel}.xlsx")
