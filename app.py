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
    # Estrutura base para cada bomba
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

# Inicialização de estados de sessão
if 'limites' not in st.session_state:
    st.session_state.limites = carregar_configuracoes()

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- 3. SERVIDOR FLASK (RECEBIMENTO DE DADOS) ---
app_flask = Flask(__name__)
CORS(app_flask)

@app_flask.route('/update', methods=['GET'])
def update():
    try:
        id_b = request.args.get('id', 'jacutinga_b01')
        
        def safe_float(v):
            try: return float(v)
            except: return 0.0

        vx = safe_float(request.args.get('vx', 0))
        vy = safe_float(request.args.get('vy', 0))
        vz = safe_float(request.args.get('vz', 0))
        mancal = safe_float(request.args.get('mancal', 0))
        oleo = safe_float(request.args.get('oleo', 0))
        p_bar = safe_float(request.args.get('pressao', 0))
        
        # Cálculo do RMS de Vibração
        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        if id_b in memoria:
            # Atualiza dados instantâneos
            memoria[id_b].update({
                'vx': vx, 'vy': vy, 'vz': vz, 'rms': v_rms, 
                'mancal': mancal, 'oleo': oleo, 'pressao_bar': p_bar,
                'ultimo_visto': time.time(), 'online': True
            })
            
            # Adiciona ao histórico
            agora = datetime.now()
            ponto = {
                "Data_Hora": agora.strftime("%d/%m/%Y %H:%M:%S"), 
                "Hora": agora.strftime("%H:%M:%S"),
                "RMS_Vibracao": round(v_rms, 3), 
                "Vib_X": vx, "Vib_Y": vy, "Vib_Z": vz,
                "Temp_Mancal": mancal, 
                "Temp_Oleo": oleo,
                "Pressao_Bar": p_bar,
                "Pressao_MCA": round(p_bar * 10.197, 2)
            }
            memoria[id_b]['historico'].append(ponto)
            
            # Limita histórico a 1000 registros
            if len(memoria[id_b]['historico']) > 1000: 
                memoria[id_b]['historico'].pop(0)
                
            return "OK", 200
    except Exception as e: 
        return f"Erro: {str(e)}", 500
    return "ID Inválido", 400

# Inicia o Flask em uma thread separada
if 'thread_ativa' not in st.session_state:
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False), daemon=True).start()
    st.session_state['thread_ativa'] = True

# --- 4. LÓGICA DE ALERTAS E STATUS ---
def atualizar_status_conexao():
    agora = time.time()
    for id_b in memoria:
        visto = memoria[id_b].get('ultimo_visto')
        if visto and (agora - visto > 60): # 60 segundos sem dados = Offline
            memoria[id_b]['online'] = False

def verificar_alertas(id_b):
    dados = memoria[id_b]
    lim = st.session_state.limites
    agora_f = datetime.now().strftime("%d/%m/%Y %H:%M")
    novos = []
    
    # Regras de Alerta
    if dados['pressao_bar'] > lim['pressao_max_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO ACIMA DO LIMITE", dados['pressao_bar']))
    elif 0.1 < dados['pressao_bar'] < lim['pressao_min_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO BAIXA - ADUTORA", dados['pressao_bar']))
    
    if dados['mancal'] > lim['temp_mancal']:
        novos.append(("Temp. Mancal", "CRÍTICO", "LIMITE EXCEDIDO", dados['mancal']))
    
    if dados['rms'] > lim['vib_rms']:
        novos.append(("Vibração", "CRÍTICO", "VIBRAÇÃO ELEVADA", dados['rms']))

    # Adiciona novos alertas se não existirem alertas ativos iguais
    for sensor, status, msg, valor in novos:
        if not any(a['Mensagem'] == msg and not a['Reconhecido'] for a in dados['alertas']):
            dados['alertas'].insert(0, {
                "Equipamento": f"{dados['nome']}", "Sensor": sensor, "Mensagem": msg, 
                "Hora": agora_f, "Valor": round(valor, 2), "Status": status, "Reconhecido": False
            })
    return any(not a['Reconhecido'] for a in dados['alertas'])

# --- 5. CONFIGURAÇÃO DA INTERFACE STREAMLIT ---
st.set_page_config(page_title="Monitor de Ativos Jacutinga", layout="wide")
st_autorefresh(interval=3000, key="refresh_global") # Atualiza a UI a cada 3s
atualizar_status_conexao()

with st.sidebar:
    st.markdown("<div style='text-align: center;'><img src='https://cdn-icons-png.flaticon.com/512/3105/3105807.png' width='80'></div>", unsafe_allow_html=True)
    st.divider()
    
    id_sel = st.selectbox("📍 Selecionar Ativo:", list(memoria.keys()), 
                          format_func=lambda x: f"{memoria[x]['nome']} - {memoria[x]['local']}")
    
    st.markdown("### 🌐 Status de Conexão")
    for id_b, d in memoria.items():
        cor_led = "🟢" if d['online'] else "🔴"
        st.write(f"{cor_led} **{d['nome']}**")

    st.divider()
    aba = option_menu(
        menu_title=None, 
        options=["Dashboard", "Gráficos", "Alertas", "Configurações"],
        icons=["speedometer2", "graph-up", "bell-fill", "gear-fill"], 
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#004a8d"}},
        key="menu_principal"
    )

tem_alerta = verificar_alertas(id_sel)
dados_atual = memoria[id_sel]

# --- 6. RENDERIZAÇÃO DAS ABAS ---

if aba == "Dashboard":
    col_tit, col_sts = st.columns([0.7, 0.3])
    with col_tit:
        st.markdown(f"## 🚀 {dados_atual['nome']} - {dados_atual['local']}")
    with col_sts:
        if not dados_atual['online']:
            st.markdown("<div style='background-color:#555; color:white; padding:10px; border-radius:10px; text-align:center;'>⚪ OFFLINE</div>", unsafe_allow_html=True)
        elif tem_alerta:
            st.markdown("<div style='background-color:#ff4b4b; color:white; padding:10px; border-radius:10px; text-align:center; font-weight:bold;'>⚠️ ATENÇÃO: ALERTA</div>", unsafe_allow_html=True)
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
    
    # Layout comum para remover fundo cinza dos gráficos
    lay_g = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=30, r=30, t=50, b=20))

    with col_g1:
        fig_v = go.Figure(go.Indicator(
            mode = "gauge+number", value = dados_atual['rms'],
            title = {'text': "Vibração (RMS)", 'font': {'color': "#004a8d", 'size': 18}},
            gauge = {
                'axis': {'range': [0, lim['vib_rms']*1.5]},
                'bar': {'color': "#ffa500", 'thickness': 1},
                'bgcolor': "#f0f2f6",
                'steps': [
                    {'range': [0, lim['vib_rms']], 'color': "#e3f2fd"},
                    {'range': [lim['vib_rms'], lim['vib_rms']*1.5], 'color': "#ffebee"}
                ],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.8, 'value': lim['vib_rms']}
            }
        ))
        fig_v.update_layout(lay_g)
        st.plotly_chart(fig_v, width="stretch")

    with col_g2:
        fig_p = go.Figure(go.Indicator(
            mode = "gauge+number", value = dados_atual['pressao_bar'],
            title = {'text': "Pressão (Bar)", 'font': {'color': "#004a8d", 'size': 18}},
            gauge = {
                'axis': {'range': [0, 12]},
                'bar': {'color': "#0097d7", 'thickness': 1},
                'bgcolor': "#f0f2f6",
                'steps': [
                    {'range': [0, 2], 'color': "#ffebee"},
                    {'range': [2, 12], 'color': "#e3f2fd"}
                ]
            }
        ))
        fig_p.update_layout(lay_g)
        st.plotly_chart(fig_p, width="stretch")

    with col_g3:
        fig_t = go.Figure(go.Indicator(
            mode = "gauge+number", value = dados_atual['mancal'],
            title = {'text': "Temp. Mancal (°C)", 'font': {'color': "#004a8d", 'size': 18}},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': "#ff4b4b", 'thickness': 1},
                'bgcolor': "#f0f2f6",
                'steps': [
                    {'range': [0, lim['temp_mancal']], 'color': "#e3f2fd"},
                    {'range': [lim['temp_mancal'], 100], 'color': "#ffebee"}
                ]
            }
        ))
        fig_t.update_layout(lay_g)
        st.plotly_chart(fig_t, width="stretch")

elif aba == "Gráficos":
    st.markdown(f"## 📈 Tendências - {dados_atual['nome']}")
    if not dados_atual['historico']:
        st.info("Aguardando telemetria...")
    else:
        df_hist = pd.DataFrame(dados_atual['historico'])
        
        fig_xyz = px.line(df_hist, x="Hora", y=["Vib_X", "Vib_Y", "Vib_Z"], 
                          title="Oscilação por Eixo",
                          color_discrete_map={"Vib_X": "#004a8d", "Vib_Y": "#ff4b4b", "Vib_Z": "#ffa500"})
        fig_xyz.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_xyz, width="stretch")
        
        c_l, c_r = st.columns(2)
        with c_l:
            st.plotly_chart(px.line(df_hist, x="Hora", y="Pressao_MCA", title="Pressão (MCA)", color_discrete_sequence=['#004a8d']), width="stretch")
        with c_r:
            st.plotly_chart(px.line(df_hist, x="Hora", y="Temp_Mancal", title="Temp. Mancal (°C)", color_discrete_sequence=['#ff4b4b']), width="stretch")

elif aba == "Alertas":
    st.markdown(f"### 🔔 Eventos: {dados_atual['nome']}")
    alt_pendentes = [a for a in dados_atual['alertas'] if not a['Reconhecido']]
    
    if not alt_pendentes: 
        st.success("Sem alertas pendentes.")
    else:
        for i, a in enumerate(alt_pendentes):
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
            
        # Exportação de Relatórios
        if dados_atual['historico']:
            st.subheader("📊 Exportar Dados")
            df_export = pd.DataFrame(dados_atual['historico'])
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False)
            st.download_button("📥 Baixar Histórico Excel", output.getvalue(), f"relatorio_{id_sel}.xlsx")
        
        # Ajuste de Limites Técnicos
        with st.form("form_limites"):
            st.subheader("🔧 Ajuste de Limites")
            atuais = st.session_state.limites
            n_mancal = st.number_input("Limite Mancal (°C)", value=atuais['temp_mancal'])
            n_rms = st.number_input("Limite RMS (mm/s²)", value=atuais['vib_rms'], format="%.3f")
            n_p_max = st.number_input("Pressão Máxima (Bar)", value=atuais['pressao_max_bar'])
            n_p_min = st.number_input("Pressão Mínima (Bar)", value=atuais['pressao_min_bar'])
            
            if st.form_submit_button("💾 Salvar Configurações"):
                atuais.update({
                    'temp_mancal': n_mancal, 
                    'vib_rms': n_rms,
                    'pressao_max_bar': n_p_max,
                    'pressao_min_bar': n_p_min
                })
                salvar_configuracoes_arquivo(atuais)
                st.success("Configurações salvas com sucesso!")
