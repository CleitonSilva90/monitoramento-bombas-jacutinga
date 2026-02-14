import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Telemetria Industrial Jacutinga", layout="wide")

# Atualiza o dashboard automaticamente a cada 10 segundos
st_autorefresh(interval=10000, key="globalrefresh")

# --- 2. CONEXÃO SUPABASE ---
URL = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY" # COLOQUE SUA CHAVE AQUI
supabase = create_client(URL, KEY)

# --- 3. FUNÇÕES DE BANCO DE DADOS ---
@st.cache_data(ttl=10)
def buscar_configuracoes():
    res = supabase.table("configuracoes").select("*").eq("id", 1).execute()
    return res.data[0] if res.data else None

def buscar_todos_status():
    res = supabase.table("status_atual").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_historico(ids_selecionados):
    res = supabase.table("historico").select("*").in_("id_bomba", ids_selecionados).order("data_hora", desc=True).limit(500).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# Carrega as configurações (Limites e Senha)
config = buscar_configuracoes()

# --- 4. SIDEBAR (NAVEGAÇÃO) ---
st.sidebar.title("🏭 Controle de Ativos")
menu = st.sidebar.radio("Navegação", ["Resumo Geral", "Análise Individual", "Configurar Alarmes"])

locais = {
    "Jacutinga": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"],
    "Intermediária": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]
}

# --- 5. TELAS ---

if menu == "Resumo Geral":
    st.title("📋 Status Atual das Bombas")
    df_status = buscar_todos_status()
    
    for local, lista in locais.items():
        st.subheader(f"📍 Unidade {local}")
        cols = st.columns(3)
        for i, id_b in enumerate(lista):
            with cols[i]:
                row = df_status[df_status['id_bomba'] == id_b]
                if not row.empty:
                    val = row.iloc[0]
                    # Lógica de cor baseada no limite de pressão salvo no banco
                    cor = "red" if val['pressao'] > config['limite_pressao'] or val['mancal'] > config['limite_mancal'] else "#2E8B57"
                    
                    st.markdown(f"""
                        <div style="padding:20px; border-radius:10px; border-top: 10px solid {cor}; background-color: #f8f9fa; box-shadow: 2px 2px 5px rgba(0,0,0,0.1)">
                            <h3 style="margin:0; color:#333">{id_b.upper()}</h3>
                            <hr>
                            <p style="margin:0"><b>Pressão:</b> {val['pressao']:.2f} bar</p>
                            <p style="margin:0"><b>Mancal:</b> {val['mancal']:.1f} °C</p>
                            <p style="margin:0"><b>Vibração RMS:</b> {val['rms']:.2f}</p>
                            <p style="margin-top:10px; font-size:11px; color:gray">🕒 {val['ultima_batida'][:19]}</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ {id_b.upper()}: Sem conexão")

elif menu == "Análise Individual":
    st.title("📈 Análise de Tendências")
    ativos = st.multiselect("Selecione os ativos:", [b for l in locais.values() for b in l], default=[locais["Jacutinga"][0]])
    
    if ativos:
        df_h = buscar_historico(ativos)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            
            tab1, tab2, tab3 = st.tabs(["Pressão", "Temperaturas", "Vibração Detalhada"])
            
            with tab1:
                st.plotly_chart(px.line(df_h, x="data_hora", y="pressao", color="id_bomba", title="Evolução da Pressão (Bar)"), use_container_width=True)
            with tab2:
                st.plotly_chart(px.line(df_h, x="data_hora", y=["mancal", "oleo"], color="id_bomba", title="Temperaturas (°C)"), use_container_width=True)
            with tab3:
                # Permite escolher quais eixos de vibração ver
                eixos = st.multiselect("Escolha os eixos de vibração:", ["rms", "vx", "vy", "vz"], default=["rms"])
                st.plotly_chart(px.line(df_h, x="data_hora", y=eixos, color="id_bomba", title="Vibração por Eixo"), use_container_width=True)

elif menu == "Configurar Alarmes":
    st.title("🚨 Configurações do Sistema")
    senha = st.text_input("Digite a senha administrativa", type="password")
    
    if senha == config['senha_acesso']:
        st.success("Acesso liberado!")
        with st.form("form_ajustes"):
            col1, col2 = st.columns(2)
            with col1:
                p_max = st.number_input("Limite Pressão (bar)", value=config['limite_pressao'])
                r_max = st.number_input("Limite Vibração RMS", value=config['limite_rms'])
            with col2:
                m_max = st.number_input("Limite Temp. Mancal (°C)", value=config['limite_mancal'])
                o_max = st.number_input("Limite Temp. Óleo (°C)", value=config['limite_oleo'])
            
            nova_senha = st.text_input("Nova Senha", value=config['senha_acesso'])
            
            if st.form_submit_button("SALVAR ALTERAÇÕES"):
                update = {
                    "limite_pressao": p_max, "limite_rms": r_max,
                    "limite_mancal": m_max, "limite_oleo": o_max,
                    "senha_acesso": nova_senha
                }
                supabase.table("configuracoes").update(update).eq("id", 1).execute()
                st.success("Configurações salvas no banco de dados!")
                st.rerun()
    elif senha != "":
        st.error("Senha incorreta.")

