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
    st.session_state.limites = carregar_configuracoes()

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# --- 3. PROCESSADOR DE DADOS UNIFICADO ---
def processar_dados_recebidos(params):
    try:
        # Converte listas do Streamlit em valores únicos
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
            
            ponto = {
                "Data_Hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 
                "Hora": datetime.now().strftime("%H:%M:%S"),
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

# Captura via URL Streamlit
if st.query_params:
    processar_dados_recebidos(st.query_params.to_dict())

# Servidor Flask
app_flask = Flask(__name__)
CORS(app_flask)
@app_flask.route('/update', methods=['GET'])
def update():
    if processar_dados_recebidos(request.args.to_dict()):
        return "OK", 200
    return "Erro", 400

if 'thread_ativa' not in st.session_state:
    def rodar_flask():
        try: app_flask.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        except: pass
    threading.Thread(target=rodar_flask, daemon=True).start()
    st.session_state['thread_ativa'] = True

# --- 4. LÓGICA DE ALERTAS E CONEXÃO ---
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
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO ACIMA DO LIMITE", dados['pressao_bar']))
    elif 0.1 < dados['pressao_bar'] < lim['pressao_min_bar']:
        novos.append(("Pressão", "CRÍTICO", "PRESSÃO BAIXA - ADUTORA", dados['pressao_bar']))
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

# --- 5. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Monitor de Ativos", layout="wide")
st_autorefresh(interval=3000, key="refresh_global")
atualizar_status_conexao()

with st.sidebar:
    st.markdown("<div style='text-align: center;'><img src='https://cdn-icons-png.flaticon.com/512/3105/3105807.png' width='80'></div>", unsafe_allow_html=True)
    st.divider()
    
    id_sel = st.selectbox("📍 Selecionar Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']} - {memoria[x]['local']}")
    
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

# --- 6. RENDERIZAÇÃO ---
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
    lay_g = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=30, r=30, t=50, b=20))

    with col_g1:
        fig_v = go.Figure(go.Indicator(
            mode = "gauge+number", value = dados_atual['rms'],
            title = {'text': "Vibração (RMS)", 'font': {'color': "#004a8d", 'size': 18}},
            gauge = {
                'axis': {'range': [0, 5]}, 'bar': {'color': "#ffa500"},
                'steps': [{'range': [0, lim['vib_rms']], 'color': "#e3f2fd"},
                          {'range': [lim['vib_rms'], 5], 'color': "#ffebee"}],
                'threshold': {'line': {'color': "red", 'width': 4}, 'value': lim['vib_rms']}
            }
        ))
        fig_v.update_layout(lay_g)
        st.plotly_chart(fig_v, use_container_width=True)

    with col_g2:
        fig_p = go.Figure(go.Indicator(
            mode = "gauge+number", value = dados_atual['pressao_bar'],
            title = {'text': "Pressão (Bar)", 'font': {'color': "#004a8d", 'size': 18}},
            gauge = {
                'axis': {'range': [0, 12]}, 'bar': {'color': "#0097d7"},
                'steps': [{'range': [0, 2], 'color': "#ffebee"}, {'range': [2, 12], 'color': "#e3f2fd"}]
            }
        ))
        fig_p.update_layout(lay_g)
        st.plotly_chart(fig_p, use_container_width=True)

    with col_g3:
        fig_t = go.Figure(go.Indicator(
            mode = "gauge+number", value = dados_atual['mancal'],
            title = {'text': "Temp. Mancal (°C)", 'font': {'color': "#004a8d", 'size': 18}},
            gauge = {
                'axis': {'range': [0, 100]}, 'bar': {'color': "#ff4b4b"},
                'steps': [{'range': [0, lim['temp_mancal']], 'color': "#e3f2fd"},
                          {'range': [lim['temp_mancal'], 100], 'color': "#ffebee"}]
            }
        ))
        fig_t.update_layout(lay_g)
        st.plotly_chart(fig_t, use_container_width=True)

elif aba == "Gráficos":
    st.markdown(f"## 📈 Tendências - {dados_atual['nome']}")
    if not dados_atual['historico']:
        st.info("Aguardando telemetria...")
    else:
        df_hist = pd.DataFrame(dados_atual['historico'])
        fig_xyz = px.line(df_hist, x="Hora", y=["Vib_X", "Vib_Y", "Vib_Z"], title="Eixos de Vibração")
        fig_xyz.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_xyz, use_container_width=True)

elif aba == "Alertas":
    st.markdown("### 🔔 Central de Alertas")
    alt = [a for a in dados_atual['alertas'] if not a['Reconhecido']]
    if not alt: st.success("Sistema operando sem pendências.")
    else:
        for i, a in enumerate(alt):
            with st.container(border=True):
                c_st, c_tx, c_btn = st.columns([0.15, 0.65, 0.2])
                c_st.error(a['Status'])
                c_tx.write(f"**{a['Sensor']}**: {a['Mensagem']} em {a['Hora']}")
                if c_btn.button("✔ Reconhecer", key=f"ack_{i}"):
                    a['Reconhecido'] = True
                    st.rerun()

elif aba == "Configurações":
    st.markdown("## ⚙️ Configurações do Sistema")
    if not st.session_state.autenticado:
        col_log = st.columns([1, 2, 1])
        with col_log[1]:
            senha = st.text_input("Senha Admin:", type="password")
            if st.button("Liberar Acesso"):
                if senha == "admin123":
                    st.session_state.autenticado = True
                    st.rerun()
                else: st.error("Acesso Negado")
    else:
        if st.button("Encerrar Sessão 🔓"):
            st.session_state.autenticado = False
            st.rerun()
        st.divider()
        st.subheader("🔧 Ajuste de Limites Críticos")
        with st.form("limites_operacionais"):
            atuais = st.session_state.limites
            c_l1, c_l2 = st.columns(2)
            n_mancal = c_l1.number_input("Temp. Mancal Máx (°C)", value=float(atuais['temp_mancal']))
            n_rms = c_l2.number_input("Vibração RMS Máx (mm/s²)", value=float(atuais['vib_rms']), format="%.3f")
            c_l3, c_l4 = st.columns(2)
            n_p_max = c_l3.number_input("Pressão Máxima (Bar)", value=float(atuais['pressao_max_bar']))
            n_p_min = c_l4.number_input("Pressão Mínima (Bar)", value=float(atuais['pressao_min_bar']))
            if st.form_submit_button("💾 Salvar Configurações"):
                atuais.update({'temp_mancal': n_mancal, 'vib_rms': n_rms, 'pressao_max_bar': n_p_max, 'pressao_min_bar': n_p_min})
                salvar_configuracoes_arquivo(atuais)
                st.success("Limites atualizados!")

        st.divider()
        st.subheader("📊 Exportação de Dados")
        if dados_atual['historico']:
            df_exp = pd.DataFrame(dados_atual['historico'])
            towrite = io.BytesIO()
            df_exp.to_excel(towrite, index=False, engine='openpyxl')
            st.download_button(label="📥 Baixar Histórico em Excel", data=towrite.getvalue(), file_name=f"relatorio_{id_sel}.xlsx", mime="application/vnd.ms-excel")
