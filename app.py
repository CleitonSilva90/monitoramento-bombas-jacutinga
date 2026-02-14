import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# =========================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS (CSS)
# =========================================================
st.set_page_config(page_title="Concórdia Saneamento GS Inima", layout="wide")

st.markdown("""
<style>
/* Fundo Geral */
.stApp { background-color: #F4F8FB; }

/* Sidebar Customizada */
[data-testid="stSidebar"] { background-color: #E0FFFF; }
[data-testid="stSidebar"] * { color: #00BFFF !important; }

/* Cards de Monitoramento */
.pump-card {
    background-color: white;
    padding: 20px;
    border-radius: 12px;
    border-top: 8px solid #10b981; /* Verde padrão */
    box-shadow: 0 10px 15px rgba(0,0,0,0.05);
    margin-bottom: 20px;
}
.card-offline { border-top-color: #d1d5db !important; opacity: 0.7; }
.card-alert { border-top-color: #ff4b4b !important; }

.stat-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f3f4f6; }
.stat-label { color: #6b7280; font-weight: 500; font-size: 0.9rem; }
.stat-value { color: #111827; font-weight: 700; }

/* Estilo Login */
.login-container {
    max-width: 420px;
    margin: auto;
    padding: 40px;
    background: white;
    border-radius: 18px;
    border: 1px solid #D6EAF8;
    box-shadow: 0px 15px 35px rgba(0,0,0,0.08);
    text-align: center;
}
.login-title { color: #003366; font-weight: 700; margin-bottom: 10px; }

/* Botões */
div.stButton > button {
    background-color: #00BFFF;
    color: white;
    font-weight: 600;
    border-radius: 8px;
    height: 45px;
    border: none;
    transition: 0.3s;
}
div.stButton > button:hover { background-color: #009ACD; border: none; }
</style>
""", unsafe_allow_html=True)

# Auto Refresh (10 segundos)
st_autorefresh(interval=10000, key="globalrefresh")

# =========================================================
# 2. CONEXÃO SUPABASE (Insira suas credenciais aqui)
# =========================================================
URL = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY" 
supabase = create_client(URL, KEY)

# =========================================================
# 3. FUNÇÕES DE BUSCA
# =========================================================
def buscar_todos_status():
    try:
        res = supabase.table("status_atual").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

def buscar_historico(ids):
    try:
        res = supabase.table("historico").select("*").in_("id_bomba", ids).order("data_hora", desc=True).limit(1000).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# =========================================================
# 4. TELA DE LOGIN
# =========================================================
if 'usuario' not in st.session_state:
    st.write("##")
    col1, col_login, col3 = st.columns([1, 1.3, 1])
    with col_login:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        try:
            st.image("logo.png", width=220)
        except:
            st.title("GS INIMA")
        st.markdown('<h2 class="login-title">Acesso ao Sistema</h2>', unsafe_allow_html=True)
        u_input = st.text_input("Usuário", key="user")
        p_input = st.text_input("Senha", type="password", key="pass")
        if st.button("ACESSAR SISTEMA", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("usuario", u_input).eq("senha", p_input).execute()
            if res.data:
                st.session_state.usuario = res.data[0]
                st.rerun()
            else:
                st.error("Credenciais incorretas.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# =========================================================
# 5. ESTRUTURA E MENU
# =========================================================
df_status = buscar_todos_status()

st.sidebar.subheader(f"👤 {st.session_state.usuario['nome']}")
if st.sidebar.button("🚪 LOGOFF"):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("NAVEGAÇÃO", ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA"])

# Lista de ativos da planta
locais = {
    "JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"],
    "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]
}

# =========================================================
# 6. VISÃO GERAL
# =========================================================
if menu == "🌍 VISÃO GERAL":
    st.title("🏭 Monitoramento em Tempo Real")

    for local, lista in locais.items():
        st.subheader(f"📍 {local}")
        cols = st.columns(3) # Fixado em 3 para manter o padrão visual

        for i, id_b in enumerate(lista):
            with cols[i % 3]:
                row = df_status[df_status['id_bomba'] == id_b]
                
                if not row.empty:
                    val = row.iloc[0]
                    # Lógica simples de alerta (pode ser expandida conforme suas configs)
                    st.markdown(f"""
                    <div class="pump-card">
                        <h3 style="margin-top:0; color:#003366;">{id_b.upper()}</h3>
                        <div class="stat-row"><span class="stat-label">⛽ Pressão</span><span class="stat-value">{val['pressao']:.2f} bar</span></div>
                        <div class="stat-row"><span class="stat-label">🌡️ Mancal</span><span class="stat-value">{val['mancal']:.1f} °C</span></div>
                        <div class="stat-row"><span class="stat-label">🔥 Óleo</span><span class="stat-value">{val.get('oleo',0):.1f} °C</span></div>
                        <div class="stat-row"><span class="stat-label">📳 RMS</span><span class="stat-value">{val['rms']:.2f}</span></div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Card Offline para ativos sem dados no banco
                    st.markdown(f"""
                    <div class="pump-card card-offline">
                        <h3 style="margin-top:0; color:#9ca3af;">{id_b.upper()}</h3>
                        <p style="text-align:center; padding: 20px 0; color:#9ca3af;">SEM COMUNICAÇÃO</p>
                    </div>
                    """, unsafe_allow_html=True)

# =========================================================
# 7. ANÁLISE TÉCNICA (GRÁFICOS)
# =========================================================
elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Análise de Tendências")

    # Seleção de ativos
    todos_ativos = [b for l in locais.values() for b in l]
    escolha = st.multiselect("Selecione os ativos para comparar:", todos_ativos, default=[todos_ativos[0]])

    if escolha:
        df_h = buscar_historico(escolha)

        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            tab1, tab2, tab3 = st.tabs(["📉 Pressão", "🌡️ Temperatura", "📳 Vibração"])
            
            cores = px.colors.qualitative.Bold # Paleta de cores distintas

            # --- TABELA 1: PRESSÃO ---
            with tab1:
                fig1 = go.Figure()
                for i, ativo in enumerate(escolha):
                    df_f = df_h[df_h["id_bomba"] == ativo]
                    fig1.add_trace(go.Scatter(
                        x=df_f["data_hora"], y=df_f["pressao"],
                        mode="lines", name=f"{ativo.upper()}",
                        line=dict(color=cores[i % len(cores)], width=2.5)
                    ))
                fig1.update_layout(template="plotly_white", hovermode="x unified", legend_title="Ativos")
                st.plotly_chart(fig1, use_container_width=True)

            # --- TABELA 2: TEMPERATURA (Mancal e Óleo) ---
            with tab2:
                fig2 = go.Figure()
                for i, ativo in enumerate(escolha):
                    df_f = df_h[df_h["id_bomba"] == ativo]
                    cor = cores[i % len(cores)]

                    # Mancal (Linha Contínua)
                    fig2.add_trace(go.Scatter(
                        x=df_f["data_hora"], y=df_f["mancal"],
                        mode="lines", name=f"{ativo.upper()} - Mancal",
                        line=dict(color=cor, width=2.5)
                    ))

                    # Óleo (Linha Tracejada)
                    if 'oleo' in df_f.columns:
                        fig2.add_trace(go.Scatter(
                            x=df_f["data_hora"], y=df_f["oleo"],
                            mode="lines", name=f"{ativo.upper()} - Óleo",
                            line=dict(color=cor, width=2, dash="dash")
                        ))

                fig2.update_layout(template="plotly_white", hovermode="x unified", legend_title="Sensores")
                st.plotly_chart(fig2, use_container_width=True)

            # --- TABELA 3: VIBRAÇÃO (RMS) ---
            with tab3:
                fig3 = go.Figure()
                for i, ativo in enumerate(escolha):
                    df_f = df_h[df_h["id_bomba"] == ativo]
                    fig3.add_trace(go.Scatter(
                        x=df_f["data_hora"], y=df_f["rms"],
                        mode="lines", name=f"{ativo.upper()}",
                        line=dict(color=cores[i % len(cores)], width=2.5)
                    ))
                fig3.update_layout(template="plotly_white", hovermode="x unified", legend_title="Ativos")
                st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Nenhum dado histórico encontrado para os ativos selecionados.")
