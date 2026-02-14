import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Concórdia Saneamento GS Inima", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F4F8FB; }
    [data-testid="stSidebar"] { background-color: #E0FFFF; }
    [data-testid="stSidebar"] * { color: #00BFFF !important; }
    
    /* Banner de Alerta */
    .alert-banner {
        background: linear-gradient(90deg, #ff4b4b 0%, #b91c1c 100%);
        color: white; padding: 15px; border-radius: 10px;
        text-align: center; font-weight: bold; margin-bottom: 20px;
    }

    /* Cards */
    .pump-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border-top: 8px solid #10b981; box-shadow: 0 10px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #f3f4f6; }
    .stat-label { color: #6b7280; font-weight: 500; }
    .stat-value { color: #111827; font-weight: 700; }
    .value-critical { color: #ff4b4b !important; font-weight: 800; }

    /* Login Customizado */
    .login-container {
        max-width: 400px; margin: auto; padding: 40px;
        background: white; border-radius: 15px; text-align: center;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

st_autorefresh(interval=10000, key="globalrefresh")

# --- 2. CONEXÃO E FUNÇÕES ---
URL = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY" 
supabase = create_client(URL, KEY)

def buscar_configuracoes():
    try:
        res = supabase.table("configuracoes").select("*").eq("id", 1).execute()
        return res.data[0]
    except:
        return {"limite_pressao": 2.0, "limite_mancal": 75.0, "limite_oleo": 80.0, "limite_rms": 5.0, "senha_acesso": "1234"}

def buscar_todos_status():
    res = supabase.table("status_atual").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_historico(ids):
    res = supabase.table("historico").select("*").in_("id_bomba", ids).order("data_hora", desc=True).limit(500).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 3. LOGIN ---
if 'usuario' not in st.session_state:
    st.write("#")
    col1, col_login, col3 = st.columns([1, 1.2, 1])
    with col_login:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.image("logo.png", width=250) # Imagem da GS Inima
        st.markdown("### Acesso ao Sistema")
        u_input = st.text_input("Usuário")
        p_input = st.text_input("Senha", type="password")
        if st.button("ACESSAR", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("usuario", u_input).eq("senha", p_input).execute()
            if res.data:
                st.session_state.usuario = res.data[0]
                st.rerun()
            else:
                st.error("Credenciais inválidas")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 4. PROCESSAMENTO DE ALERTAS ---
config = buscar_configuracoes()
df_status = buscar_todos_status()
alertas_ativos = []

if not df_status.empty:
    for _, row in df_status.iterrows():
        b_id = row['id_bomba'].upper()
        if row['pressao'] < config['limite_pressao']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Pressão", "valor": row['pressao'], "limite": config['limite_pressao']})
        if row['mancal'] > config['limite_mancal']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Mancal", "valor": row['mancal'], "limite": config['limite_mancal']})
        if row.get('oleo', 0) > config['limite_oleo']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Óleo", "valor": row['oleo'], "limite": config['limite_oleo']})

if alertas_ativos:
    st.markdown(f'<div class="alert-banner">🚨 SISTEMA EM ALERTA: {len(alertas_ativos)} EVENTOS CRÍTICOS</div>', unsafe_allow_html=True)

# --- 5. SIDEBAR ---
st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.markdown(f"**Operador:** {st.session_state.usuario['nome']}")
menu = st.sidebar.radio("NAVEGAÇÃO", ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA", "🚨 ALARMES", "⚙️ CONFIGURAÇÕES"])
if st.sidebar.button("Sair"):
    del st.session_state.usuario
    st.rerun()

locais = {"JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"], "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]}

# --- 6. TELAS ---
if menu == "🌍 VISÃO GERAL":
    st.title("🏭 Monitoramento de Ativos")
    for local, lista in locais.items():
        st.subheader(f"📍 {local}")
        cols = st.columns(3)
        for i, id_b in enumerate(lista):
            with cols[i % 3]:
                row = df_status[df_status['id_bomba'] == id_b]
                if not row.empty:
                    val = row.iloc[0]
                    tem_alerta = any(a['bomba'] == id_b.upper() for a in alertas_ativos)
                    cor_borda = "#ff4b4b" if tem_alerta else "#10b981"
                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: {cor_borda}">
                            <h3>{id_b.upper()}</h3>
                            <div class="stat-row"><span>Pressão</span><b class="{'value-critical' if val['pressao'] < config['limite_pressao'] else ''}">{val['pressao']:.2f} bar</b></div>
                            <div class="stat-row"><span>Mancal</span><b class="{'value-critical' if val['mancal'] > config['limite_mancal'] else ''}">{val['mancal']:.1f} °C</b></div>
                            <div class="stat-row"><span>Óleo</span><b class="{'value-critical' if val.get('oleo',0) > config['limite_oleo'] else ''}">{val.get('oleo',0):.1f} °C</b></div>
                            <div class="stat-row"><span>RMS</span><b>{val['rms']:.2f}</b></div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="pump-card" style="border-top-color:#d1d5db; opacity:0.5;"><h3>{id_b.upper()}</h3>OFF-LINE</div>', unsafe_allow_html=True)

elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Gráficos de Tendência")
    ativos_sel = st.multiselect("Selecionar Ativos:", [b for l in locais.values() for b in l], default=["jacutinga_b01"])
    if ativos_sel:
        df_h = buscar_historico(ativos_sel)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            t1, t2 = st.tabs(["💧 Pressão", "🔥 Temperaturas"])
            
            # Paleta de cores para garantir uma cor por ativo
            cores_ativos = px.colors.qualitative.Set1 

            with t1:
                fig1 = px.line(df_h, x="data_hora", y="pressao", color="id_bomba", 
                               color_discrete_sequence=cores_ativos, template="plotly_white")
                st.plotly_chart(fig1, use_container_width=True)
            
            with t2:
                fig2 = go.Figure()
                for i, ativo in enumerate(ativos_sel):
                    df_ativo = df_h[df_h['id_bomba'] == ativo]
                    cor = cores_ativos[i % len(cores_ativos)]
                    # Mancal - Linha Contínua
                    fig2.add_trace(go.Scatter(x=df_ativo['data_hora'], y=df_ativo['mancal'], name=f"{ativo} (Mancal)", line=dict(color=cor)))
                    # Óleo - Linha Tracejada
                    fig2.add_trace(go.Scatter(x=df_ativo['data_hora'], y=df_ativo['oleo'], name=f"{ativo} (Óleo)", line=dict(color=cor, dash='dash')))
                fig2.update_layout(template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig2, use_container_width=True)

elif menu == "🚨 ALARMES":
    st.title("🔔 Central de Alarmes")
    if not alertas_ativos:
        st.success("Sistema Operacional - Nenhum alarme pendente.")
    else:
        for a in alertas_ativos:
            with st.expander(f"⚠️ {a['bomba']} - {a['sensor']}", expanded=True):
                st.write(f"Valor atual: **{a['valor']}** | Limite: **{a['limite']}**")
                if st.button("Reconhecer Alarme", key=f"btn_{a['bomba']}_{a['sensor']}"):
                    st.toast("Alarme reconhecido pelo operador.")

elif menu == "⚙️ CONFIGURAÇÕES":
    st.title("⚙️ Configurações de Limites")
    pw = st.text_input("Senha de Configuração", type="password")
    if pw == config['senha_acesso']:
        with st.form("config_form"):
            c1, c2 = st.columns(2)
            p_lim = c1.number_input("Mín. Pressão", value=float(config['limite_pressao']))
            m_lim = c1.number_input("Max. Mancal", value=float(config['limite_mancal']))
            o_lim = c2.number_input("Max. Óleo", value=float(config['limite_oleo']))
            r_lim = c2.number_input("Max. RMS", value=float(config['limite_rms']))
            if st.form_submit_button("Salvar Alterações"):
                supabase.table("configuracoes").update({"limite_pressao": p_lim, "limite_mancal": m_lim, "limite_oleo": o_lim, "limite_rms": r_lim}).eq("id", 1).execute()
                st.success("Configurações atualizadas!")
                st.rerun()
    elif pw != "":
        st.error("Senha incorreta")
