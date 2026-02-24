import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import time

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    st.error("⚠️ Biblioteca Supabase não instalada. Execute: pip install supabase")

# ============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ============================================================================

st.set_page_config(
    page_title="GS Inima | Monitoramento Avançado",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'About': "Sistema de Monitoramento Industrial - v3.0"
    }
)

# ============================================================================
# 2. CONEXÃO COM SUPABASE (com tratamento de erros)
# ============================================================================

SUPABASE_URL = "https://iemojjmgzyrxddochnlq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"

@st.cache_resource
def init_supabase():
    if not SUPABASE_AVAILABLE:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Erro ao conectar com Supabase: {e}")
        return None

supabase = init_supabase()

# ============================================================================
# 3. FUNÇÕES AUXILIARES
# ============================================================================

def bar_to_mca(bar_value):
    """Converte bar para MCA"""
    try:
        return float(bar_value) * 10.197
    except:
        return 0.0

def mca_to_bar(mca_value):
    """Converte MCA para bar"""
    try:
        return float(mca_value) / 10.197
    except:
        return 0.0

# ============================================================================
# 4. FUNÇÕES DE BANCO DE DADOS (com fallback)
# ============================================================================

@st.cache_data(ttl=10)
def get_current_data():
    """Busca dados do Supabase ou retorna mockup"""
    if not supabase:
        return get_mockup_data()
    
    try:
        response = supabase.table('status_atual').select('*').execute()
        
        if response.data and len(response.data) > 0:
            df = pd.DataFrame(response.data)
            
            # Mapear id_bomba
            df['local'] = df['id_bomba'].apply(lambda x: str(x).split('_')[0].upper() if '_' in str(x) else 'UNKNOWN')
            df['id'] = df['id_bomba'].apply(lambda x: str(x).split('_')[1].upper() if '_' in str(x) else 'B00')
            
            # Converter pressão
            df['pressao'] = df['pressao'].apply(lambda x: bar_to_mca(x) if x < 50 else x)
            
            # Renomear
            if 'rms' in df.columns:
                df = df.rename(columns={'rms': 'vibra'})
            
            # Status
            config = get_config()
            df['status'] = df.apply(lambda row: determine_status(row, config), axis=1)
            
            # Campos adicionais
            df['corrente'] = 45.0
            df['potencia'] = 22.0
            df['horas_operacao'] = 8234
            df['ultima_manutencao'] = "2024-11-15"
            
            cols = ['id', 'local', 'status', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente', 'potencia', 'horas_operacao', 'ultima_manutencao']
            return df[[c for c in cols if c in df.columns]]
        else:
            return get_mockup_data()
    except Exception as e:
        st.warning(f"Usando dados mockup: {str(e)[:100]}")
        return get_mockup_data()

def get_mockup_data():
    """Dados mockup para desenvolvimento"""
    return pd.DataFrame([
        {"id": "B01", "local": "JACUTINGA", "status": "Online", "pressao": 24.5, "mancal": 34.2, "oleo": 26.8, "vibra": 0.45, "corrente": 45.2, "potencia": 22.5, "horas_operacao": 8234, "ultima_manutencao": "2024-11-15"},
        {"id": "B02", "local": "JACUTINGA", "status": "Alarme", "pressao": 1.2, "mancal": 72.1, "oleo": 85.4, "vibra": 4.21, "corrente": 12.1, "potencia": 5.8, "horas_operacao": 12456, "ultima_manutencao": "2024-08-22"},
        {"id": "B03", "local": "JACUTINGA", "status": "Online", "pressao": 24.1, "mancal": 35.0, "oleo": 27.0, "vibra": 0.48, "corrente": 44.8, "potencia": 22.1, "horas_operacao": 6789, "ultima_manutencao": "2024-12-01"},
    ])

def determine_status(row, config):
    """Determina status da bomba"""
    try:
        # Verificar última batida
        if pd.notna(row.get('ultima_batida')):
            try:
                ultima_batida = pd.to_datetime(row['ultima_batida'])
                agora = pd.Timestamp.now(tz='UTC')
                diferenca = (agora - ultima_batida).total_seconds() / 60
                if diferenca > 5:
                    return 'Offline'
            except:
                pass
        
        # Verificar alarmes
        mancal = float(row.get('mancal', 0))
        oleo = float(row.get('oleo', 0))
        vibra = float(row.get('vibra', 0))
        pressao = float(row.get('pressao', 0))
        
        if (mancal > config['limite_mancal'] or 
            oleo > config['limite_oleo'] or
            vibra > config['limite_rms'] or
            pressao < config['limite_pressao_mca']):
            return 'Alarme'
        
        return 'Online'
    except:
        return 'Online'

@st.cache_data(ttl=60)
def get_config():
    """Busca configurações"""
    if not supabase:
        return get_default_config()
    
    try:
        response = supabase.table('configuracoes').select('*').eq('id', 1).execute()
        if response.data and len(response.data) > 0:
            config = response.data[0]
            config['limite_pressao_mca'] = bar_to_mca(config.get('limite_pressao', 2.0))
            return config
    except:
        pass
    
    return get_default_config()

def get_default_config():
    """Configurações padrão"""
    return {
        'limite_mancal': 75.0,
        'limite_oleo': 80.0,
        'limite_pressao': 2.0,
        'limite_pressao_mca': 20.4,
        'limite_rms': 5.0
    }

@st.cache_data(ttl=60)
def get_historical_data(pump_id, local, days=7):
    """Busca histórico"""
    if not supabase:
        return generate_mockup_historical(pump_id, local, days)
    
    try:
        id_bomba = f"{local.lower()}_{pump_id.lower()}"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        response = supabase.table('historico')\
            .select('*')\
            .eq('id_bomba', id_bomba)\
            .gte('data_hora', start_date.isoformat())\
            .lte('data_hora', end_date.isoformat())\
            .order('data_hora', desc=False)\
            .execute()
        
        if response.data and len(response.data) > 0:
            df = pd.DataFrame(response.data)
            df['timestamp'] = pd.to_datetime(df['data_hora'])
            if 'rms' in df.columns:
                df = df.rename(columns={'rms': 'vibra'})
            if 'corrente' not in df.columns:
                df['corrente'] = 45.0
            if 'potencia' not in df.columns:
                df['potencia'] = 22.0
            return df
    except:
        pass
    
    return generate_mockup_historical(pump_id, local, days)

def generate_mockup_historical(pump_id, local, days):
    """Gera histórico mockup"""
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    timestamps = pd.date_range(start=start_time, end=end_time, freq='5min')
    
    np.random.seed(hash(pump_id + local) % 10000)
    
    return pd.DataFrame({
        'timestamp': timestamps,
        'pressao': np.random.normal(24.0, 0.8, len(timestamps)),
        'mancal': np.random.normal(34.0, 2.5, len(timestamps)),
        'oleo': np.random.normal(26.5, 1.8, len(timestamps)),
        'vibra': np.abs(np.random.normal(0.45, 0.12, len(timestamps))),
        'corrente': np.random.normal(45.0, 2.1, len(timestamps)),
        'potencia': np.random.normal(22.0, 1.2, len(timestamps)),
    })

def save_config_to_db(limite_mancal=None, limite_oleo=None, limite_pressao=None, limite_rms=None):
    """Salva configurações no banco"""
    if not supabase:
        st.warning("Supabase não disponível - configurações não foram salvas")
        return False
    
    try:
        # Preparar dados para atualização
        update_data = {}
        if limite_mancal is not None:
            update_data['limite_mancal'] = float(limite_mancal)
        if limite_oleo is not None:
            update_data['limite_oleo'] = float(limite_oleo)
        if limite_pressao is not None:
            update_data['limite_pressao'] = float(limite_pressao)
        if limite_rms is not None:
            update_data['limite_rms'] = float(limite_rms)
        
        if not update_data:
            return False
        
        # Atualizar banco
        response = supabase.table('configuracoes')\
            .update(update_data)\
            .eq('id', 1)\
            .execute()
        
        # Limpar cache
        get_config.clear()
        get_current_data.clear()
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# ============================================================================
# 5. FUNÇÕES DE VISUALIZAÇÃO
# ============================================================================

def create_gauge_chart(value, max_value, title, color, warning_threshold=None, critical_threshold=None):
    """Gauge chart"""
    if critical_threshold and value >= critical_threshold:
        gauge_color = "#ef4444"
    elif warning_threshold and value >= warning_threshold:
        gauge_color = "#f59e0b"
    else:
        gauge_color = color
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 16, 'color': '#e2e8f0'}},
        number={'font': {'size': 32, 'color': gauge_color}},
        gauge={
            'axis': {'range': [None, max_value], 'tickwidth': 1, 'tickcolor': "#64748b"},
            'bar': {'color': gauge_color, 'thickness': 0.75},
            'bgcolor': "rgba(15, 23, 42, 0.5)",
            'borderwidth': 2,
            'bordercolor': "#1e293b",
            'steps': [
                {'range': [0, warning_threshold if warning_threshold else max_value*0.7], 'color': 'rgba(16, 185, 129, 0.1)'},
                {'range': [warning_threshold if warning_threshold else max_value*0.7, critical_threshold if critical_threshold else max_value*0.9], 'color': 'rgba(245, 158, 11, 0.1)'},
                {'range': [critical_threshold if critical_threshold else max_value*0.9, max_value], 'color': 'rgba(239, 68, 68, 0.1)'}
            ],
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#e2e8f0"},
        height=250,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig

def create_time_series_chart(df, column, title, color, y_label, show_threshold=None):
    """Time series chart"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df[column],
        mode='lines',
        name=title,
        line=dict(color=color, width=2.5),
        fill='tozeroy',
        fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)'
    ))
    
    if show_threshold:
        fig.add_hline(
            y=show_threshold,
            line_dash="dash",
            line_color="#ef4444",
            line_width=2,
            annotation_text=f"Limite: {show_threshold}",
            annotation_position="right"
        )
    
    fig.update_layout(
        title=None,
        xaxis_title=None,
        yaxis_title=y_label,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        font={'color': '#e2e8f0'},
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode='x unified',
        xaxis=dict(showgrid=True, gridcolor='rgba(100, 116, 139, 0.1)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(100, 116, 139, 0.1)')
    )
    
    return fig

def get_health_score(pump_data):
    """Calcula health score"""
    try:
        score = 100
        config = get_config()
        
        if pump_data['status'] == 'Offline':
            return 0
        elif pump_data['status'] == 'Alarme':
            score -= 40
        
        vibra = float(pump_data.get('vibra', 0))
        if vibra > config['limite_rms']:
            score -= 30
        elif vibra > config['limite_rms'] * 0.7:
            score -= 15
        
        mancal = float(pump_data.get('mancal', 0))
        if mancal > config['limite_mancal']:
            score -= 20
        elif mancal > config['limite_mancal'] * 0.9:
            score -= 10
        
        oleo = float(pump_data.get('oleo', 0))
        if oleo > config['limite_oleo']:
            score -= 20
        elif oleo > config['limite_oleo'] * 0.9:
            score -= 10
        
        pressao = float(pump_data.get('pressao', 0))
        if pressao < config['limite_pressao_mca']:
            score -= 25
        
        return max(0, score)
    except:
        return 50

def get_health_color(score):
    """Cor do health score"""
    if score >= 80:
        return "#10b981"
    elif score >= 60:
        return "#f59e0b"
    else:
        return "#ef4444"

# ============================================================================
# 6. CSS COMPACTO
# ============================================================================

st.markdown("""
<style>
    :root {
        --bg-card: #151e32;
        --border-color: #1e293b;
        --accent-blue: #38bdf8;
        --accent-green: #10b981;
        --accent-red: #ef4444;
    }
    .stApp { background: linear-gradient(135deg, #0a0e1a 0%, #050810 100%); color: #e2e8f0; }
    [data-testid="stHeader"] { display: none !important; }
    .kpi-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.25rem; text-align: center; }
    .kpi-value { font-size: 2rem; font-weight: 700; }
    .pump-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.5rem; }
    .status-Online { border-left: 4px solid var(--accent-green); }
    .status-Alarme { border-left: 4px solid var(--accent-red); }
    .status-Offline { border-left: 4px solid #64748b; }
    .txt-green { color: var(--accent-green) !important; }
    .txt-red { color: var(--accent-red) !important; }
    .txt-blue { color: var(--accent-blue) !important; }
    .txt-orange { color: #f59e0b !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 7. CONTROLE DE ESTADO
# ============================================================================

if 'view' not in st.session_state:
    st.session_state.view = 'dashboard'
if 'selected_pump_id' not in st.session_state:
    st.session_state.selected_pump_id = None
if 'selected_local' not in st.session_state:
    st.session_state.selected_local = None
if 'filter_local' not in st.session_state:
    st.session_state.filter_local = 'Todos'
if 'date_range' not in st.session_state:
    st.session_state.date_range = 7

# Auto-refresh (opcional - desabilitar se causar problemas no Render)
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

current_time = time.time()
time_since_refresh = int(current_time - st.session_state.last_refresh)
time_until_refresh = max(0, 30 - time_since_refresh)  # 30 segundos

# Refresh automático a cada 30 segundos (mais seguro para Render)
if time_since_refresh >= 30 and st.session_state.view == 'dashboard':
    st.session_state.last_refresh = current_time
    get_current_data.clear()
    st.rerun()

# ============================================================================
# 8. HEADER
# ============================================================================

df = get_current_data()

st.markdown(f"""
<div style='background: var(--bg-card); border: 1px solid var(--border-color); padding: 1rem; margin-bottom: 2rem; border-radius: 8px;'>
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <div>
            <h1 style='margin: 0; font-size: 1.8rem;'>GS INIMA | <span style='color: var(--accent-blue);'>SISTEMAS</span></h1>
        </div>
        <div style='display: flex; gap: 10px;'>
            <span style='background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: var(--accent-green); padding: 4px 12px; border-radius: 12px; font-size: 0.75rem;'>
                ● CONECTADO
            </span>
            <span style='background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); color: var(--accent-blue); padding: 4px 12px; border-radius: 12px; font-size: 0.75rem;'>
                🔄 Atualiza em {time_until_refresh}s
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# 9. NAVEGAÇÃO
# ============================================================================

col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])

with col_nav2:
    n1, n2, n3, n4 = st.columns(4)
    
    with n1:
        if st.button("📊 DASHBOARD", key="nav_dash", use_container_width=True):
            st.session_state.view = 'dashboard'
            st.session_state.selected_pump_id = None
            st.rerun()
    
    with n2:
        disabled = st.session_state.selected_pump_id is None
        if st.button("📈 DETALHES", key="nav_det", use_container_width=True, disabled=disabled):
            st.session_state.view = 'detalhes'
            st.rerun()
    
    with n3:
        if st.button("🚨 ALARMES", key="nav_alarm", use_container_width=True):
            st.session_state.view = 'alarmes'
            st.rerun()
    
    with n4:
        if st.button("⚙️ CONFIG", key="nav_config", use_container_width=True):
            st.session_state.view = 'config'
            st.rerun()

st.markdown("---")

# ============================================================================
# 10. VIEWS
# ============================================================================

# VIEW: DASHBOARD
if st.session_state.view == 'dashboard':
    
    # Filtros
    refresh_col, filter_col = st.columns([1, 9])
    
    with refresh_col:
        if st.button("🔄", key="manual_refresh", use_container_width=True):
            get_current_data.clear()
            st.session_state.last_refresh = time.time()
            st.rerun()
    
    with filter_col:
        locais_ordenados = ['Todos'] + sorted(df['local'].unique().tolist())
        sel_local = st.selectbox("📍 Localização", locais_ordenados, index=0 if st.session_state.filter_local == 'Todos' else locais_ordenados.index(st.session_state.filter_local) if st.session_state.filter_local in locais_ordenados else 0)
        if sel_local != st.session_state.filter_local:
            st.session_state.filter_local = sel_local
            st.rerun()
    
    # Filtragem
    if st.session_state.filter_local == 'Todos':
        df_show = df
        display_locais = sorted(df['local'].unique().tolist())
    else:
        df_show = df[df['local'] == st.session_state.filter_local]
        display_locais = [st.session_state.filter_local]
    
    # KPIs
    st.markdown("### 📊 Indicadores Gerais")
    df_online = df_show[df_show['status'] == 'Online']
    
    k1, k2, k3, k4, k5 = st.columns(5)
    
    with k1:
        total = len(df_show)
        online = len(df_online)
        pct = (online/total*100) if total > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-green">{online}<small>/{total}</small></div><div>Bombas Ativas</div></div>', unsafe_allow_html=True)
    
    with k2:
        avg_p = df_online['pressao'].mean() if len(df_online) > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-blue">{avg_p:.1f}<small> MCA</small></div><div>Pressão Média</div></div>', unsafe_allow_html=True)
    
    with k3:
        avg_m = df_online['mancal'].mean() if len(df_online) > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value">{avg_m:.1f}<small> °C</small></div><div>Temp. Mancal</div></div>', unsafe_allow_html=True)
    
    with k4:
        avg_o = df_online['oleo'].mean() if len(df_online) > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value">{avg_o:.1f}<small> °C</small></div><div>Temp. Óleo</div></div>', unsafe_allow_html=True)
    
    with k5:
        alarmes = len(df_show[df_show['status'] == 'Alarme'])
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-red">{alarmes}</div><div>Alarmes Ativos</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Cards das bombas
    for loc in display_locais:
        st.markdown(f'### {loc}')
        subset = df_show[df_show['local'] == loc]
        
        if len(subset) == 0:
            st.info(f"Nenhuma bomba em {loc}")
            continue
        
        cols = st.columns(min(4, len(subset)))
        
        for i, row in enumerate(subset.to_dict('records')):
            with cols[i % len(cols)]:
                health = get_health_score(row)
                health_color = get_health_color(health)
                
                config = get_config()
                icon_v = "⚠️" if row['vibra'] > config['limite_rms']*0.7 else "✅"
                icon_m = "🔥" if row['mancal'] > config['limite_mancal']*0.9 else "🌡️"
                icon_o = "🔥" if row['oleo'] > config['limite_oleo']*0.9 else "💧"
                
                st.markdown(f"""
                <div class="pump-card status-{row['status']}">
                    <div style='font-size: 0.8rem; color: #94a3b8; margin-bottom: 8px;'>{row['local']}</div>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;'>
                        <span style='font-size: 1.5rem; font-weight: 700;'>BOMBA {row['id']}</span>
                        <span style='font-size: 0.75rem; padding: 4px 12px; border-radius: 8px; background: rgba(56, 189, 248, 0.15);'>{row['status']}</span>
                    </div>
                    <div style='text-align: center; margin: 10px 0;'>
                        <div style='font-size: 0.7rem; color: #94a3b8;'>SAÚDE</div>
                        <div style='font-size: 2rem; font-weight: 700; color: {health_color};'>{health}<small>/100</small></div>
                    </div>
                    <div style='display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 1rem;'>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px;'>
                            <div style='font-size: 0.75rem; color: #cbd5e1;'>⚙️ Pressão</div>
                            <div style='font-size: 1.3rem; font-weight: 600;'>{row['pressao']:.1f}<small> MCA</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px;'>
                            <div style='font-size: 0.75rem; color: #cbd5e1;'>{icon_m} Mancal</div>
                            <div style='font-size: 1.3rem; font-weight: 600;'>{row['mancal']:.1f}<small> °C</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px;'>
                            <div style='font-size: 0.75rem; color: #cbd5e1;'>{icon_o} Óleo</div>
                            <div style='font-size: 1.3rem; font-weight: 600;'>{row['oleo']:.1f}<small> °C</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px;'>
                            <div style='font-size: 0.75rem; color: #cbd5e1;'>{icon_v} Vibração</div>
                            <div style='font-size: 1.3rem; font-weight: 600;'>{row['vibra']:.2f}<small> mm/s</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px;'>
                            <div style='font-size: 0.75rem; color: #cbd5e1;'>⚡ Corrente</div>
                            <div style='font-size: 1.3rem; font-weight: 600;'>{row['corrente']:.1f}<small> A</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px;'>
                            <div style='font-size: 0.75rem; color: #cbd5e1;'>🔌 Potência</div>
                            <div style='font-size: 1.3rem; font-weight: 600;'>{row['potencia']:.1f}<small> kW</small></div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                
                if st.button(f"📊 Ver Detalhes", key=f"btn_{row['local']}_{row['id']}", use_container_width=True):
                    st.session_state.selected_pump_id = row['id']
                    st.session_state.selected_local = row['local']
                    st.session_state.view = 'detalhes'
                    st.rerun()

# VIEW: DETALHES
elif st.session_state.view == 'detalhes':
    
    # Verificar se há bomba selecionada
    if not st.session_state.selected_pump_id or not st.session_state.selected_local:
        st.warning("Selecione uma bomba no Dashboard primeiro")
        if st.button("← Voltar ao Dashboard"):
            st.session_state.view = 'dashboard'
            st.rerun()
    else:
        # Seletores
        nav_col1, nav_col2, nav_col3 = st.columns([2, 2, 6])
        
        with nav_col1:
            locais = sorted(df['local'].unique().tolist())
            current_local = st.session_state.selected_local if st.session_state.selected_local in locais else locais[0] if locais else 'JACUTINGA'
            new_local = st.selectbox("📍 Local", locais, index=locais.index(current_local) if current_local in locais else 0)
        
        with nav_col2:
            bombas = sorted(df[df['local'] == new_local]['id'].unique().tolist())
            current_pump = st.session_state.selected_pump_id if st.session_state.selected_pump_id in bombas else bombas[0] if bombas else 'B01'
            new_pump = st.selectbox("🔧 Bomba", bombas, index=bombas.index(current_pump) if current_pump in bombas else 0)
        
        with nav_col3:
            date_ranges = {
                "Últimas 6 horas": 0.25,
                "Último dia": 1,
                "Últimos 3 dias": 3,
                "Última semana": 7,
            }
            selected_range = st.selectbox("📅 Período", list(date_ranges.keys()), index=2)
            st.session_state.date_range = date_ranges[selected_range]
        
        # Atualizar estado
        if new_local != st.session_state.selected_local or new_pump != st.session_state.selected_pump_id:
            st.session_state.selected_local = new_local
            st.session_state.selected_pump_id = new_pump
            st.rerun()
        
        # Dados
        pump_data = df[(df['local'] == st.session_state.selected_local) & (df['id'] == st.session_state.selected_pump_id)]
        
        if len(pump_data) == 0:
            st.error("Bomba não encontrada")
        else:
            pump_data = pump_data.iloc[0]
            historical_df = get_historical_data(st.session_state.selected_pump_id, st.session_state.selected_local, days=st.session_state.date_range)
            
            st.markdown("---")
            
            # Header
            health = get_health_score(pump_data)
            health_color = get_health_color(health)
            
            st.markdown(f"## {pump_data['local']} | BOMBA {pump_data['id']}")
            st.markdown(f"**Status:** {pump_data['status']} | **Saúde:** {health}/100")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gauges
            st.markdown("### 🎯 Indicadores em Tempo Real")
            g1, g2, g3, g4 = st.columns(4)
            
            config = get_config()
            
            with g1:
                st.plotly_chart(create_gauge_chart(pump_data['vibra'], 5.0, "Vibração (mm/s)", "#10b981", warning_threshold=config['limite_rms']*0.7, critical_threshold=config['limite_rms']), use_container_width=True)
            
            with g2:
                st.plotly_chart(create_gauge_chart(pump_data['pressao'], 50, "Pressão (MCA)", "#38bdf8", warning_threshold=config['limite_pressao_mca']*1.2, critical_threshold=config['limite_pressao_mca']), use_container_width=True)
            
            with g3:
                st.plotly_chart(create_gauge_chart(pump_data['mancal'], 100, "Temp. Mancal (°C)", "#f59e0b", warning_threshold=config['limite_mancal']*0.9, critical_threshold=config['limite_mancal']), use_container_width=True)
            
            with g4:
                st.plotly_chart(create_gauge_chart(pump_data['oleo'], 100, "Temp. Óleo (°C)", "#ef4444", warning_threshold=config['limite_oleo']*0.9, critical_threshold=config['limite_oleo']), use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gráficos
            st.markdown("### 📈 Tendências Históricas")
            
            tab1, tab2, tab3 = st.tabs(["🌊 Vibração", "⚙️ Pressão", "🌡️ Temperaturas"])
            
            with tab1:
                st.plotly_chart(create_time_series_chart(historical_df, 'vibra', 'Vibração', '#10b981', 'Vibração (mm/s)', show_threshold=config['limite_rms']), use_container_width=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Atual", f"{pump_data['vibra']:.2f} mm/s")
                c2.metric("Média", f"{historical_df['vibra'].mean():.2f} mm/s")
                c3.metric("Máximo", f"{historical_df['vibra'].max():.2f} mm/s")
                c4.metric("Mínimo", f"{historical_df['vibra'].min():.2f} mm/s")
            
            with tab2:
                st.plotly_chart(create_time_series_chart(historical_df, 'pressao', 'Pressão', '#38bdf8', 'Pressão (MCA)', show_threshold=config['limite_pressao_mca']), use_container_width=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Atual", f"{pump_data['pressao']:.1f} MCA")
                c2.metric("Média", f"{historical_df['pressao'].mean():.1f} MCA")
                c3.metric("Máximo", f"{historical_df['pressao'].max():.1f} MCA")
                c4.metric("Mínimo", f"{historical_df['pressao'].min():.1f} MCA")
            
            with tab3:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=historical_df['timestamp'], y=historical_df['mancal'], mode='lines', name='Mancal', line=dict(color='#f59e0b', width=2.5)))
                fig.add_trace(go.Scatter(x=historical_df['timestamp'], y=historical_df['oleo'], mode='lines', name='Óleo', line=dict(color='#ef4444', width=2.5)))
                fig.add_hline(y=config['limite_mancal'], line_dash="dash", line_color="#ef4444", annotation_text="Limite")
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(15, 23, 42, 0.5)', font={'color': '#e2e8f0'}, height=300, margin=dict(l=10, r=10, t=10, b=10), hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Mancal Atual", f"{pump_data['mancal']:.1f} °C")
                c2.metric("Óleo Atual", f"{pump_data['oleo']:.1f} °C")
                c3.metric("Mancal Médio", f"{historical_df['mancal'].mean():.1f} °C")
                c4.metric("Óleo Médio", f"{historical_df['oleo'].mean():.1f} °C")

# VIEW: ALARMES
elif st.session_state.view == 'alarmes':
    st.markdown("### 🚨 Central de Alarmes")
    st.info("📊 Módulo de alarmes em desenvolvimento. Os alarmes serão exibidos em tempo real baseados nas configurações.")

# VIEW: CONFIG
elif st.session_state.view == 'config':
    st.markdown("### ⚙️ Configurações do Sistema")
    st.info("💡 Configure os limites de alarmes. As alterações serão salvas no banco de dados.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["⚙️ Pressão", "〰️ Vibração", "🌡️ Mancal", "💧 Óleo"])
    
    config = get_config()
    
    with tab1:
        st.markdown("#### Configurações de Pressão")
        
        limite_pressao = st.number_input(
            "Limite Mínimo de Pressão (bar)",
            min_value=0.1,
            max_value=40.0,
            value=float(config.get('limite_pressao', 2.0)),
            step=0.1,
            help="Pressão abaixo deste valor gera alarme",
            key="config_pressao"
        )
        
        st.info(f"💡 Equivalente a {bar_to_mca(limite_pressao):.1f} MCA")
        
        if st.button("💾 Salvar Pressão", type="primary", use_container_width=True):
            if save_config_to_db(limite_pressao=limite_pressao):
                st.success("✅ Limite de pressão salvo no banco!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar")
    
    with tab2:
        st.markdown("#### Configurações de Vibração")
        
        limite_rms = st.number_input(
            "Limite RMS (mm/s)",
            min_value=0.1,
            max_value=10.0,
            value=float(config.get('limite_rms', 5.0)),
            step=0.1,
            key="config_rms"
        )
        
        if st.button("💾 Salvar Vibração", type="primary", use_container_width=True):
            if save_config_to_db(limite_rms=limite_rms):
                st.success("✅ Limite de vibração salvo no banco!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar")
    
    with tab3:
        st.markdown("#### Configurações de Temperatura do Mancal")
        
        limite_mancal = st.number_input(
            "Limite Máximo (°C)",
            min_value=20,
            max_value=150,
            value=int(config.get('limite_mancal', 75)),
            step=5,
            key="config_mancal"
        )
        
        if st.button("💾 Salvar Mancal", type="primary", use_container_width=True):
            if save_config_to_db(limite_mancal=limite_mancal):
                st.success("✅ Limite de mancal salvo no banco!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar")
    
    with tab4:
        st.markdown("#### Configurações de Temperatura do Óleo")
        
        limite_oleo = st.number_input(
            "Limite Máximo (°C)",
            min_value=20,
            max_value=150,
            value=int(config.get('limite_oleo', 80)),
            step=5,
            key="config_oleo"
        )
        
        if st.button("💾 Salvar Óleo", type="primary", use_container_width=True):
            if save_config_to_db(limite_oleo=limite_oleo):
                st.success("✅ Limite de óleo salvo no banco!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar")

# ============================================================================
# 11. RODAPÉ
# ============================================================================

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(f"""
<div style='text-align: center; color: #64748b; font-size: 0.8rem; padding: 20px; border-top: 1px solid #1e293b;'>
    GS Inima Sistemas © 2025 | v3.0 | {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
</div>
""", unsafe_allow_html=True)
