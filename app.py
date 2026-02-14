import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Concórdia Saneamento GS Inima", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F4F8FB; }
    [data-testid="stSidebar"] { background-color: #E0FFFF; }
    [data-testid="stSidebar"] * { color: #00BFFF !important; }
    
    .login-box {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; margin-top: 80px;
    }

    .alert-banner {
        background: linear-gradient(90deg, #ff4b4b 0%, #b91c1c 100%);
        color: white; padding: 15px; border-radius: 10px;
        text-align: center; font-weight: bold; font-size: 1.1rem;
        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
    }

    .pump-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border-top: 8px solid #10b981; box-shadow: 0 10px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #f3f4f6; }
    .value-critical { color: #ff4b4b !important; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

st_autorefresh(interval=10000, key="globalrefresh")

# --- 2. CONEXÃO SUPABASE ---
URL = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY" 
supabase = create_client(URL, KEY)

def buscar_configuracoes():
    try:
        res = supabase.table("configuracoes").select("*").eq("id", 1).execute()
        return res.data[0] if res.data else None
    except:
        return {"limite_pressao": 2.0, "limite_mancal": 75.0, "limite_oleo": 80.0, "limite_rms": 5.0, "senha_acesso": "1234"}

def buscar_todos_status():
    res = supabase.table("status_atual").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_historico(ids):
    res = supabase.table("historico").select("*").in_("id_bomba", ids).order("data_hora", desc=True).limit(500).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 3. TELA DE LOGIN (CORREÇÃO DE PARÂMETRO) ---
if 'usuario' not in st.session_state:
    col1, col_login, col3 = st.columns([1, 1, 1])
    with col_login:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        # CORREÇÃO: use_container_width substituído por width="stretch" para evitar o erro do print
        st.image("logo.png", width=350) 
        u_input = st.text_input("Usuário")
        p_input = st.text_input("Senha", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("usuario", u_input).eq("senha", p_input).execute()
            if res.data:
                st.session_state.usuario = res.data[0]
                st.rerun()
            else: st.error("Acesso negado.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 4. LOGICA DE ALARMES ---
config = buscar_configuracoes()
df_status = buscar_todos_status()
alertas_ativos = []

if not df_status.empty:
    for _, row in df_status.iterrows():
        b_id = row['id_bomba'].upper()
        if row['pressao'] < config['limite_pressao']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Pressão", "valor": f"{row['pressao']:.2f}", "limite": config['limite_pressao']})
        if row['mancal'] > config['limite_mancal']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Mancal", "valor": f"{row['mancal']:.1f}", "limite": config['limite_mancal']})
        if row.get('oleo', 0) > config['limite_oleo']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Óleo", "valor": f"{row['oleo']:.1f}", "limite": config['limite_oleo']})

if alertas_ativos:
    st.markdown(f'<div class="alert-banner">🚨 SISTEMA EM ALERTA: {len(alertas_ativos)} EVENTO(S) DETECTADO(S)</div>', unsafe_allow_html=True)

# --- 5. SIDEBAR (CORREÇÃO DE PARÂMETRO) ---
st.sidebar.image("logo.png", width="stretch") # Corrigido aqui também
menu = st.sidebar.radio("NAVEGAÇÃO", ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA", "🚨 CENTRAL DE ALERTAS", "⚙️ CONFIGURAÇÕES"])
if st.sidebar.button("🚪 SAIR"):
    del st.session_state.usuario
    st.rerun()

locais = {"JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"], 
          "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]}

# --- 6. TELAS ---

if menu == "🌍 VISÃO GERAL":
    st.title("🏭 Monitoramento Real-Time")
    for local, lista in locais.items():
        st.subheader(f"📍 {local}")
        cols = st.columns(3)
        for i, id_b in enumerate(lista):
            with cols[i % 3]:
                row = df_status[df_status['id_bomba'] == id_b]
                if not row.empty:
                    val = row.iloc[0]
                    tem_a = any(a['bomba'] == id_b.upper() for a in alertas_ativos)
                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: {'#ff4b4b' if tem_a else '#10b981'}">
                            <h3>{id_b.upper()}</h3>
                            <div class="stat-row"><span>Pressão</span><b>{val['pressao']:.2f} bar</b></div>
                            <div class="stat-row"><span>Mancal</span><b>{val['mancal']:.1f} °C</b></div>
                            <div class="stat-row"><span>Óleo</span><b>{val.get('oleo',0):.1f} °C</b></div>
                            <div class="stat-row"><span>RMS</span><b>{val['rms']:.2f}</b></div>
                        </div>
                    """, unsafe_allow_html=True)
                else: st.markdown(f'<div class="pump-card" style="opacity:0.6;"><h3>{id_b.upper()}</h3>OFFLINE</div>', unsafe_allow_html=True)

elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Histórico de Ativos")
    sel_ativos = st.multiselect("Bomba(s):", [b for l in locais.values() for b in l], default=["jacutinga_b01"])
    
    if sel_ativos:
        df_h = buscar_historico(sel_ativos)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            t1, t2, t3 = st.tabs(["📉 Pressão", "🌡️ Temperaturas", "📳 Vibração (Multieixos)"])
            
            with t1:
                fig1 = go.Figure()
                for ativo in sel_ativos:
                    d = df_h[df_h['id_bomba'] == ativo]
                    fig1.add_trace(go.Scatter(x=d['data_hora'], y=d['pressao'], name=f"{ativo}", line=dict(color='#00BFFF')))
                fig1.add_hline(y=config['limite_pressao'], line_dash="dot", line_color="red", annotation_text="Limite Mín.")
                st.plotly_chart(fig1, use_container_width=True)

            with t2:
                fig2 = go.Figure()
                for ativo in sel_ativos:
                    d = df_h[df_h['id_bomba'] == ativo]
                    fig2.add_trace(go.Scatter(x=d['data_hora'], y=d['mancal'], name=f"{ativo} (Mancal)", line=dict(color='#FF4B4B')))
                    fig2.add_trace(go.Scatter(x=d['data_hora'], y=d['oleo'], name=f"{ativo} (Óleo)", line=dict(color='#FFA500', dash='dash')))
                fig2.add_hline(y=config['limite_mancal'], line_dash="dot", line_color="red", annotation_text="Alerta Mancal")
                fig2.add_hline(y=config['limite_oleo'], line_dash="dot", line_color="orange", annotation_text="Alerta Óleo")
                st.plotly_chart(fig2, use_container_width=True)

            with t3:
                eixos_sel = st.multiselect("Selecione os eixos:", ["rms", "vx", "vy", "vz"], default=["rms"])
                fig3 = go.Figure()
                estilos = {"rms": dict(color="#10b981", width=3), "vx": dict(color="#8E44AD", dash="dot"), 
                           "vy": dict(color="#2E4053", dash="dash"), "vz": dict(color="#D35400", dash="dashdot")}
                for ativo in sel_ativos:
                    d = df_h[df_h['id_bomba'] == ativo]
                    for eixo in eixos_sel:
                        if eixo in d.columns:
                            fig3.add_trace(go.Scatter(x=d['data_hora'], y=d[eixo], name=f"{ativo} ({eixo.upper()})", line=estilos[eixo]))
                fig3.add_hline(y=config['limite_rms'], line_dash="dot", line_color="red", annotation_text="Limite RMS")
                st.plotly_chart(fig3, use_container_width=True)

elif menu == "🚨 CENTRAL DE ALERTAS":
    st.title("🔔 Central de Alarmes")
    if not alertas_ativos: st.success("✅ Tudo normal.")
    else:
        for a in alertas_ativos:
            st.error(f"⚠️ **{a['bomba']}** | {a['sensor']} em **{a['valor']}** (Limite: {a['limite']})")
            if st.button(f"Reconhecer {a['bomba']} - {a['sensor']}"): st.toast("Alarme reconhecido.")

elif menu == "⚙️ CONFIGURAÇÕES":
    st.title("⚙️ Ajustes de Sistema")
    pw = st.text_input("Senha", type="password")
    if pw == config['senha_acesso']:
        with st.form("form_cfg"):
            p = st.number_input("Mín. Pressão", value=float(config['limite_pressao']))
            m = st.number_input("Max. Mancal", value=float(config['limite_mancal']))
            o = st.number_input("Max. Óleo", value=float(config['limite_oleo']))
            r = st.number_input("Max. RMS", value=float(config['limite_rms']))
            if st.form_submit_button("SALVAR"):
                supabase.table("configuracoes").update({"limite_pressao": p, "limite_mancal": m, "limite_oleo": o, "limite_rms": r}).eq("id", 1).execute()
                st.success("Salvo!")
                st.rerun()
