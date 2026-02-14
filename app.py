import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Concórdia Saneamento GS Inima", layout="wide")

if 'reconhecidos' not in st.session_state:
    st.session_state.reconhecidos = []

st.markdown("""
    <style>
    .stApp { background-color: #F4F8FB; }
    [data-testid="stSidebar"] { background-color: #E0FFFF; }
    [data-testid="stSidebar"] * { color: #00BFFF !important; }
    .login-box { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 80px; }
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

# --- 2. CONEXÃO ---
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

# --- TELA DE LOGIN ATRAENTE ---
if 'usuario' not in st.session_state:
    # Esconde a barra lateral na tela de login
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none; }
            
            /* Fundo da tela de login */
            .stApp {
                background: linear-gradient(135deg, #00BFFF 0%, #001F3F 100%);
            }

            /* Container do Cartão de Login */
            .login-card {
                background: rgba(255, 255, 255, 0.95);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 15px 35px rgba(0,0,0,0.2);
                text-align: center;
                max-width: 400px;
                margin: auto;
            }

            /* Estilo dos campos de texto */
            .stTextInput>div>div>input {
                border-radius: 10px !important;
                border: 1px solid #ddd !important;
                height: 45px;
            }

            /* Estilo do botão */
            .stButton>button {
                width: 100%;
                background-color: #00BFFF !important;
                color: white !important;
                font-weight: bold !important;
                height: 50px;
                border-radius: 10px !important;
                border: none !important;
                transition: 0.3s;
            }
            .stButton>button:hover {
                background-color: #0080FF !important;
                transform: scale(1.02);
            }
        </style>
    """, unsafe_allow_html=True)

    # Layout centralizado
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.image("logo.png", width=280)  # Sua logo da GS Inima
        
        st.markdown("### Painel de Monitoramento")
        u_input = st.text_input("Usuário", placeholder="Digite seu usuário")
        p_input = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        
        st.write("") # Espaçamento
        
        if st.button("ENTRAR NO SISTEMA"):
            res = supabase.table("usuarios").select("*").eq("usuario", u_input).eq("senha", p_input).execute()
            if res.data:
                st.session_state.usuario = res.data[0]
                st.rerun()
            else:
                st.error("⚠️ Usuário ou senha incorretos.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:white; margin-top:20px; font-size:12px;">© 2026 Concórdia Saneamento - GS Inima Group</p>', unsafe_allow_html=True)
    
    st.stop()

# --- 4. ALARMES ---
config = buscar_configuracoes()
df_status = buscar_todos_status()
alertas_reais = [] # O que está errado fisicamente
alertas_visiveis = [] # O que ainda não foi reconhecido

if not df_status.empty:
    for _, row in df_status.iterrows():
        b_id = row['id_bomba'].upper()
        # Verificação física
        erro = False
        if row['pressao'] < config['limite_pressao'] or row['mancal'] > config['limite_mancal'] or row.get('oleo', 0) > config['limite_oleo']:
            erro = True
            alertas_reais.append(b_id)
            if b_id not in st.session_state.reconhecidos:
                alertas_visiveis.append({"bomba": b_id, "detalhe": f"Falha detectada em {b_id}"})

if alertas_visiveis:
    st.markdown(f'<div class="alert-banner">🚨 SISTEMA EM ALERTA: {len(alertas_visiveis)} EVENTO(S) NÃO RECONHECIDO(S)</div>', unsafe_allow_html=True)

# --- 5. SIDEBAR ---
st.sidebar.image("logo.png") 
menu = st.sidebar.radio("NAVEGAÇÃO", ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA", "🚨 CENTRAL DE ALERTAS", "⚙️ CONFIGURAÇÕES"])
if st.sidebar.button("🚪 SAIR"):
    st.session_state.clear()
    st.rerun()

locais = {"JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"], "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]}

# --- 6. TELAS ---
if menu == "🌍 VISÃO GERAL":
    st.title("🏭 Dashboard Operacional")
    for local, lista in locais.items():
        st.subheader(f"📍 {local}")
        cols = st.columns(3)
        for i, id_b in enumerate(lista):
            with cols[i % 3]:
                row = df_status[df_status['id_bomba'] == id_b]
                if not row.empty:
                    val = row.iloc[0]
                    # Borda fica vermelha se houver erro REAL (mesmo reconhecido)
                    cor_borda = '#ff4b4b' if id_b.upper() in alertas_reais else '#10b981'
                    cp = "value-critical" if val['pressao'] < config['limite_pressao'] else ""
                    cm = "value-critical" if val['mancal'] > config['limite_mancal'] else ""
                    
                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: {cor_borda}">
                            <h3>{id_b.upper()}</h3>
                            <div class="stat-row"><span>Pressão</span><b class="{cp}">{val['pressao']:.2f} bar</b></div>
                            <div class="stat-row"><span>Mancal</span><b class="{cm}">{val['mancal']:.1f} °C</b></div>
                            <div class="stat-row"><span>RMS</span><b>{val['rms']:.2f}</b></div>
                        </div>
                    """, unsafe_allow_html=True)

elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Histórico")
    sel = st.multiselect("Bomba(s):", [b for l in locais.values() for b in l], default=["jacutinga_b01"])
    if sel:
        df_h = buscar_historico(sel)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            t1, t2, t3 = st.tabs(["📉 Pressão", "🌡️ Temperaturas", "📳 Vibração"])
            with t1:
                fig1 = go.Figure()
                for a in sel:
                    d = df_h[df_h['id_bomba'] == a]
                    fig1.add_trace(go.Scatter(x=d['data_hora'], y=d['pressao'], name=a, line=dict(color='#00BFFF')))
                fig1.add_hline(y=config['limite_pressao'], line_dash="dot", line_color="red")
                st.plotly_chart(fig1, use_container_width=True)
            with t3:
                eixos = st.multiselect("Eixos:", ["rms", "vx", "vy", "vz"], default=["rms"])
                fig3 = go.Figure()
                for a in sel:
                    d = df_h[df_h['id_bomba'] == a]
                    for e in eixos: fig3.add_trace(go.Scatter(x=d['data_hora'], y=d[e], name=f"{a}-{e}"))
                st.plotly_chart(fig3, use_container_width=True)

elif menu == "🚨 CENTRAL DE ALERTAS":
    st.title("🔔 Alarmes Pendentes")
    if not alertas_visiveis: st.success("Nenhum alarme pendente de reconhecimento.")
    else:
        for a in alertas_visiveis:
            c1, c2 = st.columns([4, 1])
            c1.error(f"Alerta Crítico: {a['bomba']}")
            if c2.button("Reconhecer", key=f"rec_{a['bomba']}"):
                st.session_state.reconhecidos.append(a['bomba'])
                st.rerun()

elif menu == "⚙️ CONFIGURAÇÕES":
    st.title("⚙️ Gestão de Sistema")
    pw = st.text_input("Senha Mestre", type="password")
    if pw == config['senha_acesso']:
        with st.form("limites"):
            st.subheader("Configurar Limites")
            p = st.number_input("Mín. Pressão", value=float(config['limite_pressao']))
            m = st.number_input("Max. Mancal", value=float(config['limite_mancal']))
            if st.form_submit_button("SALVAR LIMITES"):
                supabase.table("configuracoes").update({"limite_pressao": p, "limite_mancal": m}).eq("id", 1).execute()
                st.success("Limites atualizados!")
        
        st.markdown("---")
        st.subheader("👤 Cadastrar Novo Usuário")
        with st.form("novo_user"):
            nu = st.text_input("Nome de Usuário")
            np = st.text_input("Senha", type="password")
            if st.form_submit_button("CADASTRAR"):
                supabase.table("usuarios").insert({"usuario": nu, "senha": np}).execute()
                st.success(f"Usuário {nu} cadastrado!")
