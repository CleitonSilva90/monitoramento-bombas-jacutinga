import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

# --- 1. CONFIGURAÇÃO VISUAL MODERNA ---
st.set_page_config(page_title="PRO-TELEMETRY | Indústria 4.0", layout="wide")

# CSS para Estilo Industrial Profissional
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #111827; color: white; }
    .main { background-color: #f3f4f6; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .pump-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border-top: 8px solid #10b981; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #f3f4f6; }
    .stat-label { color: #6b7280; font-weight: 500; }
    .stat-value { color: #111827; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# Auto-refresh a cada 10 segundos
st_autorefresh(interval=10000, key="globalrefresh")

# --- 2. CONEXÃO SUPABASE (Substitua pela sua KEY real) ---
URL = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY" 
supabase = create_client(URL, KEY)

# --- 3. FUNÇÕES DE BANCO DE DADOS ---
def buscar_configuracoes():
    try:
        res = supabase.table("configuracoes").select("*").eq("id", 1).execute()
        return res.data[0] if res.data else None
    except:
        return {"limite_pressao": 25.0, "limite_mancal": 75.0, "limite_oleo": 80.0, "limite_rms": 5.0, "senha_acesso": "1234"}

def buscar_todos_status():
    res = supabase.table("status_atual").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_historico(ids_selecionados):
    res = supabase.table("historico").select("*").in_("id_bomba", ids_selecionados).order("data_hora", desc=True).limit(500).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# Carregar Configurações Atuais
config = buscar_configuracoes()

# --- 4. SIDEBAR ---
st.sidebar.title("🎛️ CORE CONTROL")
st.sidebar.markdown("---")
menu = st.sidebar.selectbox("NAVEGAÇÃO", ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA", "⚙️ CONFIGURAÇÕES"])

locais = {
    "JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"],
    "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]
}

# --- 5. TELAS ---

if menu == "🌍 VISÃO GERAL":
    st.title("🏭 Monitoramento de Ativos")
    df_status = buscar_todos_status()
    
    for local, lista in locais.items():
        st.subheader(f"📍 {local}")
        cols = st.columns(3)
        for i, id_b in enumerate(lista):
            with cols[i]:
                row = df_status[df_status['id_bomba'] == id_b]
                if not row.empty:
                    val = row.iloc[0]
                    # Lógica de Alerta (Se qualquer valor ultrapassar o limite, fica vermelho)
                    alert = (val['pressao'] > config['limite_pressao'] or 
                             val['mancal'] > config['limite_mancal'] or 
                             val.get('oleo', 0) > config['limite_oleo'] or
                             val['rms'] > config['limite_rms'])
                    
                    cor_borda = "#ef4444" if alert else "#10b981"
                    
                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: {cor_borda}">
                            <h3 style="margin:0;">{id_b.upper()}</h3>
                            <p style="font-size:12px; color:gray;">Sinal: {val['ultima_batida'][11:19]}</p>
                            <div class="stat-row"><span class="stat-label">⛽ Pressão</span><span class="stat-value">{val['pressao']:.2f} bar</span></div>
                            <div class="stat-row"><span class="stat-label">🌡️ Mancal</span><span class="stat-value">{val['mancal']:.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">🔥 Óleo</span><span class="stat-value">{val.get('oleo', 0):.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">📳 Vibração (RMS)</span><span class="stat-value">{val['rms']:.2f}</span></div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: #d1d5db; color: #9ca3af;">
                            <h3>{id_b.upper()}</h3>
                            <p>OFF-LINE</p>
                        </div>
                    """, unsafe_allow_html=True)

elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Gráficos de Tendência")
    todos_ativos = [b for l in locais.values() for b in l]
    selecionados = st.multiselect("Selecione os ativos para análise:", todos_ativos, default=[todos_ativos[0]])
    
    if selecionados:
        df_h = buscar_historico(selecionados)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            
            t1, t2, t3 = st.tabs(["📉 Pressão", "🌡️ Temperaturas", "📳 Vibração (Eixos)"])
            
            with t1:
                st.plotly_chart(px.line(df_h, x="data_hora", y="pressao", color="id_bomba", template="plotly_white"), use_container_width=True)
            with t2:
                st.plotly_chart(px.line(df_h, x="data_hora", y=["mancal", "oleo"], color="id_bomba", template="plotly_white"), use_container_width=True)
            with t3:
                eixos = st.multiselect("Eixos de Vibração:", ["rms", "vx", "vy", "vz"], default=["rms", "vx"])
                st.plotly_chart(px.line(df_h, x="data_hora", y=eixos, color="id_bomba", template="plotly_white"), use_container_width=True)

elif menu == "⚙️ CONFIGURAÇÕES":
    st.title("🔐 Configuração de Alarmes")
    senha_input = st.text_input("Senha de Acesso", type="password")
    
    if senha_input == config['senha_acesso']:
        st.success("Acesso Liberado")
        with st.form("set_alarms"):
            c1, c2 = st.columns(2)
            with c1:
                p_max = st.number_input("Limite Pressão (bar)", value=float(config['limite_pressao']))
                m_max = st.number_input("Limite Temp. Mancal (°C)", value=float(config['limite_mancal']))
            with c2:
                o_max = st.number_input("Limite Temp. Óleo (°C)", value=float(config['limite_oleo']))
                r_max = st.number_input("Limite Vibração RMS", value=float(config['limite_rms']))
            
            nova_senha = st.text_input("Alterar Senha", value=config['senha_acesso'])
            
            if st.form_submit_button("GRAVAR CONFIGURAÇÕES NO BANCO"):
                novos_dados = {
                    "limite_pressao": p_max, "limite_mancal": m_max,
                    "limite_oleo": o_max, "limite_rms": r_max,
                    "senha_acesso": nova_senha
                }
                supabase.table("configuracoes").update(novos_dados).eq("id", 1).execute()
                st.success("Configurações atualizadas com sucesso!")
                st.rerun()
    elif senha_input != "":
        st.error("Senha Incorreta")
