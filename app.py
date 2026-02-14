import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

# --- 1. CONFIGURAÇÃO VISUAL MODERNA ---
st.set_page_config(page_title="Concórdia Saneamento GS Inima", layout="wide")

st.markdown("""
    <style>
    /* Estilos da Sidebar */
    [data-testid="stSidebar"] { background-color: #FFFAFA; }
    [data-testid="stSidebar"] * { color: #00BFFF !important; }
    [data-testid="stWidgetLabel"] p { color: #00BFFF !important; font-size: 1.2rem !important; font-weight: 800 !important; text-shadow: 0px 0px 5px rgba(0, 191, 255, 0.2); }
    hr { border-color: #00BFFF !important; }

    /* Banner de Alerta Superior */
    .alert-banner {
        background: linear-gradient(90deg, #ff4b4b 0%, #b91c1c 100%);
        color: white; padding: 15px; border-radius: 10px;
        text-align: center; font-weight: bold; font-size: 1.1rem;
        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
    }

    /* Cards dos Ativos */
    .pump-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border-top: 8px solid #10b981; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        margin-bottom: 20px; min-height: 250px;
    }
    .stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #f3f4f6; }
    .stat-label { color: #6b7280; font-weight: 500; }
    .stat-value { color: #111827; font-weight: 700; }
    .value-critical { color: #ff4b4b !important; font-weight: 800; }
    
    /* Login Box */
  st.markdown("""
<style>

/* ===== FUNDO GERAL ===== */
.stApp {
    background-color: #F4F8FB;
}

/* ===== SIDEBAR ===== */
[data-testid="stSidebar"] { 
    background-color: #E0FFFF; 
}
[data-testid="stSidebar"] * { 
    color: #00BFFF !important; 
}

/* ===== LOGIN CONTAINER MODERNO ===== */
.login-container {
    max-width: 420px;
    margin: auto;
    padding: 40px 35px 35px 35px;
    background: white;
    border-radius: 18px;
    border: 1px solid #D6EAF8;
    box-shadow: 0px 15px 35px rgba(0,0,0,0.08);
    text-align: center;
}

/* ===== TÍTULO LOGIN ===== */
.login-title {
    color: #003366;
    font-weight: 700;
    margin-bottom: 10px;
}

/* ===== INPUTS ===== */
div[data-baseweb="input"] {
    border-radius: 8px !important;
}

/* ===== BOTÃO ===== */
div.stButton > button {
    background-color: #00BFFF;
    color: white;
    font-weight: 600;
    border-radius: 8px;
    height: 45px;
    border: none;
}

div.stButton > button:hover {
    background-color: #009ACD;
    color: white;
}

hr { 
    border-color: #00BFFF !important; 
}

</style>
""", unsafe_allow_html=True)


# Auto-refresh a cada 10 segundos
st_autorefresh(interval=10000, key="globalrefresh")

# --- 2. CONEXÃO SUPABASE ---
URL = "https://iemojjmgzyrxddochnlq.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY" 
supabase = create_client(URL, KEY)

# --- 3. FUNÇÕES DE BANCO DE DADOS ---
def buscar_configuracoes():
    try:
        res = supabase.table("configuracoes").select("*").eq("id", 1).execute()
        return res.data[0] if res.data else {"limite_pressao": 2.0, "limite_mancal": 75.0, "limite_oleo": 80.0, "limite_rms": 5.0}
    except:
        return {"limite_pressao": 2.0, "limite_mancal": 75.0, "limite_oleo": 80.0, "limite_rms": 5.0}

def buscar_todos_status():
    res = supabase.table("status_atual").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_historico(ids_selecionados):
    res = supabase.table("historico").select("*").in_("id_bomba", ids_selecionados).order("data_hora", desc=True).limit(1000).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_reconhecidos():
    res = supabase.table("logs_alertas").select("*").eq("status", "Reconhecido").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 4. TELA DE LOGIN ---
if 'usuario' not in st.session_state:

    col1, col_login, col3 = st.columns([1, 1.3, 1])

    with col_login:

        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        # Logo
        st.image("logo.png", width=220)

        # Título estilizado
        st.markdown(
            '<h2 class="login-title">Acesso ao Sistema</h2>',
            unsafe_allow_html=True
        )

        # Campos
        u_input = st.text_input("Usuário")
        p_input = st.text_input("Senha", type="password")

        st.markdown("<br>", unsafe_allow_html=True)

        # Botão
        if st.button("ACESSAR SISTEMA", use_container_width=True):
            res = supabase.table("usuarios") \
                .select("*") \
                .eq("usuario", u_input) \
                .eq("senha", p_input) \
                .execute()

            if res.data:
                st.session_state.usuario = res.data[0]
                st.rerun()
            else:
                st.error("Credenciais incorretas.")

        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()


# --- 5. PROCESSAMENTO DE ALERTAS ---
config = buscar_configuracoes()
df_status = buscar_todos_status()
df_recon = buscar_reconhecidos()

alertas_ativos = [] # Lista de alarmes reais acontecendo agora
alertas_criticos = [] # Lista de alarmes que NÃO foram reconhecidos ainda

if not df_status.empty:
    for _, row in df_status.iterrows():
        b_id = row['id_bomba'].lower()
        checks = [
            ("Pressão Saída", row['pressao'], config['limite_pressao'], "Mínima", row['pressao'] < config['limite_pressao']),
            ("Temp. Mancal", row['mancal'], config['limite_mancal'], "Máxima", row['mancal'] > config['limite_mancal']),
            ("Temp. Óleo", row.get('oleo', 0), config['limite_oleo'], "Máxima", row.get('oleo', 0) > config['limite_oleo']),
            ("Vibração RMS", row['rms'], config['limite_rms'], "Máxima", row['rms'] > config['limite_rms'])
        ]
        for s_nome, s_val, s_lim, s_tipo, em_erro in checks:
            if em_erro:
                alerta = {"bomba": b_id, "sensor": s_nome, "valor": s_val, "limite": s_lim, "tipo": s_tipo}
                alertas_ativos.append(alerta)
                ja_recon = not df_recon[(df_recon['bomba'] == b_id) & (df_recon['sensor'] == s_nome)].empty if not df_recon.empty else False
                if not ja_recon: alertas_criticos.append(alerta)

# Banner de Alerta Pendente
if alertas_criticos:
    st.markdown(f'<div class="alert-banner">🚨 SISTEMA EM ALERTA: {len(alertas_criticos)} EVENTOS NÃO RECONHECIDOS</div>', unsafe_allow_html=True)

# --- 6. SIDEBAR ---
st.sidebar.subheader(f"Logado como: {st.session_state.usuario['nome']}")
if st.sidebar.button("🚪 LOGOFF"):
    del st.session_state.usuario
    st.rerun()

st.sidebar.markdown("---")
opcoes_menu = ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA", "🚨 CENTRAL DE ALERTAS"]
if st.session_state.usuario['nivel_acesso'] == 'Admin':
    opcoes_menu += ["⚙️ CONFIGURAÇÕES", "👥 USUÁRIOS"]

menu = st.sidebar.radio("NAVEGAÇÃO", opcoes_menu)

locais = {
    "JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"],
    "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]
}

# --- 7. TELAS ---

if menu == "🌍 VISÃO GERAL":
    st.title("🏭 Monitoramento em Tempo Real")
    for local, lista in locais.items():
        st.subheader(f"📍 {local}")
        cols = st.columns(3)
        for i, id_b in enumerate(lista):
            with cols[i]:
                row = df_status[df_status['id_bomba'] == id_b]
                if not row.empty:
                    val = row.iloc[0]
                    # Borda vermelha apenas para alarmes NÃO reconhecidos
                    tem_pendencia = any(a['bomba'] == id_b for a in alertas_criticos)
                    cor_topo = "#ef4444" if tem_pendencia else "#10b981"
                    
                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: {cor_topo}">
                            <h3 style="margin:0;">{id_b.upper()}</h3>
                            <div class="stat-row"><span class="stat-label">⛽ Pressão</span><span class="stat-value">{val['pressao']:.2f} bar</span></div>
                            <div class="stat-row"><span class="stat-label">🌡️ Mancal</span><span class="stat-value">{val['mancal']:.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">🔥 Óleo</span><span class="stat-value">{val.get('oleo', 0):.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">📳 RMS</span><span class="stat-value">{val['rms']:.2f}</span></div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="pump-card" style="border-top-color:#d1d5db; opacity:0.6;"><h3>{id_b.upper()}</h3><p style="text-align:center; padding-top:20px;">DESCONECTADO</p></div>', unsafe_allow_html=True)

elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Análise de Tendências")
    ativos = [b for l in locais.values() for b in l]
    escolha = st.multiselect("Selecione os ativos:", ativos, default=[ativos[0]])
    
    if escolha:
        df_h = buscar_historico(escolha)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            
            tab1, tab2, tab3 = st.tabs(["💧 Hidráulica", "🔥 Térmica", "📳 Vibração"])
            
            with tab1:
                # Cor dinâmica por id_bomba
                fig1 = px.line(df_h, x="data_hora", y="pressao", color="id_bomba", title="Pressão (bar)", template="plotly_white")
                st.plotly_chart(fig1, use_container_width=True)
            
            with tab2:
                # Cada ativo terá sua cor, e linhas separadas para Mancal/Óleo
                fig2 = px.line(df_h, x="data_hora", y=["mancal", "oleo"], color="id_bomba", title="Temperaturas (°C)", template="plotly_white")
                st.plotly_chart(fig2, use_container_width=True)
                
            with tab3:
                eixo_sel = st.multiselect("Eixos:", ["rms", "vx", "vy", "vz"], default=["rms"])
                fig3 = px.line(df_h, x="data_hora", y=eixo_sel, color="id_bomba", title="Vibração", template="plotly_white")
                st.plotly_chart(fig3, use_container_width=True)

elif menu == "🚨 CENTRAL DE ALERTAS":
    st.title("🔔 Central de Alarmes")
    if not alertas_ativos:
        st.success("Tudo operando conforme os limites.")
    else:
        for a in alertas_ativos:
            rec_check = df_recon[(df_recon['bomba'] == a['bomba']) & (df_recon['sensor'] == a['sensor'])] if not df_recon.empty else pd.DataFrame()
            
            with st.container():
                c1, c2 = st.columns([4, 1])
                if rec_check.empty:
                    c1.error(f"🚨 **{a['bomba'].upper()}**: {a['sensor']} fora do limite (**{a['valor']}**)")
                    if c2.button("Reconhecer", key=f"rec_{a['bomba']}_{a['sensor']}"):
                        supabase.table("logs_alertas").insert({
                            "bomba": a['bomba'], "sensor": a['sensor'], "valor_detectado": str(a['valor']),
                            "limite_definido": str(a['limite']), "status": "Reconhecido", "operador": st.session_state.usuario['nome']
                        }).execute()
                        st.rerun()
                else:
                    op_nome = rec_check.iloc[-1]['operador']
                    c1.warning(f"⚠️ **{a['bomba'].upper()}**: {a['sensor']} (Reconhecido por {op_nome})")
                    c2.info("Ciente")

