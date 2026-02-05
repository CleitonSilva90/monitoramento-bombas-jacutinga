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

# --- 2. MEMÓRIA GLOBAL ---
@st.cache_resource
def obter_memoria_global():
    return {
        "jacutinga_b01": {"nome": "Bomba 01", "local": "Jacutinga", "mancal": 0.0, "oleo": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "rms": 0.0, "pressao_bar": 0.0, "historico": [], "alertas": []},
        "jacutinga_b02": {"nome": "Bomba 02", "local": "Jacutinga", "mancal": 0.0, "oleo": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "rms": 0.0, "pressao_bar": 0.0, "historico": [], "alertas": []},
        "jacutinga_b03": {"nome": "Bomba 03", "local": "Jacutinga", "mancal": 0.0, "oleo": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "rms": 0.0, "pressao_bar": 0.0, "historico": [], "alertas": []}
    }

memoria = obter_memoria_global()

if 'limites' not in st.session_state:
    st.session_state.limites = carregar_configuracoes()

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- 3. SERVIDOR FLASK ---
app_flask = Flask(__name__)
CORS(app_flask)

@app_flask.route('/update', methods=['GET'])
def update():
    try:
        id_b = request.args.get('id', 'jacutinga_b01')
        def safe_float(v):
            try: return float(v)
            except: return 0.0

        vx, vy, vz = safe_float(request.args.get('vx', 0)), safe_float(request.args.get('vy', 0)), safe_float(request.args.get('vz', 0))
        mancal, oleo, p_bar = safe_float(request.args.get('mancal', 0)), safe_float(request.args.get('oleo', 0)), safe_float(request.args.get('pressao', 0))
        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        if id_b in memoria:
            memoria[id_b].update({'vx': vx, 'vy': vy, 'vz': vz, 'rms': v_rms, 'mancal': mancal, 'oleo': oleo, 'pressao_bar': p_bar})
            ponto = {
                "Data_Hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 
                "Hora": datetime.now().strftime("%H:%M:%S"),
                "RMS_Vibracao": round(v_rms, 3), 
                "Vib_X": vx, "Vib_Y": vy, "Vib_Z": vz,
                "Temp_Mancal": mancal, 
                "Pressao_MCA": round(p_bar * 10.197, 2), "Temp_Oleo": oleo, "Pressao_Bar": p_bar
            }
            memoria[id_b]['historico'].append(ponto)
            if len(memoria[id_b]['historico']) > 1000: memoria[id_b]['historico'].pop(0)
            return "OK", 200
    except: return "Erro", 500
    return "ID Inválido", 400

if 'thread_ativa' not in st.session_state:
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False), daemon=True).start()
    st.session_state['thread_ativa'] = True

# --- 4. LÓGICA DE ALERTAS ---
def verificar_alertas(id_b):
    dados = memoria[id_b]
    lim = st.session_state.limites
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    novos = []
    if dados['pressao_bar'] > lim['pressao_max_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO ACIMA DO LIMITE", dados['pressao_bar']))
    elif 0.1 < dados['pressao_bar'] < lim['pressao_min_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO BAIXA - ADUTORA", dados['pressao_bar']))
    if dados['mancal'] > lim['temp_mancal']:
        novos.append(("Temp. Mancal", "CRÍTICO", "LIMITE EXCEDIDO", dados['mancal']))
    if dados['rms'] > lim['vib_rms']:
        novos.append(("Vibração", "CRÍTICO", "VIBRAÇÃO ELEVADA", dados['rms']))

    for sensor, status, msg, valor in novos:
        if not any(a['Mensagem'] == msg and a['Hora'] == agora for a in dados['alertas']):
            dados['alertas'].insert(0, {
                "Equipamento": f"{dados['nome']}", "Sensor": sensor, "Mensagem": msg, 
                "Hora": agora, "Valor": round(valor, 2), "Status": status, "Reconhecido": False
            })
    return len(novos) > 0

# --- 5. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Monitor de Ativos", layout="wide")

with st.sidebar:
    st.markdown("<div style='text-align: center;'><img src='https://cdn-icons-png.flaticon.com/512/3105/3105807.png' width='80'></div>", unsafe_allow_html=True)
    st.divider()
    id_sel = st.selectbox("📍 Selecionar Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']} - {memoria[x]['local']}")
    
    aba = option_menu(
        menu_title=None, 
        options=["Dashboard", "Gráficos", "Alertas", "Configurações"],
        icons=["speedometer2", "graph-up", "bell-fill", "gear-fill"], 
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#004a8d"}},
        key="menu_principal"
    )

if aba != "Configurações":
    st_autorefresh(interval=2000, key="refresh_global")

tem_alerta = verificar_alertas(id_sel)
dados_atual = memoria[id_sel]

# --- 6. RENDERIZAÇÃO ---
main_area = st.empty()

with main_area.container():
    if aba == "Dashboard":
        # Cabeçalho com Status
        col_tit, col_sts = st.columns([0.7, 0.3])
        with col_tit:
            st.markdown(f"## 🚀 {dados_atual['nome']} - {dados_atual['local']}")
        with col_sts:
            if tem_alerta:
                st.markdown("<div style='background-color:#ff4b4b; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>⚠️ ATENÇÃO: ALERTA ATIVO</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='background-color:#28a745; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>✅ OPERAÇÃO NORMAL</div>", unsafe_allow_html=True)
        
        st.divider()

        # Linha 1: Métricas de Temperatura
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️ Temp. Mancal", f"{dados_atual['mancal']:.1f} °C")
        c2.metric("🌡️ Temp. Óleo", f"{dados_atual['oleo']:.1f} °C")
        c3.metric("📳 Vibração RMS", f"{dados_atual['rms']:.3f} mm/s²")
        c4.metric("💧 Pressão Saída", f"{dados_atual['pressao_bar'] * 10.197:.1f} MCA")

        st.markdown("### 📊 Indicadores de Performance")
        
        # Linha 2: Gauges Criativos
        col_g1, col_g2, col_g3 = st.columns(3)
        
        lim = st.session_state.limites
        
        with col_g1:
            # Gauge de Vibração
            fig_v = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = dados_atual['rms'],
                title = {'text': "Nível de Vibração (RMS)"},
                gauge = {
                    'axis': {'range': [0, lim['vib_rms'] * 1.5]},
                    'bar': {'color': "#004a8d"},
                    'steps': [
                        {'range': [0, lim['vib_rms']*0.7], 'color': "#e8f5e9"},
                        {'range': [lim['vib_rms']*0.7, lim['vib_rms']], 'color': "#fff3e0"},
                        {'range': [lim['vib_rms'], lim['vib_rms']*1.5], 'color': "#ffebee"}
                    ],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': lim['vib_rms']}
                }
            ))
            fig_v.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig_v, use_container_width=True)

        with col_g2:
            # Gauge de Pressão
            fig_p = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = dados_atual['pressao_bar'],
                title = {'text': "Pressão de Saída (Bar)"},
                gauge = {
                    'axis': {'range': [0, lim['pressao_max_bar'] + 2]},
                    'bar': {'color': "#0097d7"},
                    'steps': [
                        {'range': [0, lim['pressao_min_bar']], 'color': "#ffebee"},
                        {'range': [lim['pressao_min_bar'], lim['pressao_max_bar']], 'color': "#e8f5e9"},
                        {'range': [lim['pressao_max_bar'], lim['pressao_max_bar']+2], 'color': "#ffebee"}
                    ]
                }
            ))
            fig_p.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig_p, use_container_width=True)

        with col_g3:
            # Gauge de Temperatura do Mancal
            fig_t = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = dados_atual['mancal'],
                title = {'text': "Temp. Mancal (°C)"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#ff4b4b"},
                    'steps': [
                        {'range': [0, lim['temp_mancal']], 'color': "#e8f5e9"},
                        {'range': [lim['temp_mancal'], 100], 'color': "#ffebee"}
                    ]
                }
            ))
            fig_t.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig_t, use_container_width=True)

    elif aba == "Gráficos":
        st.markdown(f"## 📈 Histórico de Tendências - {dados_atual['nome']}")
        if not dados_atual['historico']:
            st.info("Aguardando telemetria...")
        else:
            df_hist = pd.DataFrame(dados_atual['historico'])
            
            st.subheader("📳 Vibração por Eixo (X, Y, Z)")
            fig_xyz = px.line(df_hist, x="Hora", y=["Vib_X", "Vib_Y", "Vib_Z"], 
                              title="Oscilação por Eixo em Tempo Real",
                              color_discrete_map={"Vib_X": "#004a8d", "Vib_Y": "#ff4b4b", "Vib_Z": "#ffa500"})
            st.plotly_chart(fig_xyz, use_container_width=True)
            
            st.divider()
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.plotly_chart(px.line(df_hist, x="Hora", y="Pressao_MCA", title="Pressão (MCA)", color_discrete_sequence=['#004a8d']), use_container_width=True)
                st.plotly_chart(px.line(df_hist, x="Hora", y="Temp_Mancal", title="Temp. Mancal (°C)", color_discrete_sequence=['#ff4b4b']), use_container_width=True)
            with col_g2:
                st.plotly_chart(px.area(df_hist, x="Hora", y="RMS_Vibracao", title="Vibração RMS", color_discrete_sequence=['#ffa500']), use_container_width=True)
                st.plotly_chart(px.line(df_hist, x="Hora", y="Temp_Oleo", title="Temp. Óleo (°C)", color_discrete_sequence=['#b22222']), use_container_width=True)

    # ... [Resto do código de Alertas e Configurações permanece idêntico ao anterior] ...
    elif aba == "Alertas":
        st.markdown(f"### 🔔 Eventos: {dados_atual['nome']}")
        alt = [a for a in dados_atual['alertas'] if not a['Reconhecido']]
        if not alt: st.success("Sem alertas pendentes.")
        else:
            for i, a in enumerate(alt):
                with st.container(border=True):
                    c_st, c_tx, c_btn = st.columns([0.15, 0.65, 0.2])
                    cor = "#ff4b4b" if a['Status'] == "CRÍTICO" else "#ffa500"
                    c_st.markdown(f"<div style='background-color:{cor}; color:white; padding:8px; border-radius:5px; text-align:center;'>{a['Status']}</div>", unsafe_allow_html=True)
                    c_tx.markdown(f"**{a['Sensor']}** - {a['Mensagem']}\n\n🕒 {a['Hora']} | Valor: {a['Valor']}")
                    if c_btn.button("OK", key=f"btn_{id_sel}_{i}"):
                        a['Reconhecido'] = True
                        st.rerun()

    elif aba == "Configurações":
        st.title("⚙️ Configuração e Relatórios")
        if not st.session_state.autenticado:
            with st.container(border=True):
                st.warning("🔒 Área Restrita")
                senha = st.text_input("Senha de Administrador:", type="password")
                if st.button("Entrar"):
                    if senha == "admin123":
                        st.session_state.autenticado = True
                        st.rerun()
                    else: st.error("Senha inválida!")
        else:
            if st.sidebar.button("Logoff 🔓"):
                st.session_state.autenticado = False
                st.rerun()
            st.subheader("📄 Exportar Dados")
            if dados_atual['historico']:
                df_export = pd.DataFrame(dados_atual['historico'])
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Telemetria')
                st.download_button(label="📥 Baixar Histórico em Excel", data=output.getvalue(), 
                                   file_name=f"relatorio_{id_sel}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.divider()
            with st.form("form_limites"):
                st.subheader("🔧 Ajuste de Limites")
                c1, c2 = st.columns(2)
                atuais = st.session_state.limites
                with c1:
                    n_mancal = st.number_input("Limite Mancal (°C)", value=atuais['temp_mancal'])
                    n_oleo = st.number_input("Limite Óleo (°C)", value=atuais['temp_oleo'])
                    n_rms = st.number_input("Limite RMS (mm/s²)", value=atuais['vib_rms'], format="%.3f")
                with c2:
                    n_p_max = st.number_input("Limite Máximo (Bar)", value=atuais['pressao_max_bar'])
                    n_p_min = st.number_input("Limite Mínimo (Bar)", value=atuais['pressao_min_bar'])
                if st.form_submit_button("💾 Salvar Definitivamente"):
                    novos = {'temp_mancal': n_mancal, 'temp_oleo': n_oleo, 'vib_rms': n_rms, 'pressao_max_bar': n_p_max, 'pressao_min_bar': n_p_min}
                    st.session_state.limites.update(novos)
                    salvar_configuracoes_arquivo(novos)
                    st.success("Configurações salvas!")