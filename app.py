import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import threading
import time
import math
import json
import os
from datetime import datetime
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh
from supabase import create_client
import io

# =====================================================
# 🔥 CONFIGURAÇÃO STREAMLIT (OBRIGATORIAMENTE PRIMEIRO)
# =====================================================
st.set_page_config(page_title="Monitor de Ativos", layout="wide")

# =====================================================
# 1. CONEXÃO BANCO (SUPABASE)
# =====================================================
URL_SUPABASE = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

# =====================================================
# 2. FUNÇÕES DE PERSISTÊNCIA
# =====================================================
ARQUIVO_CONFIG = 'config_bombas.json'

def carregar_configuracoes():
    padrao = {
        'temp_mancal': 70.0,
        'temp_oleo': 65.0,
        'vib_rms': 2.8,
        'pressao_max_bar': 10.0,
        'pressao_min_bar': 2.0
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

# =====================================================
# 3. MEMÓRIA GLOBAL (CACHE)
# =====================================================
@st.cache_resource
def obter_memoria_global():
    base = {
        "mancal": 0.0, "oleo": 0.0,
        "vx": 0.0, "vy": 0.0, "vz": 0.0,
        "rms": 0.0, "pressao_bar": 0.0,
        "historico": [], "alertas": [],
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

# =====================================================
# 4. PROCESSADOR DE DADOS
# =====================================================
def processar_dados_recebidos(params):
    try:
        dados = {k: (v[0] if isinstance(v, list) else v) for k, v in params.items()}
        id_b = dados.get('id', 'jacutinga_b01')

        if id_b not in memoria:
            return False

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
            'vx': vx, 'vy': vy, 'vz': vz,
            'rms': v_rms,
            'mancal': mancal, 'oleo': oleo,
            'pressao_bar': p_bar,
            'ultimo_visto': time.time(),
            'online': True
        })

        ponto = {
            "Data_Hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Hora": datetime.now().strftime("%H:%M:%S"),
            "RMS_Vibracao": round(v_rms, 3),
            "Vib_X": vx, "Vib_Y": vy, "Vib_Z": vz,
            "Temp_Mancal": mancal,
            "Temp_Oleo": oleo,
            "Pressao_Bar": p_bar,
            "Pressao_MCA": round(p_bar * 10.197, 2)
        }

        memoria[id_b]['historico'].append(ponto)
        if len(memoria[id_b]['historico']) > 1000:
            memoria[id_b]['historico'].pop(0)

        with open(f"sync_{id_b}.json", "w") as f:
            json.dump({
                'vx': vx, 'vy': vy, 'vz': vz,
                'rms': v_rms,
                'mancal': mancal,
                'oleo': oleo,
                'pressao_bar': p_bar,
                'ultimo_visto': time.time(),
                'online': True,
                'historico': memoria[id_b]['historico'][-100:],
                'alertas': memoria[id_b]['alertas']
            }, f)

        # SUPABASE
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

        return True
    except:
        return False

# =====================================================
# 5. API (QUERY PARAMS)
# =====================================================
query_params = dict(st.query_params)

if 'id' in query_params:
    if processar_dados_recebidos(query_params):
        st.write("OK")
        st.stop()
    else:
        st.error("Erro ao processar dados")
        st.stop()

# =====================================================
# 6. SINCRONIZAÇÃO
# =====================================================
def sincronizar_dados():
    agora = time.time()
    for id_b in memoria:
        arq = f"sync_{id_b}.json"
        if os.path.exists(arq):
            try:
                with open(arq) as f:
                    dados = json.load(f)
                    for k in dados:
                        memoria[id_b][k] = dados[k]
            except:
                pass
        if memoria[id_b]['ultimo_visto'] and agora - memoria[id_b]['ultimo_visto'] > 60:
            memoria[id_b]['online'] = False

st_autorefresh(interval=3000, key="refresh_global")
sincronizar_dados()

# =====================================================
# 7. ALERTAS
# =====================================================
def verificar_alertas(id_b):
    dados = memoria[id_b]
    lim = st.session_state.limites
    agora_f = datetime.now().strftime("%d/%m/%Y %H:%M")
    novos = []

    if dados['pressao_bar'] > lim['pressao_max_bar']:
        novos.append(("Pressão","CRÍTICO","PRESSÃO ACIMA DO LIMITE",dados['pressao_bar']))
    if 0.1 < dados['pressao_bar'] < lim['pressao_min_bar']:
        novos.append(("Pressão","CRÍTICO","PRESSÃO BAIXA",dados['pressao_bar']))
    if dados['mancal'] > lim['temp_mancal']:
        novos.append(("Temp. Mancal","CRÍTICO","LIMITE EXCEDIDO",dados['mancal']))
    if dados['rms'] > lim['vib_rms']:
        novos.append(("Vibração","CRÍTICO","VIBRAÇÃO ELEVADA",dados['rms']))

    for s, stt, msg, v in novos:
        if not any(a['Mensagem'] == msg and not a['Reconhecido'] for a in dados['alertas']):
            dados['alertas'].insert(0,{
                "Equipamento": dados['nome'],
                "Sensor": s,
                "Mensagem": msg,
                "Hora": agora_f,
                "Valor": round(v,2),
                "Status": stt,
                "Reconhecido": False
            })
    return any(not a['Reconhecido'] for a in dados['alertas'])

# =====================================================
# 8. INTERFACE (SIDEBAR + ABAS)
# =====================================================
with st.sidebar:
    st.markdown("<div style='text-align:center;'><img src='https://cdn-icons-png.flaticon.com/512/3105/3105807.png' width='80'></div>", unsafe_allow_html=True)
    st.divider()
    id_sel = st.selectbox("📍 Selecionar Ativo:", list(memoria.keys()), format_func=lambda x: f"{memoria[x]['nome']} - {memoria[x]['local']}")
    for id_b, d in memoria.items():
        st.write(f"{'🟢' if d['online'] else '🔴'} **{d['nome']}**")
    st.divider()
    aba = option_menu(None, ["Dashboard","Gráficos","Alertas","Configurações"],
        icons=["speedometer2","graph-up","bell-fill","gear-fill"], default_index=0)

tem_alerta = verificar_alertas(id_sel)
dados_atual = memoria[id_sel]

# =====================================================
# 9. DASHBOARD
# =====================================================
if aba == "Dashboard":
    col_tit, col_sts = st.columns([0.7,0.3])
    with col_tit:
        st.markdown(f"## 🚀 {dados_atual['nome']} - {dados_atual['local']}")
    with col_sts:
        if not dados_atual['online']:
            st.markdown("⚪ OFFLINE")
        elif tem_alerta:
            st.markdown("⚠️ ALERTA")
        else:
            st.markdown("✅ NORMAL")

    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌡️ Temp. Mancal", f"{dados_atual['mancal']:.1f} °C")
    c2.metric("🌡️ Temp. Óleo", f"{dados_atual['oleo']:.1f} °C")
    c3.metric("📳 Vibração RMS", f"{dados_atual['rms']:.3f}")
    c4.metric("💧 Pressão Saída", f"{dados_atual['pressao_bar']*10.197:.1f} MCA")

elif aba == "Gráficos":
    st.markdown("## 📈 Gráficos")
    if dados_atual['historico']:
        df = pd.DataFrame(dados_atual['historico'])
        st.plotly_chart(px.line(df, x="Hora", y="RMS_Vibracao"), use_container_width=True)

elif aba == "Alertas":
    st.markdown("## 🔔 Alertas")
    for a in dados_atual['alertas']:
        if not a['Reconhecido']:
            st.error(f"{a['Sensor']}: {a['Mensagem']}")

elif aba == "Configurações":
    st.markdown("## ⚙️ Configurações")
    st.write("Configurações mantidas conforme código original")
