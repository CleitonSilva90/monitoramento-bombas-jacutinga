import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

# --- 1. CONFIGURAÇÃO VISUAL MODERNA ---
st.set_page_config(page_title="Concórdia Saneamento GS Inima", layout="wide")

st.markdown("""
    <style>
    /* Estilos Gerais e Sidebar */
    [data-testid="stSidebar"] { background-color: #E0FFFF; }
    [data-testid="stSidebar"] * { color: #00BFFF !important; }
    [data-testid="stWidgetLabel"] p { color: #00BFFF !important; font-size: 1.2rem !important; font-weight: 800 !important; text-shadow: 0px 0px 5px rgba(0, 191, 255, 0.2); }
    hr { border-color: #00BFFF !important; }

    /* Login Box Inspirado na Imagem */
    .login-box {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 15px;
        border: 2px solid #00BFFF;
        box-shadow: 0px 10px 25px rgba(0,0,0,0.1);
        text-align: center;
        max-width: 400px;
        margin: auto;
    }

    /* Cards e Alertas */
    .alert-banner {
        background: linear-gradient(90deg, #ff4b4b 0%, #b91c1c 100%);
        color: white; padding: 15px; border-radius: 10px;
        text-align: center; font-weight: bold; font-size: 1.1rem;
        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
    }
    .pump-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border-top: 8px solid #10b981; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #f3f4f6; }
    .stat-label { color: #6b7280; font-weight: 500; }
    .stat-value { color: #111827; font-weight: 700; }
    .value-critical { color: #ff4b4b !important; font-weight: 800; }
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
        return res.data[0] if res.data else None
    except:
        return {"limite_pressao": 2.0, "limite_mancal": 75.0, "limite_oleo": 80.0, "limite_rms": 5.0, "senha_acesso": "1234"}

def buscar_todos_status():
    res = supabase.table("status_atual").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_historico(ids_selecionados):
    res = supabase.table("historico").select("*").in_("id_bomba", ids_selecionados).order("data_hora", desc=True).limit(500).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def buscar_reconhecidos():
    res = supabase.table("logs_alertas").select("*").eq("status", "Reconhecido").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def registrar_reconhecimento(bomba, sensor, valor, limite):
    dados = {
        "bomba": bomba, "sensor": sensor, "valor_detectado": str(valor),
        "limite_definido": str(limite), "status": "Reconhecido",
        "operador": st.session_state.usuario['nome']
    }
    supabase.table("logs_alertas").insert(dados).execute()

# --- 4. TELA DE LOGIN ---
if 'usuario' not in st.session_state:
    col1, col_login, col3 = st.columns([1, 1.2, 1])
    with col_login:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.title("👤 Acesso")
        u_in = st.text_input("Usuário")
        p_in = st.text_input("Senha", type="password")
        if st.button("LOGIN", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("usuario", u_in).eq("senha", p_in).execute()
            if res.data:
                st.session_state.usuario = res.data[0]
                st.rerun()
            else:
                st.error("Credenciais inválidas.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. PRÉ-PROCESSAMENTO DE ALERTAS ---
config = buscar_configuracoes()
df_status = buscar_todos_status()
df_recon = buscar_reconhecidos()

alertas_ativos = []   # Todos que estão fora do limite (Central)
alertas_criticos = [] # Apenas os NÃO reconhecidos (Banner e Dashboard)

if not df_status.empty:
    for _, row in df_status.iterrows():
        b_id = row['id_bomba'].upper()
        # Regras
        checks = [
            ("Pressão Saída", row['pressao'], config['limite_pressao'], "Mínima", row['pressao'] < config['limite_pressao']),
            ("Temp. Mancal", row['mancal'], config['limite_mancal'], "Máxima", row['mancal'] > config['limite_mancal']),
            ("Temp. Óleo", row.get('oleo', 0), config['limite_oleo'], "Máxima", row.get('oleo', 0) > config['limite_oleo']),
            ("Vibração RMS", row['rms'], config['limite_rms'], "Máxima", row['rms'] > config['limite_rms'])
        ]
        for s_nome, s_val, s_lim, s_tipo, em_erro in checks:
            if em_erro:
                alerta_data = {"bomba": b_id, "sensor": s_nome, "valor": f"{s_val:.2f}", "limite": s_lim, "tipo": s_tipo}
                alertas_ativos.append(alerta_data)
                
                ja_recon = False
                if not df_recon.empty:
                    ja_recon = not df_recon[(df_recon['bomba'] == b_id) & (df_recon['sensor'] == s_nome)].empty
                if not ja_recon:
                    alertas_criticos.append(alerta_data)

# Banner Superior
if alertas_criticos:
    st.markdown(f'<div class="alert-banner">🚨 SISTEMA EM ALERTA: {len(alertas_criticos)} EVENTO(S) PENDENTE(S)</div>', unsafe_allow_html=True)

# --- 6. SIDEBAR ---
try:
    st.sidebar.image("logo.png", use_container_width=True)
except:
    st.sidebar.subheader("GS INIMA")

st.sidebar.write(f"👤 {st.session_state.usuario['nome']} ({st.session_state.usuario['nivel_acesso']})")
if st.sidebar.button("🚪 LOGOFF"):
    del st.session_state.usuario
    st.rerun()

st.sidebar.markdown("---")
opcoes = ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA", "🚨 CENTRAL DE ALERTAS"]
if st.session_state.usuario['nivel_acesso'] == 'Admin':
    opcoes += ["⚙️ CONFIGURAÇÕES", "👥 USUÁRIOS"]

menu = st.sidebar.radio("NAVEGAÇÃO", opcoes)

locais = {
    "JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"],
    "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]
}

# --- 7. TELAS ---

if menu == "🌍 VISÃO GERAL":
    st.title("🏭 Monitoramento de Ativos")
    for local, lista in locais.items():
        st.subheader(f"📍 {local}")
        cols = st.columns(3)
        for i, id_b in enumerate(lista):
            with cols[i]:
                row = df_status[df_status['id_bomba'] == id_b]
                if not row.empty:
                    val = row.iloc[0]
                    tem_pendencia = any(a['bomba'] == id_b.upper() for a in alertas_criticos)
                    cor_borda = "#ef4444" if tem_pendencia else "#10b981"
                    
                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: {cor_borda}">
                            <h3 style="margin:0;">{id_b.upper()}</h3>
                            <div class="stat-row"><span class="stat-label">⛽ Pressão</span><span class="stat-value">{val['pressao']:.2f} bar</span></div>
                            <div class="stat-row"><span class="stat-label">🌡️ Mancal</span><span class="stat-value">{val['mancal']:.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">🔥 Óleo</span><span class="stat-value">{val.get('oleo', 0):.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">📳 RMS</span><span class="stat-value">{val['rms']:.2f}</span></div>
                        </div>
                    """, unsafe_allow_html=True)

elif menu == "🚨 CENTRAL DE ALERTAS":
    st.title("🔔 Central de Alarmes")
    if not alertas_ativos:
        st.success("✅ Nenhum alarme detectado no momento.")
    else:
        for a in alertas_ativos:
            rec_info = df_recon[(df_recon['bomba'] == a['bomba']) & (df_recon['sensor'] == a['sensor'])] if not df_recon.empty else pd.DataFrame()
            with st.container():
                c1, c2 = st.columns([4, 1])
                if rec_info.empty:
                    c1.error(f"**{a['bomba']}** | {a['sensor']} fora do limite: **{a['valor']}**")
                    if c2.button("Reconhecer", key=f"btn_{a['bomba']}_{a['sensor']}"):
                        registrar_reconhecimento(a['bomba'], a['sensor'], a['valor'], a['limite'])
                        st.rerun()
                else:
                    c1.warning(f"⚠️ **{a['bomba']}** | {a['sensor']} - Reconhecido por {rec_info.iloc[-1]['operador']}")
                    c2.info("Ciente")

elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Gráficos de Tendência")
    todos = [b for l in locais.values() for b in l]
    selecionados = st.multiselect("Analisar:", todos, default=[todos[0]])
    if selecionados:
        df_h = buscar_historico(selecionados)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            st.plotly_chart(px.line(df_h, x="data_hora", y=["pressao", "mancal", "oleo"], color="id_bomba"), use_container_width=True)

elif menu == "⚙️ CONFIGURAÇÕES":
    st.title("⚙️ Limites de Alarme")
    with st.form("set_alarms"):
        p_min = st.number_input("Pressão Mínima", value=float(config['limite_pressao']))
        m_max = st.number_input("Mancal Máxima", value=float(config['limite_mancal']))
        o_max = st.number_input("Óleo Máxima", value=float(config['limite_oleo']))
        r_max = st.number_input("Vibração Máxima", value=float(config['limite_rms']))
        if st.form_submit_button("SALVAR"):
            supabase.table("configuracoes").update({"limite_pressao": p_min, "limite_mancal": m_max, "limite_oleo": o_max, "limite_rms": r_max}).eq("id", 1).execute()
            st.success("Configurações atualizadas!")

elif menu == "👥 USUÁRIOS":
    st.title("👥 Gestão de Equipe")
    with st.expander("Cadastrar Novo Usuário"):
        with st.form("new_user"):
            n = st.text_input("Nome")
            u = st.text_input("Username")
            s = st.text_input("Senha", type="password")
            niv = st.selectbox("Nível", ["Leitura", "Operador", "Admin"])
            if st.form_submit_button("CADASTRAR"):
                supabase.table("usuarios").insert({"nome":n, "usuario":u, "senha":s, "nivel_acesso":niv}).execute()
                st.success("Usuário criado!")
                st.rerun()
