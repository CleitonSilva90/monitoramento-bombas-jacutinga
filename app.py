import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

# --- 1. CONFIGURAÇÃO VISUAL MODERNA ---
st.set_page_config(page_title="PRO-TELEMETRY | Indústria 4.0", layout="wide")

st.markdown("""
    <style>
    /* Fundo do menu lateral */
    [data-testid="stSidebar"] { 
        background-color: #111827; 
    }
    
    /* COR SOMENTE DAS LETRAS E ÍCONES NO MENU LATERAL */
    [data-testid="stSidebar"] * {
        color: #00BFFF !important; 
    }
    
    /* Estilização para as opções do Radio Button */
    [data-testid="stWidgetLabel"] p {
        color: #00BFFF !important;
        font-size: 1.2rem !important;
        font-weight: 800 !important;
        text-shadow: 0px 0px 5px rgba(0, 191, 255, 0.2);
    }
    
    /* Linha divisória em azul */
    hr {
        border-color: #00BFFF !important;
    }

    /* Estilo para o Banner de Alerta Superior (Inspirado Base44) */
    .alert-banner {
        background: linear-gradient(90deg, #ff4b4b 0%, #b91c1c 100%);
        color: white; padding: 15px; border-radius: 10px;
        text-align: center; font-weight: bold; font-size: 1.1rem;
        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
    }

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
    
    /* Classe para destacar valores em alerta nos cards */
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

config = buscar_configuracoes()

# --- 4. PRÉ-PROCESSAMENTO DE ALERTAS (BANNER E CENTRAL) ---
df_status = buscar_todos_status()
alertas_ativos = []

if not df_status.empty:
    for _, row in df_status.iterrows():
        b_id = row['id_bomba'].upper()
        # Regras de Alerta
        if row['pressao'] < config['limite_pressao']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Pressão Saída", "valor": f"{row['pressao']:.2f} bar", "limite": config['limite_pressao'], "tipo": "Mínima"})
        if row['mancal'] > config['limite_mancal']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Temp. Mancal", "valor": f"{row['mancal']:.1f} °C", "limite": config['limite_mancal'], "tipo": "Máxima"})
        if row.get('oleo', 0) > config['limite_oleo']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Temp. Óleo", "valor": f"{row['oleo']:.1f} °C", "limite": config['limite_oleo'], "tipo": "Máxima"})
        if row['rms'] > config['limite_rms']:
            alertas_ativos.append({"bomba": b_id, "sensor": "Vibração RMS", "valor": f"{row['rms']:.2f}", "limite": config['limite_rms'], "tipo": "Máxima"})

# Banner Superior
if alertas_ativos:
    st.markdown(f'<div class="alert-banner">🚨 SISTEMA EM ALERTA: {len(alertas_ativos)} EVENTO(S) CRÍTICO(S) DETECTADO(S)</div>', unsafe_allow_html=True)

# --- 5. SIDEBAR ---
st.sidebar.title("🎛️ CORE CONTROL")
st.sidebar.markdown("---")
menu = st.sidebar.radio("NAVEGAÇÃO", ["🌍 VISÃO GERAL", "📊 ANÁLISE TÉCNICA", "🚨 CENTRAL DE ALERTAS", "⚙️ CONFIGURAÇÕES"])

locais = {
    "JACUTINGA": ["jacutinga_b01", "jacutinga_b02", "jacutinga_b03"],
    "INTERMEDIÁRIA": ["intermediaria_b01", "intermediaria_b02", "intermediaria_b03"]
}

# --- 6. TELAS ---

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
                    # Verifica se esta bomba tem alerta ativo
                    b_tem_alerta = any(a['bomba'] == id_b.upper() for a in alertas_ativos)
                    cor_borda = "#ef4444" if b_tem_alerta else "#10b981"
                    
                    # Estilos críticos individuais
                    cp = "value-critical" if val['pressao'] < config['limite_pressao'] else ""
                    cm = "value-critical" if val['mancal'] > config['limite_mancal'] else ""
                    co = "value-critical" if val.get('oleo', 0) > config['limite_oleo'] else ""
                    cv = "value-critical" if val['rms'] > config['limite_rms'] else ""

                    try:
                        data_formatada = pd.to_datetime(val['ultima_batida']).strftime('%d/%m %H:%M:%S')
                    except:
                        data_formatada = val['ultima_batida']

                    st.markdown(f"""
                        <div class="pump-card" style="border-top-color: {cor_borda}">
                            <h3 style="margin:0;">{id_b.upper()}</h3>
                            <p style="font-size:12px; color:gray;">Sinal: {data_formatada}</p>
                            <div class="stat-row"><span class="stat-label">⛽ Pressão</span><span class="stat-value {cp}">{val['pressao']:.2f} bar</span></div>
                            <div class="stat-row"><span class="stat-label">🌡️ Mancal</span><span class="stat-value {cm}">{val['mancal']:.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">🔥 Óleo</span><span class="stat-value {co}">{val.get('oleo', 0):.1f} °C</span></div>
                            <div class="stat-row"><span class="stat-label">📳 Vibração (RMS)</span><span class="stat-value {cv}">{val['rms']:.2f}</span></div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="pump-card" style="border-top-color:#d1d5db;color:#9ca3af;"><h3>{id_b.upper()}</h3><p>OFF-LINE</p></div>', unsafe_allow_html=True)

elif menu == "🚨 CENTRAL DE ALERTAS":
    st.title("🔔 Central de Gerenciamento de Alarmes")
    
    # KPIs inspirados no design SCADA
    k1, k2, k3 = st.columns(3)
    k1.metric("Ativos Monitorados", "6")
    k2.metric("Alertas Ativos", len(alertas_ativos), delta=len(alertas_ativos), delta_color="inverse")
    k3.metric("Status do Sistema", "CRÍTICO" if alertas_ativos else "OPERALCIONAL")

    st.markdown("---")
    if not alertas_ativos:
        st.success("✅ Nenhum alarme detectado no momento.")
    else:
        for a in alertas_ativos:
            with st.container():
                c1, c2 = st.columns([4, 1])
                c1.error(f"**{a['bomba']}** | {a['sensor']} fora do limite: **{a['valor']}** (Limite {a['tipo']}: {a['limite']})")
                if c2.button("Reconhecer", key=f"btn_{a['bomba']}_{a['sensor']}"):
                    st.toast(f"Evento em {a['bomba']} reconhecido.")

elif menu == "📊 ANÁLISE TÉCNICA":
    st.title("📈 Gráficos de Tendência")
    todos_ativos = [b for l in locais.values() for b in l]
    selecionados = st.multiselect("Bombas para análise:", todos_ativos, default=[todos_ativos[0]])
    
    if selecionados:
        df_h = buscar_historico(selecionados)
        if not df_h.empty:
            df_h['data_hora'] = pd.to_datetime(df_h['data_hora'])
            t1, t2, t3 = st.tabs(["📉 Pressão", "🌡️ Temperaturas", "📳 Vibração (Eixos)"])
            
            with t1:
                fig1 = px.line(df_h, x="data_hora", y="pressao", color="id_bomba", template="plotly_white")
                fig1.update_xaxes(tickformat="%d/%m\n%H:%M", title_text="Hora Local")
                st.plotly_chart(fig1, width="stretch") 
            with t2:
                fig2 = px.line(df_h, x="data_hora", y=["mancal", "oleo"], 
                                   color_discrete_map={"mancal": "#FF4B4B", "oleo": "#00CCFF"},
                                   title="Comparativo: Mancal (Vermelho) vs Óleo (Azul)",
                                   template="plotly_white")
                fig2.update_xaxes(tickformat="%d/%m\n%H:%M", title_text="Hora Local")
                st.plotly_chart(fig2, width="stretch") 
            with t3:
                eixos = st.multiselect("Eixos:", ["rms", "vx", "vy", "vz"], default=["rms", "vx"])
                fig3 = px.line(df_h, x="data_hora", y=eixos, color="id_bomba", template="plotly_white")
                fig3.update_xaxes(tickformat="%d/%m\n%H:%M", title_text="Hora Local")
                st.plotly_chart(fig3, width="stretch") 

elif menu == "⚙️ CONFIGURAÇÕES":
    st.title("🔐 Configuração de Alarmes")
    senha_input = st.text_input("Senha de Acesso", type="password")
    
    if senha_input == config['senha_acesso']:
        st.success("Acesso Liberado")
        with st.form("set_alarms"):
            c1, c2 = st.columns(2)
            p_min = c1.number_input("Limite MÍNIMO Pressão (bar)", value=float(config['limite_pressao']))
            m_max = c1.number_input("Limite MÁXIMO Temp. Mancal (°C)", value=float(config['limite_mancal']))
            o_max = c2.number_input("Limite MÁXIMO Temp. Óleo (°C)", value=float(config['limite_oleo']))
            r_max = c2.number_input("Limite MÁXIMO Vibração RMS", value=float(config['limite_rms']))
            nova_senha = st.text_input("Alterar Senha", value=config['senha_acesso'])
            
            if st.form_submit_button("GRAVAR CONFIGURAÇÕES"):
                novos_dados = {"limite_pressao": p_min, "limite_mancal": m_max, "limite_oleo": o_max, "limite_rms": r_max, "senha_acesso": nova_senha}
                supabase.table("configuracoes").update(novos_dados).eq("id", 1).execute()
                st.success("Salvo com sucesso!")
                st.rerun()

