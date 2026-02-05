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

# --- 1. CONFIGURAÇÕES E PERSISTÊNCIA ---
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

# --- 3. PROCESSADOR DE DADOS (CRUCIAL PARA O CÓDIGO 200) ---
def processar_entrada(params):
    try:
        # O Streamlit envia query_params como listas. Precisamos extrair o primeiro item.
        dados = {k: (v[0] if isinstance(v, list) else v) for k, v in params.items()}
        
        id_b = dados.get('id', 'jacutinga_b01')
        if id_b in memoria:
            def safe_f(v):
                try: return float(v)
                except: return 0.0

            vx = safe_f(dados.get('vx', 0))
            vy = safe_f(dados.get('vy', 0))
            vz = safe_f(dados.get('vz', 0))
            mancal = safe_f(dados.get('mancal', 0))
            oleo = safe_f(dados.get('oleo', 0))
            p_bar = safe_f(dados.get('pressao', 0))
            
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
    except:
        return False
    return False

# Esta linha captura o que o seu ESP32 está enviando (image_2d9623.png)
if st.query_params:
    processar_entrada(st.query_params.to_dict())

# Servidor Flask (Mantido para compatibilidade local)
app_flask = Flask(__name__)
CORS(app_flask)
@app_flask.route('/update', methods=['GET'])
def update():
    if processar_entrada(request.args.to_dict()):
        return "OK", 200
    return "Erro", 400

if 'thread_ativa' not in st.session_state:
    def rodar_flask():
        try: app_flask.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        except: pass
    threading.Thread(target=rodar_flask, daemon=True).start()
    st.session_state['thread_ativa'] = True

# --- 4. LÓGICA DE STATUS E ALERTAS ---
def atualizar_status_conexao():
    agora = time.time()
    for id_b in memoria:
        visto = memoria[id_b].get('ultimo_visto')
        if visto and (agora - visto > 60): 
            memoria[id_b]['online'] = False

def verificar_alertas(id_b):
    dados = memoria[id_b]
    lim = st.session_state.limites
    agora_f = datetime.now().strftime("%d/%m/%Y %H:%M")
    novos = []
    
    if dados['pressao_bar'] > lim['pressao_max_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO ALTA", dados['pressao_bar']))
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

# --- 5. INTERFACE (RESTALRADA) ---
st.set_page_config(page_title="Monitor Jacutinga", layout="wide", page_icon="🚀")
st_autorefresh(interval=3000, key="refresh_global")
atualizar_status_conexao()

with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>⚙️ MENU</h2>", unsafe_allow_html=True)
    id_sel = st.selectbox("Selecionar Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']}")
    
    st.markdown("### Status Conexão")
    for id_b, d in memoria.items():
        cor = "🟢" if d['online'] else "🔴"
        st.write(f"{cor} {d['nome']}")

    st.divider()
    aba = option_menu(None, ["Dashboard", "Gráficos", "Alertas", "Configurações"], 
                      icons=["speedometer2", "graph-up", "bell", "gear"], 
                      default_index=0, styles={"nav-link-selected": {"background-color": "#004a8d"}})

dados_atual = memoria[id_sel]
tem_alerta = verificar_alertas(id_sel)

if aba == "Dashboard":
    c_tit, c_sts = st.columns([0.8, 0.2])
    with c_tit:
        st.title(f"🚀 {dados_atual['nome']} - {dados_atual['local']}")
    with c_sts:
        status_txt = "⚠️ ALERTA" if tem_alerta else "✅ NORMAL"
        cor_sts = "#ff4b4b" if tem_alerta else "#28a745"
        if not dados_atual['online']: status_txt = "⚪ OFFLINE"; cor_sts = "#555"
        st.markdown(f"<div style='background-color:{cor_sts}; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>{status_txt}</div>", unsafe_allow_html=True)

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🌡️ Temp. Mancal", f"{dados_atual['mancal']:.1f} °C")
    m2.metric("🌡️ Temp. Óleo", f"{dados_atual['oleo']:.1f} °C")
    m3.metric("📳 Vibração (RMS)", f"{dados_atual['rms']:.3f} mm/s²")
    m4.metric("💧 Pressão", f"{dados_atual['pressao_bar'] * 10.197:.1f} MCA")

    st.markdown("### Indicadores de Performance")
    g1, g2, g3 = st.columns(3)
    
    with g1:
        fig1 = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['rms'], title={'text': "Vibração RMS"},
            gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "#ffa500"}, 'threshold': {'line': {'color': "red", 'width': 4}, 'value': st.session_state.limites['vib_rms']}}))
        fig1.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig1, use_container_width=True)

    with g2:
        fig2 = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['pressao_bar'], title={'text': "Pressão (Bar)"},
            gauge={'axis': {'range': [0, 15]}, 'bar': {'color': "#0097d7"}}))
        fig2.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig2, use_container_width=True)

    with g3:
        fig3 = go.Figure(go.Indicator(mode="gauge+number", value=dados_atual['mancal'], title={'text': "Temp. Mancal °C"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ff4b4b"}, 'threshold': {'line': {'color': "red", 'width': 4}, 'value': st.session_state.limites['temp_mancal']}}))
        fig3.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig3, use_container_width=True)

elif aba == "Gráficos":
    st.subheader(f"📈 Tendências Históricas - {dados_atual['nome']}")
    if not dados_atual['historico']:
        st.info("Aguardando telemetria...")
    else:
        df = pd.DataFrame(dados_atual['historico'])
        st.plotly_chart(px.line(df, x="Hora", y=["Vib_X", "Vib_Y", "Vib_Z"], title="Vibração por Eixo"), use_container_width=True)
        
        c_l, c_r = st.columns(2)
        with c_l:
            st.plotly_chart(px.line(df, x="Hora", y="Pressao_Bar", title="Pressão (Bar)"), use_container_width=True)
        with c_r:
            st.plotly_chart(px.line(df, x="Hora", y="Temp_Mancal", title="Temperatura (°C)"), use_container_width=True)

elif aba == "Alertas":
    st.subheader("🔔 Gerenciamento de Alertas")
    pendentes = [a for a in dados_atual['alertas'] if not a['Reconhecido']]
    if not pendentes:
        st.success("Tudo em ordem!")
    else:
        for i, a in enumerate(pendentes):
            with st.container(border=True):
                col_a, col_b = st.columns([0.8, 0.2])
                col_a.error(f"**{a['Sensor']}**: {a['Mensagem']} (Valor: {a['Valor']}) - {a['Hora']}")
                if col_b.button("✅ Reconhecer", key=f"btn_{i}"):
                    a['Reconhecido'] = True
                    st.rerun()

elif aba == "Configurações":
    st.subheader("⚙️ Configurações e Relatórios")
    if not st.session_state.autenticado:
        senha = st.text_input("Senha Admin:", type="password")
        if st.button("Entrar"):
            if senha == "admin123": st.session_state.autenticado = True; st.rerun()
            else: st.error("Incorreto")
    else:
        if st.button("Logoff 🔓"): st.session_state.autenticado = False; st.rerun()
        
        with st.form("set_limites"):
            l = st.session_state.limites
            new_t = st.number_input("Temp. Mancal Máx (°C)", value=l['temp_mancal'])
            new_v = st.number_input("Vibração RMS Máx (mm/s²)", value=l['vib_rms'])
            if st.form_submit_button("Salvar Alterações"):
                st.session_state.limites.update({'temp_mancal': new_t, 'vib_rms': new_v})
                salvar_configuracoes_arquivo(st.session_state.limites)
                st.success("Configurações salvas!")

        if dados_atual['historico']:
            st.divider()
            df_exp = pd.DataFrame(dados_atual['historico'])
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False)
            st.download_button("📥 Baixar Histórico em Excel", output.getvalue(), "relatorio_jacutinga.xlsx")
