import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta
import time
from supabase import create_client, Client
import os

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
# 2. CONEXÃO COM SUPABASE
# ============================================================================

# Credenciais do Supabase
SUPABASE_URL = "https://iemojjmgzyrxddochnlq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"

# Inicializar cliente Supabase
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# ============================================================================
# 3. FUNÇÕES DE ACESSO AO BANCO DE DADOS
# ============================================================================

@st.cache_data(ttl=10)  # Cache de 10 segundos para dados em tempo real
def get_current_data():
    """Busca dados atuais do banco de dados"""
    try:
        response = supabase.table('status_atual').select('*').execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            
            # Mapear id_bomba para formato esperado
            # Exemplo: "jacutinga_b01" -> local="JACUTINGA", id="B01"
            df['local'] = df['id_bomba'].apply(lambda x: x.split('_')[0].upper())
            df['id'] = df['id_bomba'].apply(lambda x: x.split('_')[1].upper())
            
            # Determinar status baseado nos limites e última batida
            df['status'] = df.apply(determine_status, axis=1)
            
            # Converter pressão de bar para MCA
            df['pressao_mca'] = df['pressao'] * 10.197
            
            # Renomear colunas para compatibilidade
            df = df.rename(columns={
                'rms': 'vibra',
                'pressao_mca': 'pressao'
            })
            
            # Adicionar campos mockup temporários (até serem implementados no ESP32)
            df['corrente'] = 45.0  # Placeholder
            df['potencia'] = 22.0  # Placeholder
            df['horas_operacao'] = 8234  # Placeholder
            df['ultima_manutencao'] = "2024-11-15"  # Placeholder
            
            return df
        else:
            # Retornar DataFrame vazio com estrutura esperada
            return pd.DataFrame(columns=['id', 'local', 'status', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente', 'potencia'])
            
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return pd.DataFrame(columns=['id', 'local', 'status', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente', 'potencia'])

def determine_status(row):
    """Determina o status da bomba baseado nos sensores e última batida"""
    try:
        # Verificar se a bomba está respondendo (última batida)
        if pd.notna(row.get('ultima_batida')):
            ultima_batida = pd.to_datetime(row['ultima_batida'])
            agora = pd.Timestamp.now(tz='America/Sao_Paulo')
            diferenca = (agora - ultima_batida).total_seconds() / 60  # em minutos
            
            if diferenca > 5:  # Sem resposta há mais de 5 minutos
                return 'Offline'
        
        # Buscar configurações
        config = get_config()
        
        # Verificar se há alarmes
        if (row.get('mancal', 0) > config['limite_mancal'] or 
            row.get('oleo', 0) > config['limite_oleo'] or
            row.get('rms', 0) > config['limite_rms'] or
            row.get('pressao', 0) < config['limite_pressao'] / 10.197):  # Converter de MCA para bar
            return 'Alarme'
        
        return 'Online'
        
    except Exception as e:
        return 'Online'  # Default

@st.cache_data(ttl=60)
def get_config():
    """Busca configurações do banco"""
    try:
        response = supabase.table('configuracoes').select('*').eq('id', 1).execute()
        if response.data:
            config = response.data[0]
            # Converter limite de pressão de bar para MCA
            config['limite_pressao_mca'] = config['limite_pressao'] * 10.197
            return config
        else:
            # Configurações padrão
            return {
                'limite_mancal': 75.0,
                'limite_oleo': 80.0,
                'limite_pressao': 2.0,
                'limite_pressao_mca': 20.4,
                'limite_rms': 5.0
            }
    except Exception as e:
        st.error(f"Erro ao buscar configurações: {e}")
        return {
            'limite_mancal': 75.0,
            'limite_oleo': 80.0,
            'limite_pressao': 2.0,
            'limite_pressao_mca': 20.4,
            'limite_rms': 5.0
        }

@st.cache_data(ttl=60)
def get_historical_data(pump_id, local, days=7):
    """Busca dados históricos do banco"""
    try:
        # Converter para formato do banco (ex: "B01" + "JACUTINGA" -> "jacutinga_b01")
        id_bomba = f"{local.lower()}_{pump_id.lower()}"
        
        # Calcular data inicial
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Buscar dados
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
            
            # Renomear colunas
            df = df.rename(columns={'rms': 'vibra'})
            
            # Adicionar campos mockup temporários
            df['corrente'] = 45.0
            df['potencia'] = 22.0
            
            return df
        else:
            # Se não houver dados, gerar mockup
            return generate_mockup_historical(pump_id, local, days)
            
    except Exception as e:
        st.error(f"Erro ao buscar histórico: {e}")
        return generate_mockup_historical(pump_id, local, days)

def generate_mockup_historical(pump_id, local, days):
    """Gera dados históricos mockup quando não há dados reais"""
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    timestamps = pd.date_range(start=start_time, end=end_time, freq='5min')
    
    np.random.seed(hash(pump_id + local) % 10000)
    
    data = {
        'timestamp': timestamps,
        'pressao': np.random.normal(2.4, 0.08, len(timestamps)),
        'mancal': np.random.normal(34.0, 2.5, len(timestamps)),
        'oleo': np.random.normal(26.5, 1.8, len(timestamps)),
        'vibra': np.abs(np.random.normal(0.45, 0.12, len(timestamps))),
        'corrente': np.random.normal(45.0, 2.1, len(timestamps)),
        'potencia': np.random.normal(22.0, 1.2, len(timestamps)),
    }
    
    return pd.DataFrame(data)

def get_alarmes():
    """Busca logs de alarmes do banco"""
    try:
        response = supabase.table('logs_alertas')\
            .select('*')\
            .order('data_hora', desc=True)\
            .limit(50)\
            .execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            
            # Renomear e formatar colunas
            df = df.rename(columns={
                'data_hora': 'timestamp',
                'bomba': 'bomba',
                'sensor': 'tipo',
                'valor_detectado': 'mensagem'
            })
            
            # Adicionar coluna ack baseada no status
            df['ack'] = df['status'].apply(lambda x: x != 'Ativo')
            
            return df
        else:
            return pd.DataFrame(columns=['timestamp', 'bomba', 'tipo', 'mensagem', 'ack'])
            
    except Exception as e:
        st.error(f"Erro ao buscar alarmes: {e}")
        return pd.DataFrame(columns=['timestamp', 'bomba', 'tipo', 'mensagem', 'ack'])

def save_config_to_db(config):
    """Salva configurações no banco"""
    try:
        # Converter limite de pressão de MCA para bar antes de salvar
        config_to_save = config.copy()
        if 'limite_pressao_mca' in config_to_save:
            config_to_save['limite_pressao'] = config_to_save['limite_pressao_mca'] / 10.197
            del config_to_save['limite_pressao_mca']
        
        response = supabase.table('configuracoes')\
            .update(config_to_save)\
            .eq('id', 1)\
            .execute()
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configurações: {e}")
        return False

def create_alerta_log(bomba, sensor, valor, limite):
    """Cria log de alerta no banco"""
    try:
        data = {
            'bomba': bomba,
            'sensor': sensor,
            'valor_detectado': str(valor),
            'limite_definido': str(limite),
            'status': 'Ativo',
            'operador': 'Sistema'
        }
        
        response = supabase.table('logs_alertas').insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao criar log de alerta: {e}")
        return False

# ============================================================================
# 4. FUNÇÕES AUXILIARES (Mantidas do código original)
# ============================================================================

def bar_to_mca(bar_value):
    """Converte pressão de bar para MCA"""
    return bar_value * 10.197

def mca_to_bar(mca_value):
    """Converte pressão de MCA para bar"""
    return mca_value / 10.197

def create_gauge_chart(value, max_value, title, color, warning_threshold=None, critical_threshold=None):
    """Cria um gráfico gauge profissional"""
    
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
        title={'text': title, 'font': {'size': 16, 'color': '#e2e8f0', 'family': 'Rajdhani'}},
        number={'font': {'size': 32, 'color': gauge_color, 'family': 'JetBrains Mono'}},
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
            'threshold': {
                'line': {'color': "#ef4444", 'width': 3},
                'thickness': 0.75,
                'value': critical_threshold if critical_threshold else max_value
            }
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
    """Cria gráfico de série temporal profissional"""
    
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
    
    if len(df) > 20:
        df['ma'] = df[column].rolling(window=20).mean()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['ma'],
            mode='lines',
            name='Média Móvel',
            line=dict(color='rgba(255,255,255,0.3)', width=1, dash='dot')
        ))
    
    fig.update_layout(
        title=None,
        xaxis_title=None,
        yaxis_title=y_label,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        font={'color': '#e2e8f0', 'family': 'Inter'},
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor='rgba(100, 116, 139, 0.1)', zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(100, 116, 139, 0.1)', zeroline=False)
    )
    
    return fig

def get_health_score(pump_data, config):
    """Calcula score de saúde da bomba baseado nas configurações"""
    score = 100
    
    if pump_data['status'] == 'Offline':
        return 0
    elif pump_data['status'] == 'Alarme':
        score -= 40
    
    # Vibração
    if pump_data['vibra'] > config['limite_rms']:
        score -= 30
    elif pump_data['vibra'] > config['limite_rms'] * 0.7:
        score -= 15
    elif pump_data['vibra'] > config['limite_rms'] * 0.5:
        score -= 5
    
    # Temperatura Mancal
    if pump_data['mancal'] > config['limite_mancal']:
        score -= 20
    elif pump_data['mancal'] > config['limite_mancal'] * 0.9:
        score -= 10
    
    # Temperatura Óleo
    if pump_data['oleo'] > config['limite_oleo']:
        score -= 20
    elif pump_data['oleo'] > config['limite_oleo'] * 0.9:
        score -= 10
    
    # Pressão (em bar)
    pressao_bar = pump_data['pressao'] / 10.197
    if pressao_bar < config['limite_pressao']:
        score -= 25
    elif pressao_bar < config['limite_pressao'] * 1.2:
        score -= 10
    
    return max(0, score)

def get_health_color(score):
    """Retorna cor baseada no score de saúde"""
    if score >= 80:
        return "#10b981"
    elif score >= 60:
        return "#f59e0b"
    else:
        return "#ef4444"

# ============================================================================
# 5. CSS (Importado do código original)
# ============================================================================

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #0f1729;
            --bg-card: #151e32;
            --bg-card-hover: #1a2540;
            --border-color: #1e293b;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-blue: #38bdf8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-orange: #f59e0b;
            --accent-purple: #8b5cf6;
        }

        .stApp {
            background: linear-gradient(135deg, var(--bg-primary) 0%, #050810 100%);
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
        }

        [data-testid="stHeader"] { display: none !important; }
        .main .block-container { padding-top: 1.5rem !important; max-width: 100% !important; }
        
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-secondary); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        
        .main-header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 1.5rem;
            margin-bottom: 2rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        .logo-text {
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            font-size: 1.8rem;
            color: var(--text-primary);
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        
        .logo-accent { color: var(--accent-blue); font-weight: 700; }
        
        .status-badge {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--accent-green);
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }

        .nav-container {
            display: flex;
            gap: 8px;
            background: var(--bg-card);
            padding: 6px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }
        
        .nav-btn button {
            background: transparent !important;
            border: none !important;
            color: var(--text-secondary) !important;
            font-family: 'Rajdhani', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            text-transform: uppercase;
            padding: 8px 20px !important;
            border-radius: 6px !important;
            transition: all 0.3s ease !important;
        }
        
        .nav-btn button:hover {
            background: rgba(56, 189, 248, 0.1) !important;
            color: var(--accent-blue) !important;
        }
        
        .nav-active button {
            background: rgba(56, 189, 248, 0.15) !important;
            color: var(--accent-blue) !important;
            border: 1px solid rgba(56, 189, 248, 0.3) !important;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.2) !important;
        }

        .kpi-card {
            background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-secondary) 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .kpi-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple));
        }
        
        .kpi-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(56, 189, 248, 0.15);
            border-color: var(--accent-blue);
        }
        
        .kpi-label {
            font-size: 0.85rem;
            color: var(--text-primary);
            text-transform: uppercase;
            letter-spacing: 1.2px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .kpi-value {
            font-family: 'Rajdhani', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1;
        }
        
        .kpi-trend {
            font-size: 0.85rem;
            margin-top: 6px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .pump-card {
            background: linear-gradient(145deg, var(--bg-card), var(--bg-secondary));
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        
        .pump-card:hover {
            border-color: var(--accent-blue);
            box-shadow: 0 12px 30px rgba(56, 189, 248, 0.2);
            transform: translateY(-6px);
        }

        .status-Online { border-left: 4px solid var(--accent-green); }
        .status-Alarme { border-left: 4px solid var(--accent-red); animation: alertPulse 2s infinite; }
        .status-Offline { border-left: 4px solid var(--text-muted); }
        
        @keyframes alertPulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
        }

        .card-header {
            font-family: 'Rajdhani', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card-sub {
            font-size: 0.8rem;
            color: #94a3b8;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .metric-item {
            background: rgba(15, 23, 42, 0.5);
            padding: 10px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .m-label {
            font-size: 0.75rem;
            color: #cbd5e1;
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 4px;
            text-transform: uppercase;
            font-weight: 500;
        }
        
        .m-val {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .txt-green { color: var(--accent-green) !important; }
        .txt-red { color: var(--accent-red) !important; }
        .txt-blue { color: var(--accent-blue) !important; }
        .txt-orange { color: var(--accent-orange) !important; }
        
        .stButton > button {
            background: linear-gradient(135deg, var(--bg-card), var(--bg-secondary)) !important;
            color: var(--accent-blue) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
            font-family: 'Rajdhani', sans-serif !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
        }
        
        .stButton > button:hover {
            border-color: var(--accent-blue) !important;
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2) !important;
            transform: translateY(-2px) !important;
        }
        
        .stSelectbox label, .stMultiSelect label, .stNumberInput label {
            color: var(--text-primary) !important;
            font-family: 'Rajdhani', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.1rem !important;
            text-transform: uppercase !important;
        }
        
        .section-header {
            font-family: 'Rajdhani', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            border-left: 4px solid var(--accent-blue);
            padding-left: 12px;
            margin: 1.5rem 0 1rem 0;
            text-transform: uppercase;
        }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# 6. CONTROLE DE ESTADO
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

# Carregar configurações do banco
config = get_config()

# ============================================================================
# 7. HEADER
# ============================================================================

df = get_current_data()

st.markdown("""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 15px;">
                <div class="logo-text">
                    GS INIMA | <span class="logo-accent">SISTEMAS</span>
                </div>
                <div class="status-badge">● DADOS EM TEMPO REAL</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ============================================================================
# 8. NAVEGAÇÃO
# ============================================================================

col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])

with col_nav2:
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    n1, n2, n3, n4 = st.columns(4)
    
    def nav_class(page):
        return "nav-active" if st.session_state.view == page else "nav-btn"
    
    with n1:
        st.markdown(f'<div class="{nav_class("dashboard")}">', unsafe_allow_html=True)
        if st.button("📊 DASHBOARD", key="nav_dash", use_container_width=True):
            st.session_state.view = 'dashboard'
            st.session_state.selected_pump_id = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with n2:
        st.markdown(f'<div class="{nav_class("detalhes")}">', unsafe_allow_html=True)
        if st.button("📈 DETALHES", key="nav_det", use_container_width=True, disabled=st.session_state.selected_pump_id is None):
            st.session_state.view = 'detalhes'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with n3:
        st.markdown(f'<div class="{nav_class("alarmes")}">', unsafe_allow_html=True)
        if st.button("🚨 ALARMES", key="nav_alarm", use_container_width=True):
            st.session_state.view = 'alarmes'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with n4:
        st.markdown(f'<div class="{nav_class("config")}">', unsafe_allow_html=True)
        if st.button("⚙️ CONFIG", key="nav_config", use_container_width=True):
            st.session_state.view = 'config'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# ============================================================================
# 9. VIEWS (continuação no próximo arquivo devido ao limite de tamanho)
# ============================================================================

# VIEW: DASHBOARD
if st.session_state.view == 'dashboard':
    
    # Botão de atualização
    col_refresh, col_filter = st.columns([1, 9])
    with col_refresh:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    with col_filter:
        locais_ordenados = ['Todos', 'JACUTINGA', 'INTERMEDIÁRIA']
        sel_local = st.selectbox("📍 Localização", locais_ordenados, index=locais_ordenados.index(st.session_state.filter_local))
        if sel_local != st.session_state.filter_local:
            st.session_state.filter_local = sel_local
            st.rerun()
    
    if st.session_state.filter_local == 'Todos':
        df_show = df
        display_locais = ['JACUTINGA', 'INTERMEDIÁRIA']
    else:
        df_show = df[df['local'] == st.session_state.filter_local]
        display_locais = [st.session_state.filter_local]
    
    # KPIs
    st.markdown("### 📊 Indicadores Gerais")
    df_online = df_show[df_show['status'] == 'Online']
    
    k1, k2, k3, k4, k5 = st.columns(5)
    
    with k1:
        total_bombas = len(df_show)
        online_bombas = len(df_online)
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Bombas Ativas</div>
                <div class="kpi-value txt-green">{online_bombas}<small>/{total_bombas}</small></div>
                <div class="kpi-trend txt-green">↗ {(online_bombas/total_bombas*100) if total_bombas > 0 else 0:.0f}% Online</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k2:
        avg_pressure = df_online['pressao'].mean() if len(df_online) > 0 else 0
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Pressão Média</div>
                <div class="kpi-value txt-blue">{avg_pressure:.1f}<small> MCA</small></div>
                <div class="kpi-trend">Sistema Normal</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k3:
        avg_temp = df_online['mancal'].mean() if len(df_online) > 0 else 0
        temp_color = "txt-red" if avg_temp > config['limite_mancal'] else "txt-orange" if avg_temp > config['limite_mancal'] * 0.9 else "txt-green"
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Temp. Mancal</div>
                <div class="kpi-value {temp_color}">{avg_temp:.1f}<small> °C</small></div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k4:
        avg_oleo = df_online['oleo'].mean() if len(df_online) > 0 else 0
        oleo_color = "txt-red" if avg_oleo > config['limite_oleo'] else "txt-orange" if avg_oleo > config['limite_oleo'] * 0.9 else "txt-green"
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Temp. Óleo</div>
                <div class="kpi-value {oleo_color}">{avg_oleo:.1f}<small> °C</small></div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k5:
        alarmes_ativos = len(df_show[df_show['status'] == 'Alarme'])
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Alarmes Ativos</div>
                <div class="kpi-value txt-red">{alarmes_ativos}</div>
                <div class="kpi-trend">{'⚠️ Atenção' if alarmes_ativos > 0 else '✓ OK'}</div>
            </div>
        ''', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Cards das bombas
    for loc in display_locais:
        st.markdown(f'<div class="section-header">{loc}</div>', unsafe_allow_html=True)
        
        subset = df_show[df_show['local'] == loc]
        
        if len(subset) == 0:
            st.info(f"Nenhuma bomba encontrada em {loc}")
            continue
        
        cols = st.columns(min(4, len(subset)))
        
        for i, row in enumerate(subset.to_dict('records')):
            with cols[i % len(cols)]:
                health_score = get_health_score(row, config)
                health_color = get_health_color(health_score)
                
                icon_vibra = "⚠️" if row['vibra'] > config['limite_rms'] * 0.7 else "✅"
                color_vibra = "txt-red" if row['vibra'] > config['limite_rms'] else "txt-orange" if row['vibra'] > config['limite_rms'] * 0.7 else "txt-green"
                
                icon_temp = "🔥" if row['mancal'] > config['limite_mancal'] * 0.9 else "🌡️"
                color_temp = "txt-red" if row['mancal'] > config['limite_mancal'] else "txt-orange" if row['mancal'] > config['limite_mancal'] * 0.9 else ""
                
                icon_oleo = "🔥" if row['oleo'] > config['limite_oleo'] * 0.9 else "💧"
                color_oleo = "txt-red" if row['oleo'] > config['limite_oleo'] else "txt-orange" if row['oleo'] > config['limite_oleo'] * 0.9 else ""
                
                badge_class = f"badge-{row['status'].lower()}"
                
                card_html = f"""
                <div class="pump-card status-{row['status']}">
                    <div class="card-sub">{row['local']}</div>
                    <div class="card-header">
                        <span>BOMBA {row['id']}</span>
                        <span style="font-size: 0.75rem; padding: 4px 12px; border-radius: 8px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); color: #38bdf8;">{row['status']}</span>
                    </div>
                    <div style="text-align: center; margin: 10px 0;">
                        <div style="font-size: 0.7rem; color: #94a3b8; margin-bottom: 4px;">SAÚDE DO EQUIPAMENTO</div>
                        <div style="font-size: 2rem; font-weight: 700; color: {health_color};">{health_score}<small style="font-size: 0.5em;">/100</small></div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 1rem;">
                        <div class="metric-item">
                            <div class="m-label">⚙️ Pressão</div>
                            <div class="m-val txt-blue">{row['pressao']:.1f}<small> MCA</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">{icon_temp} Mancal</div>
                            <div class="m-val {color_temp}">{row['mancal']:.1f}<small> °C</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">{icon_oleo} Óleo</div>
                            <div class="m-val {color_oleo}">{row['oleo']:.1f}<small> °C</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">{icon_vibra} Vibração</div>
                            <div class="m-val {color_vibra}">{row['vibra']:.2f}<small> mm/s</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">⚡ Corrente</div>
                            <div class="m-val">{row.get('corrente', 0):.1f}<small> A</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">🔌 Potência</div>
                            <div class="m-val">{row.get('potencia', 0):.1f}<small> kW</small></div>
                        </div>
                    </div>
                </div>
                """
                
                st.markdown(card_html, unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                
                if st.button(f"📊 Ver Detalhes", key=f"btn_{row['local']}_{row['id']}", use_container_width=True):
                    st.session_state.selected_pump_id = row['id']
                    st.session_state.selected_local = row['local']
                    st.session_state.view = 'detalhes'
                    st.rerun()

# Continuar com as outras views no próximo bloco...
elif st.session_state.view == 'config':
    st.markdown("### ⚙️ Configurações do Sistema")
    st.info("💡 Ajuste os limites de alarmes. As alterações serão salvas no banco de dados.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["⚙️ Pressão", "〰️ Vibração", "🌡️ Temp. Mancal", "💧 Temp. Óleo"])
    
    with tab1:
        st.markdown("#### Configurações de Pressão")
        limite_pressao = st.number_input(
            "Limite Mínimo de Pressão (bar)",
            min_value=0.1,
            max_value=10.0,
            value=float(config['limite_pressao']),
            step=0.1,
            help="Pressão abaixo deste valor gera alarme"
        )
        
        if st.button("💾 Salvar Pressão", type="primary"):
            config['limite_pressao'] = limite_pressao
            if save_config_to_db(config):
                st.success("✅ Configuração salva!")
                st.cache_data.clear()
                st.rerun()
    
    with tab2:
        st.markdown("#### Configurações de Vibração")
        limite_rms = st.number_input(
            "Limite RMS (mm/s)",
            min_value=0.1,
            max_value=10.0,
            value=float(config['limite_rms']),
            step=0.1
        )
        
        if st.button("💾 Salvar Vibração", type="primary"):
            config['limite_rms'] = limite_rms
            if save_config_to_db(config):
                st.success("✅ Configuração salva!")
                st.cache_data.clear()
                st.rerun()
    
    with tab3:
        st.markdown("#### Configurações de Temperatura do Mancal")
        limite_mancal = st.number_input(
            "Limite Máximo (°C)",
            min_value=20,
            max_value=150,
            value=int(config['limite_mancal']),
            step=5
        )
        
        if st.button("💾 Salvar Mancal", type="primary"):
            config['limite_mancal'] = limite_mancal
            if save_config_to_db(config):
                st.success("✅ Configuração salva!")
                st.cache_data.clear()
                st.rerun()
    
    with tab4:
        st.markdown("#### Configurações de Temperatura do Óleo")
        limite_oleo = st.number_input(
            "Limite Máximo (°C)",
            min_value=20,
            max_value=150,
            value=int(config['limite_oleo']),
            step=5
        )
        
        if st.button("💾 Salvar Óleo", type="primary"):
            config['limite_oleo'] = limite_oleo
            if save_config_to_db(config):
                st.success("✅ Configuração salva!")
                st.cache_data.clear()
                st.rerun()

elif st.session_state.view == 'alarmes':
    st.markdown("### 🚨 Central de Alarmes")
    
    df_alarmes = get_alarmes()
    
    if len(df_alarmes) == 0:
        st.success("✅ Nenhum alarme ativo no momento!")
    else:
        for idx, row in df_alarmes.iterrows():
            status_color = "#10b981" if row['ack'] else "#ef4444"
            st.markdown(f"""
                <div style='background: rgba(15, 23, 42, 0.5); border-left: 4px solid {status_color}; padding: 15px; border-radius: 8px; margin: 10px 0;'>
                    <div style='font-size: 0.85rem; color: #94a3b8;'>{row['timestamp']}</div>
                    <div style='font-size: 1.2rem; font-weight: 600; color: white; margin: 5px 0;'>{row['bomba']}</div>
                    <div style='font-size: 1rem; color: #e2e8f0;'>{row['mensagem']}</div>
                </div>
            """, unsafe_allow_html=True)

# Rodapé
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(f"""
    <div style='text-align: center; color: #64748b; font-size: 0.8rem; padding: 20px; border-top: 1px solid #1e293b;'>
        GS Inima Sistemas © 2025 | Conectado ao Supabase | Última atualização: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
    </div>
""", unsafe_allow_html=True)
