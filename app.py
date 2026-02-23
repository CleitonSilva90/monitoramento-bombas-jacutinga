import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta
import time
from supabase import create_client, Client

# ============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ============================================================================

st.set_page_config(
    page_title="GS Inima | Monitoramento Avançado",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'About': "Sistema de Monitoramento Industrial - v3.0 | Integrado com Supabase"
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

@st.cache_data(ttl=10)  # Cache de 10 segundos para atualização automática
def get_current_data():
    """Busca dados atuais do Supabase"""
    try:
        response = supabase.table('status_atual').select('*').execute()
        
        if response.data and len(response.data) > 0:
            df = pd.DataFrame(response.data)
            
            # Mapear id_bomba para formato esperado (ex: "jacutinga_b01" -> local="JACUTINGA", id="B01")
            df['local'] = df['id_bomba'].apply(lambda x: x.split('_')[0].upper())
            df['id'] = df['id_bomba'].apply(lambda x: x.split('_')[1].upper())
            
            # Converter pressão de bar para MCA
            df['pressao_mca'] = df['pressao'] * 10.197
            
            # Renomear colunas
            df = df.rename(columns={'rms': 'vibra', 'pressao_mca': 'pressao'})
            
            # Determinar status baseado nos limites e última batida
            config = get_config()
            df['status'] = df.apply(lambda row: determine_status(row, config), axis=1)
            
            # Adicionar campos mockup temporários (até serem implementados no ESP32)
            df['corrente'] = df.get('corrente', 45.0).fillna(45.0)
            df['potencia'] = df.get('potencia', 22.0).fillna(22.0)
            df['horas_operacao'] = 8234  # Placeholder
            df['ultima_manutencao'] = "2024-11-15"  # Placeholder
            
            return df[['id', 'local', 'status', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente', 'potencia', 'horas_operacao', 'ultima_manutencao']]
        else:
            # Se não houver dados, retornar DataFrame vazio
            return pd.DataFrame(columns=['id', 'local', 'status', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente', 'potencia', 'horas_operacao', 'ultima_manutencao'])
            
    except Exception as e:
        st.error(f"Erro ao buscar dados do Supabase: {e}")
        return pd.DataFrame(columns=['id', 'local', 'status', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente', 'potencia', 'horas_operacao', 'ultima_manutencao'])

def determine_status(row, config):
    """Determina o status da bomba baseado nos sensores e última batida"""
    try:
        # Verificar se a bomba está respondendo (última batida)
        if pd.notna(row.get('ultima_batida')):
            ultima_batida = pd.to_datetime(row['ultima_batida'])
            agora = pd.Timestamp.now(tz='UTC')
            diferenca = (agora - ultima_batida).total_seconds() / 60  # em minutos
            
            if diferenca > 5:  # Sem resposta há mais de 5 minutos
                return 'Offline'
        
        # Verificar se há alarmes
        if (row.get('mancal', 0) > config['limite_mancal'] or 
            row.get('oleo', 0) > config['limite_oleo'] or
            row.get('rms', 0) > config['limite_rms'] or
            row.get('pressao', 0) < config['limite_pressao']):
            return 'Alarme'
        
        return 'Online'
        
    except Exception as e:
        return 'Online'  # Default

@st.cache_data(ttl=60)
def get_config():
    """Busca configurações do banco"""
    try:
        response = supabase.table('configuracoes').select('*').eq('id', 1).execute()
        if response.data and len(response.data) > 0:
            config = response.data[0]
            # Converter limite de pressão de bar para MCA se necessário
            if config.get('limite_pressao'):
                config['limite_pressao_mca'] = config['limite_pressao'] * 10.197
            return config
        else:
            # Configurações padrão
            return {
                'limite_mancal': 75.0,
                'limite_oleo': 80.0,
                'limite_pressao': 2.0,
                'limite_rms': 5.0
            }
    except Exception as e:
        # Configurações padrão em caso de erro
        return {
            'limite_mancal': 75.0,
            'limite_oleo': 80.0,
            'limite_pressao': 2.0,
            'limite_rms': 5.0
        }

@st.cache_data(ttl=60)
def get_historical_data(pump_id, local, days=7):
    """Busca dados históricos do Supabase"""
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
            df = df.rename(columns={'rms': 'vibra'})
            
            # Adicionar campos mockup se não existirem
            if 'corrente' not in df.columns:
                df['corrente'] = 45.0
            if 'potencia' not in df.columns:
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
    """Busca logs de alarmes do Supabase"""
    try:
        response = supabase.table('logs_alertas')\
            .select('*')\
            .order('data_hora', desc=True)\
            .limit(50)\
            .execute()
        
        if response.data and len(response.data) > 0:
            df = pd.DataFrame(response.data)
            df = df.rename(columns={
                'data_hora': 'timestamp',
                'bomba': 'bomba',
                'sensor': 'tipo',
                'valor_detectado': 'mensagem'
            })
            df['ack'] = df['status'].apply(lambda x: x != 'Ativo')
            return df
        else:
            return pd.DataFrame(columns=['timestamp', 'bomba', 'tipo', 'mensagem', 'ack'])
            
    except Exception as e:
        return pd.DataFrame(columns=['timestamp', 'bomba', 'tipo', 'mensagem', 'ack'])

def save_config_to_db(config):
    """Salva configurações no banco"""
    try:
        response = supabase.table('configuracoes')\
            .update(config)\
            .eq('id', 1)\
            .execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configurações: {e}")
        return False

# ============================================================================
# 3. CSS PROFISSIONAL AVANÇADO
# ============================================================================

st.markdown("""
    <style>
        /* IMPORTAÇÃO DE FONTES */
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

        /* TEMA GLOBAL */
        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #0f1729;
            --bg-card: #151e32;
            --bg-card-hover: #1a2540;
            --border-color: #1e293b;
            --border-active: #38bdf8;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-blue: #38bdf8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-orange: #f59e0b;
            --accent-purple: #8b5cf6;
        }

        /* FUNDO E TIPOGRAFIA BASE */
        .stApp {
            background: linear-gradient(135deg, var(--bg-primary) 0%, #050810 100%);
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
        }

        /* REMOVER ELEMENTOS PADRÃO DO STREAMLIT */
        [data-testid="stHeader"] { display: none !important; }
        .main .block-container { 
            padding-top: 1.5rem !important; 
            max-width: 100% !important;
        }
        
        /* SCROLLBAR CUSTOMIZADA */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-secondary); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

        /* ===== HEADER PROFISSIONAL ===== */
        .main-header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 1.5rem;
            margin-bottom: 2rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo-section {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .logo-text {
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            font-size: 1.8rem;
            color: var(--text-primary);
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        
        .logo-accent {
            color: var(--accent-blue);
            font-weight: 700;
        }
        
        .status-badge {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--accent-green);
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        /* ===== NAVEGAÇÃO MODERNA ===== */
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
            letter-spacing: 1px;
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

        /* ===== KPI CARDS PROFISSIONAIS ===== */
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
        
        .kpi-value small {
            font-size: 0.6em;
            color: var(--text-muted);
            font-weight: 500;
        }
        
        .kpi-trend {
            font-size: 0.85rem;
            margin-top: 6px;
            font-weight: 600;
            color: var(--text-primary);
        }
            font-weight: 500;
        }
        
        .kpi-trend {
            font-size: 0.8rem;
            margin-top: 6px;
            font-weight: 600;
        }

        /* ===== CARDS DE BOMBA PREMIUM ===== */
        .pump-card {
            background: linear-gradient(145deg, var(--bg-card), var(--bg-secondary));
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        
        .pump-card::after {
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.03) 0%, transparent 70%);
            pointer-events: none;
        }
        
        .pump-card:hover {
            border-color: var(--accent-blue);
            box-shadow: 0 12px 30px rgba(56, 189, 248, 0.2);
            transform: translateY(-6px);
            background: linear-gradient(145deg, var(--bg-card-hover), var(--bg-card));
        }

        /* STATUS COM BORDA COLORIDA */
        .status-Online { border-left: 4px solid var(--accent-green); }
        .status-Alarme { 
            border-left: 4px solid var(--accent-red);
            animation: alertPulse 2s infinite;
        }
        .status-Offline { border-left: 4px solid var(--text-muted); }
        
        @keyframes alertPulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
        }

        /* CABEÇALHO DO CARD */
        .card-header {
            font-family: 'Rajdhani', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
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
        
        .status-badge-card {
            font-size: 0.75rem;
            padding: 4px 12px;
            border-radius: 8px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        
        .badge-online {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--accent-green);
        }
        
        .badge-alarme {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: var(--accent-red);
        }
        
        .badge-offline {
            background: rgba(100, 116, 139, 0.15);
            border: 1px solid rgba(100, 116, 139, 0.3);
            color: var(--text-muted);
        }

        /* GRID DE MÉTRICAS */
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 1rem;
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
            letter-spacing: 0.5px;
            font-weight: 500;
        }
        
        .m-val {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .m-val small {
            font-size: 0.65em;
            color: var(--text-muted);
        }

        /* CORES DE TEXTO */
        .txt-green { color: var(--accent-green) !important; }
        .txt-red { color: var(--accent-red) !important; }
        .txt-blue { color: var(--accent-blue) !important; }
        .txt-orange { color: var(--accent-orange) !important; }
        .txt-purple { color: var(--accent-purple) !important; }

        /* BOTÕES CUSTOMIZADOS */
        .stButton > button {
            background: linear-gradient(135deg, var(--bg-card), var(--bg-secondary)) !important;
            color: var(--accent-blue) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
            font-family: 'Rajdhani', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            padding: 10px 20px !important;
            transition: all 0.3s ease !important;
        }
        
        .stButton > button:hover {
            background: linear-gradient(135deg, var(--bg-card-hover), var(--bg-card)) !important;
            border-color: var(--accent-blue) !important;
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2) !important;
            transform: translateY(-2px) !important;
        }
        
        /* SELECTBOX E MULTISELECT CUSTOMIZADOS */
        .stSelectbox > div > div,
        .stMultiSelect > div > div {
            background: var(--bg-card) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
            color: var(--text-primary) !important;
        }
        
        .stSelectbox label,
        .stMultiSelect label {
            color: var(--text-primary) !important;
            font-family: 'Rajdhani', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1.1rem !important;
            text-transform: uppercase !important;
            letter-spacing: 1.2px !important;
            margin-bottom: 8px !important;
        }
        
        /* Tags do MultiSelect */
        .stMultiSelect [data-baseweb="tag"] {
            background: rgba(56, 189, 248, 0.15) !important;
            border: 1px solid rgba(56, 189, 248, 0.3) !important;
            color: var(--accent-blue) !important;
            border-radius: 6px !important;
            font-family: 'Inter', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
        }
        
        /* Dropdown */
        [data-baseweb="popover"] {
            background: var(--bg-card) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
        }
        
        /* Opções do dropdown */
        [role="option"] {
            background: var(--bg-card) !important;
            color: var(--text-primary) !important;
            font-size: 0.95rem !important;
        }
        
        [role="option"]:hover {
            background: rgba(56, 189, 248, 0.1) !important;
        }
        
        /* Input de número */
        .stNumberInput label {
            color: var(--text-primary) !important;
            font-family: 'Rajdhani', sans-serif !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
        }
        
        .stNumberInput input {
            background: var(--bg-card) !important;
            border: 1px solid var(--border-color) !important;
            color: var(--text-primary) !important;
            font-size: 1rem !important;
        }

        /* SECTION HEADERS */
        .section-header {
            font-family: 'Rajdhani', sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            border-left: 4px solid var(--accent-blue);
            padding-left: 12px;
            margin: 1.5rem 0 1rem 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* TABELAS ESTILIZADAS */
        .styled-table {
            width: 100%;
            background: var(--bg-card);
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }
        
        .styled-table th {
            background: var(--bg-secondary);
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 1px;
            padding: 12px;
        }
        
        .styled-table td {
            padding: 12px;
            border-top: 1px solid var(--border-color);
        }
        
        /* ALERTS */
        .alert-critical {
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid var(--accent-red);
            padding: 12px;
            border-radius: 6px;
            margin: 8px 0;
        }
        
        .alert-warning {
            background: rgba(245, 158, 11, 0.1);
            border-left: 4px solid var(--accent-orange);
            padding: 12px;
            border-radius: 6px;
            margin: 8px 0;
        }
        
        /* LOADING INDICATOR */
        .loading-spinner {
            border: 3px solid rgba(56, 189, 248, 0.1);
            border-top: 3px solid var(--accent-blue);
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* TOOLTIPS */
        .tooltip {
            position: relative;
            cursor: help;
        }
        
        .tooltip::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: var(--bg-secondary);
            color: var(--text-primary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.75rem;
            white-space: nowrap;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s;
            border: 1px solid var(--border-color);
        }
        
        .tooltip:hover::after {
            opacity: 1;
        }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# 4. FUNÇÕES DE UI AUXILIARES
# ============================================================================

def create_gauge_chart(value, max_value, title, color, warning_threshold=None, critical_threshold=None):
    """Cria um gráfico gauge profissional"""
    
    # Define cores baseadas em thresholds
    if critical_threshold and value >= critical_threshold:
        gauge_color = "#ef4444"
    elif warning_threshold and value >= warning_threshold:
        gauge_color = "#f59e0b"
    else:
        gauge_color = color
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
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
    
    # Linha principal
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df[column],
        mode='lines',
        name=title,
        line=dict(color=color, width=2.5),
        fill='tozeroy',
        fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)'
    ))
    
    # Linha de threshold se fornecida
    if show_threshold:
        fig.add_hline(
            y=show_threshold,
            line_dash="dash",
            line_color="#ef4444",
            line_width=2,
            annotation_text=f"Limite: {show_threshold}",
            annotation_position="right"
        )
    
    # Média móvel
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
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(100, 116, 139, 0.1)',
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(100, 116, 139, 0.1)',
            zeroline=False
        )
    )
    
    return fig

def get_health_score(pump_data):
    """Calcula score de saúde da bomba (0-100) usando configurações do banco"""
    score = 100
    
    # Buscar configurações
    config = get_config()
    
    # Penalizações
    if pump_data['status'] == 'Offline':
        return 0
    elif pump_data['status'] == 'Alarme':
        score -= 40
    
    # Vibração
    if pump_data['vibra'] > config.get('limite_rms', 5.0):
        score -= 30
    elif pump_data['vibra'] > config.get('limite_rms', 5.0) * 0.7:
        score -= 15
    elif pump_data['vibra'] > config.get('limite_rms', 5.0) * 0.5:
        score -= 5
    
    # Temperatura Mancal
    if pump_data['mancal'] > config.get('limite_mancal', 75.0):
        score -= 20
    elif pump_data['mancal'] > config.get('limite_mancal', 75.0) * 0.9:
        score -= 10
    
    # Temperatura Óleo
    if pump_data['oleo'] > config.get('limite_oleo', 80.0):
        score -= 20
    elif pump_data['oleo'] > config.get('limite_oleo', 80.0) * 0.9:
        score -= 10
    
    # Pressão (converter de MCA para bar para comparação)
    pressao_bar = pump_data['pressao'] / 10.197 if pump_data['pressao'] > 10 else pump_data['pressao']
    if pressao_bar < config.get('limite_pressao', 2.0):
        score -= 25
    elif pressao_bar < config.get('limite_pressao', 2.0) * 1.2:
        score -= 10
    
    return max(0, score)

def get_health_color(score):
    """Retorna cor baseada no score de saúde"""
    if score >= 80:
        return "#10b981"  # Verde
    elif score >= 60:
        return "#f59e0b"  # Laranja
    else:
        return "#ef4444"  # Vermelho

# ============================================================================
# 5. CONTROLE DE ESTADO E NAVEGAÇÃO
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

# Configurações de alarmes (thresholds)
if 'config' not in st.session_state:
    st.session_state.config = {
        'pressao': {
            'min_range': 0,
            'max_range': 300,  # MCA - Ajustado para escala industrial
            'warning_min': 20,
            'critical_min': 15,
            'unidade': 'MCA'
        },
        'vibra': {
            'warning': 1.5,
            'critical': 3.0,
            'unidade': 'mm/s'
        },
        'mancal': {
            'warning': 60,
            'critical': 75,
            'unidade': '°C'
        },
        'oleo': {
            'warning': 70,
            'critical': 85,
            'unidade': '°C'
        },
        'corrente': {
            'warning': 50,
            'critical': 60,
            'unidade': 'A'
        }
    }

# Função para converter bar para MCA
def bar_to_mca(bar_value):
    """Converte pressão de bar para metros de coluna d'água (MCA)"""
    return bar_value * 10.197

# Função para converter MCA para bar
def mca_to_bar(mca_value):
    """Converte pressão de MCA para bar"""
    return mca_value / 10.197

# ============================================================================
# AUTO-REFRESH: Atualização automática a cada 10 segundos
# ============================================================================

# Inicializar contador de refresh
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# Verificar se passaram 10 segundos
current_time = time.time()
if current_time - st.session_state.last_refresh >= 10:
    st.session_state.last_refresh = current_time
    st.cache_data.clear()  # Limpar cache para forçar nova busca
    st.rerun()

# Placeholder para mostrar tempo até próxima atualização
time_until_refresh = 10 - int(current_time - st.session_state.last_refresh)

# ============================================================================
# 6. HEADER PROFISSIONAL
# ============================================================================

df = get_current_data()

st.markdown(f"""
    <div class="main-header">
        <div class="header-content">
            <div class="logo-section">
                <div class="logo-text">
                    GS INIMA | <span class="logo-accent">SISTEMAS</span>
                </div>
                <div class="status-badge">● CONECTADO AO SUPABASE</div>
                <div style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); color: #38bdf8; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">
                    🔄 Atualiza em {time_until_refresh}s
                </div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ============================================================================
# 7. NAVEGAÇÃO
# ============================================================================

col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])

with col_nav2:
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    n1, n2, n3, n4, n5 = st.columns(5)
    
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
        st.markdown(f'<div class="{nav_class("relatorios")}">', unsafe_allow_html=True)
        if st.button("📄 RELATÓRIOS", key="nav_rel", use_container_width=True):
            st.session_state.view = 'relatorios'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with n5:
        st.markdown(f'<div class="{nav_class("config")}">', unsafe_allow_html=True)
        if st.button("⚙️ CONFIG", key="nav_config", use_container_width=True):
            st.session_state.view = 'config'
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# ============================================================================
# 8. VIEWS PRINCIPAIS
# ============================================================================

# ======================== VIEW: DASHBOARD ========================
if st.session_state.view == 'dashboard':
    
    # Botão de atualização manual e filtros
    refresh_col, filter_col = st.columns([1, 9])
    
    with refresh_col:
        if st.button("🔄 Atualizar", key="manual_refresh", use_container_width=True):
            st.cache_data.clear()
            st.session_state.last_refresh = time.time()
            st.rerun()
    
    with filter_col:
        # Define ordem customizada: JACUTINGA primeiro, depois INTERMEDIÁRIA
        locais_ordenados = ['Todos', 'JACUTINGA', 'INTERMEDIÁRIA']
        sel_local = st.selectbox("📍 Localização", locais_ordenados, index=locais_ordenados.index(st.session_state.filter_local))
        if sel_local != st.session_state.filter_local:
            st.session_state.filter_local = sel_local
            st.rerun()
    
    # Filtragem (agora sem filtro de status)
    if st.session_state.filter_local == 'Todos':
        df_show = df
        display_locais = ['JACUTINGA', 'INTERMEDIÁRIA']  # Ordem fixa
    else:
        df_show = df[df['local'] == st.session_state.filter_local]
        display_locais = [st.session_state.filter_local]
    
    # KPIs Globais
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
                <div class="kpi-trend txt-green">↗ {(online_bombas/total_bombas*100):.0f}% Online</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k2:
        avg_pressure = bar_to_mca(df_online['pressao'].mean()) if len(df_online) > 0 else 0
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Pressão Média</div>
                <div class="kpi-value txt-blue">{avg_pressure:.1f}<small> MCA</small></div>
                <div class="kpi-trend">Sistema Normal</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k3:
        avg_temp = df_online['mancal'].mean() if len(df_online) > 0 else 0
        temp_color = "txt-red" if avg_temp > st.session_state.config['mancal']['critical'] else "txt-orange" if avg_temp > st.session_state.config['mancal']['warning'] else "txt-green"
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Temp. Mancal</div>
                <div class="kpi-value {temp_color}">{avg_temp:.1f}<small> °C</small></div>
                <div class="kpi-trend">Temperatura OK</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k4:
        avg_oleo = df_online['oleo'].mean() if len(df_online) > 0 else 0
        oleo_color = "txt-red" if avg_oleo > st.session_state.config['oleo']['critical'] else "txt-orange" if avg_oleo > st.session_state.config['oleo']['warning'] else "txt-green"
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Temp. Óleo</div>
                <div class="kpi-value {oleo_color}">{avg_oleo:.1f}<small> °C</small></div>
                <div class="kpi-trend">Óleo OK</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k5:
        alarmes_ativos = len(df_show[df_show['status'] == 'Alarme'])
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Alarmes Ativos</div>
                <div class="kpi-value txt-red">{alarmes_ativos}</div>
                <div class="kpi-trend">{'⚠️ Atenção Requerida' if alarmes_ativos > 0 else '✓ Tudo OK'}</div>
            </div>
        ''', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Cards das Bombas por Local
    for loc in display_locais:
        st.markdown(f'<div class="section-header">{loc}</div>', unsafe_allow_html=True)
        
        subset = df_show[df_show['local'] == loc]
        
        if len(subset) == 0:
            st.info(f"Nenhuma bomba encontrada em {loc} com os filtros aplicados.")
            continue
        
        cols = st.columns(min(4, len(subset)))
        
        for i, row in enumerate(subset.to_dict('records')):
            with cols[i % len(cols)]:
                
                # Calcula score de saúde
                health_score = get_health_score(row)
                health_color = get_health_color(health_score)
                
                # Converte pressão para MCA
                pressao_mca = bar_to_mca(row['pressao'])
                
                # Ícones dinâmicos
                icon_vibra = "⚠️" if row['vibra'] > st.session_state.config['vibra']['warning'] else "✅"
                color_vibra = "txt-red" if row['vibra'] > st.session_state.config['vibra']['critical'] else "txt-orange" if row['vibra'] > st.session_state.config['vibra']['warning'] else "txt-green"
                
                icon_temp = "🔥" if row['mancal'] > st.session_state.config['mancal']['warning'] else "🌡️"
                color_temp = "txt-red" if row['mancal'] > st.session_state.config['mancal']['critical'] else "txt-orange" if row['mancal'] > st.session_state.config['mancal']['warning'] else ""
                
                icon_oleo = "🔥" if row['oleo'] > st.session_state.config['oleo']['warning'] else "💧"
                color_oleo = "txt-red" if row['oleo'] > st.session_state.config['oleo']['critical'] else "txt-orange" if row['oleo'] > st.session_state.config['oleo']['warning'] else ""
                
                # Badge de status
                badge_class = f"badge-{row['status'].lower()}"
                
                # HTML do card com grid 2x3
                card_html = f"""
                <div class="pump-card status-{row['status']}" style="position: relative;">
                    <div class="card-sub">{row['local']}</div>
                    <div class="card-header">
                        <span>BOMBA {row['id']}</span>
                        <span class="status-badge-card {badge_class}">{row['status']}</span>
                    </div>
                    <div style="text-align: center; margin: 10px 0;">
                        <div style="font-size: 0.7rem; color: #94a3b8; margin-bottom: 4px;">SAÚDE DO EQUIPAMENTO</div>
                        <div style="font-size: 2rem; font-weight: 700; color: {health_color};">{health_score}<small style="font-size: 0.5em;">/100</small></div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 1rem;">
                        <div class="metric-item">
                            <div class="m-label">⚙️ Pressão</div>
                            <div class="m-val txt-blue">{pressao_mca:.1f}<small> MCA</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">{icon_temp} Mancal</div>
                            <div class="m-val {color_temp}">{row['mancal']}<small> °C</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">{icon_oleo} Óleo</div>
                            <div class="m-val {color_oleo}">{row['oleo']}<small> °C</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">{icon_vibra} Vibração</div>
                            <div class="m-val {color_vibra}">{row['vibra']}<small> mm/s</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">⚡ Corrente</div>
                            <div class="m-val">{row['corrente']}<small> A</small></div>
                        </div>
                        <div class="metric-item">
                            <div class="m-label">🔌 Potência</div>
                            <div class="m-val">{row['potencia']}<small> kW</small></div>
                        </div>
                    </div>
                </div>
                """
                
                st.markdown(card_html, unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                
                # Botão para navegar
                if st.button(f"📊 Ver Detalhes", key=f"btn_{row['local']}_{row['id']}", use_container_width=True):
                    st.session_state.selected_pump_id = row['id']
                    st.session_state.selected_local = row['local']
                    st.session_state.view = 'detalhes'
                    st.rerun()

# ======================== VIEW: DETALHES ========================
elif st.session_state.view == 'detalhes':
    
    # Seletores de navegação
    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([2, 2, 2, 6])
    
    with nav_col1:
        locais = ['JACUTINGA', 'INTERMEDIÁRIA']  # Ordem fixa
        current_local = st.session_state.selected_local if st.session_state.selected_local else locais[0]
        new_local = st.selectbox("📍 Local", locais, index=locais.index(current_local))
    
    with nav_col2:
        bombas_do_local = sorted(df[df['local'] == new_local]['id'].unique())
        current_pump = st.session_state.selected_pump_id if st.session_state.selected_pump_id in bombas_do_local else bombas_do_local[0]
        new_pump = st.selectbox("🔧 Bomba", bombas_do_local, index=bombas_do_local.index(current_pump))
    
    with nav_col3:
        date_ranges = {
            "Últimas 6 horas": 0.25,
            "Último dia": 1,
            "Últimos 3 dias": 3,
            "Última semana": 7,
            "Últimas 2 semanas": 14,
            "Último mês": 30
        }
        selected_range = st.selectbox("📅 Período", list(date_ranges.keys()), index=2)
        st.session_state.date_range = date_ranges[selected_range]
    
    # Atualiza estado
    if new_local != st.session_state.selected_local or new_pump != st.session_state.selected_pump_id:
        st.session_state.selected_local = new_local
        st.session_state.selected_pump_id = new_pump
        st.rerun()
    
    # Dados da bomba
    pump_data = df[(df['local'] == st.session_state.selected_local) & (df['id'] == st.session_state.selected_pump_id)].iloc[0]
    historical_df = get_historical_data(st.session_state.selected_pump_id, st.session_state.selected_local, days=st.session_state.date_range)
    
    st.markdown("---")
    
    # Header da bomba
    header_col1, header_col2, header_col3 = st.columns([3, 2, 2])
    
    with header_col1:
        status_color = {"Online": "#10b981", "Alarme": "#ef4444", "Offline": "#64748b"}[pump_data['status']]
        st.markdown(f"""
            <h1 style='font-family: Rajdhani; margin: 0; font-size: 2rem;'>
                {pump_data['local']} | BOMBA {pump_data['id']}
            </h1>
            <p style='color: {status_color}; font-weight: bold; font-size: 1.1rem;'>
                ● STATUS: {pump_data['status'].upper()}
            </p>
        """, unsafe_allow_html=True)
    
    with header_col2:
        health_score = get_health_score(pump_data)
        health_color = get_health_color(health_score)
        st.markdown(f"""
            <div style='text-align: center; background: var(--bg-card); padding: 15px; border-radius: 10px; border: 2px solid {health_color};'>
                <div style='font-size: 0.8rem; color: #94a3b8; margin-bottom: 5px;'>SAÚDE</div>
                <div style='font-size: 2.5rem; font-weight: 700; color: {health_color};'>{health_score}<small style='font-size: 0.5em;'>/100</small></div>
            </div>
        """, unsafe_allow_html=True)
    
    with header_col3:
        st.markdown(f"""
            <div style='background: var(--bg-card); padding: 15px; border-radius: 10px; border: 1px solid var(--border-color);'>
                <div style='font-size: 0.7rem; color: #94a3b8; margin-bottom: 8px;'>HORAS DE OPERAÇÃO</div>
                <div style='font-size: 1.5rem; font-weight: 700; color: white;'>{pump_data['horas_operacao']:,}h</div>
                <div style='font-size: 0.7rem; color: #64748b; margin-top: 5px;'>Últ. Manutenção: {pump_data['ultima_manutencao']}</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Gauges principais
    st.markdown("### 🎯 Indicadores em Tempo Real")
    gauge_col1, gauge_col2, gauge_col3, gauge_col4 = st.columns(4)
    
    with gauge_col1:
        st.plotly_chart(
            create_gauge_chart(
                pump_data['vibra'], 
                5.0, 
                "Vibração (mm/s)", 
                "#10b981", 
                warning_threshold=st.session_state.config['vibra']['warning'], 
                critical_threshold=st.session_state.config['vibra']['critical']
            ),
            use_container_width=True
        )
    
    with gauge_col2:
        pressao_mca = bar_to_mca(pump_data['pressao'])
        st.plotly_chart(
            create_gauge_chart(
                pressao_mca, 
                st.session_state.config['pressao']['max_range'], 
                "Pressão (MCA)", 
                "#38bdf8", 
                warning_threshold=st.session_state.config['pressao']['warning_min'], 
                critical_threshold=st.session_state.config['pressao']['critical_min']
            ),
            use_container_width=True
        )
    
    with gauge_col3:
        st.plotly_chart(
            create_gauge_chart(
                pump_data['mancal'], 
                100, 
                "Temp. Mancal (°C)", 
                "#f59e0b", 
                warning_threshold=st.session_state.config['mancal']['warning'], 
                critical_threshold=st.session_state.config['mancal']['critical']
            ),
            use_container_width=True
        )
    
    with gauge_col4:
        st.plotly_chart(
            create_gauge_chart(
                pump_data['oleo'], 
                100, 
                "Temp. Óleo (°C)", 
                "#ef4444", 
                warning_threshold=st.session_state.config['oleo']['warning'], 
                critical_threshold=st.session_state.config['oleo']['critical']
            ),
            use_container_width=True
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Gráficos temporais
    st.markdown("### 📈 Tendências Históricas")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🌊 Vibração", "⚙️ Pressão", "🌡️ Temperaturas", "⚡ Energia"])
    
    with tab1:
        st.plotly_chart(
            create_time_series_chart(historical_df, 'vibra', 'Vibração', '#10b981', 'Vibração (mm/s)', show_threshold=3.0),
            use_container_width=True
        )
        
        # Estatísticas
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        stat_col1.metric("Atual", f"{pump_data['vibra']:.2f} mm/s")
        stat_col2.metric("Média", f"{historical_df['vibra'].mean():.2f} mm/s")
        stat_col3.metric("Máximo", f"{historical_df['vibra'].max():.2f} mm/s")
        stat_col4.metric("Mínimo", f"{historical_df['vibra'].min():.2f} mm/s")
    
    with tab2:
        # Converter histórico para MCA
        historical_df_mca = historical_df.copy()
        historical_df_mca['pressao_mca'] = historical_df_mca['pressao'].apply(bar_to_mca)
        
        st.plotly_chart(
            create_time_series_chart(
                historical_df_mca, 
                'pressao_mca', 
                'Pressão', 
                '#38bdf8', 
                'Pressão (MCA)', 
                show_threshold=st.session_state.config['pressao']['critical_min']
            ),
            use_container_width=True
        )
        
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        stat_col1.metric("Atual", f"{pressao_mca:.1f} MCA")
        stat_col2.metric("Média", f"{historical_df_mca['pressao_mca'].mean():.1f} MCA")
        stat_col3.metric("Máximo", f"{historical_df_mca['pressao_mca'].max():.1f} MCA")
        stat_col4.metric("Mínimo", f"{historical_df_mca['pressao_mca'].min():.1f} MCA")
    
    with tab3:
        # Gráfico dual para temperaturas
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=historical_df['timestamp'],
            y=historical_df['mancal'],
            mode='lines',
            name='Mancal',
            line=dict(color='#f59e0b', width=2.5)
        ))
        
        fig.add_trace(go.Scatter(
            x=historical_df['timestamp'],
            y=historical_df['oleo'],
            mode='lines',
            name='Óleo',
            line=dict(color='#ef4444', width=2.5)
        ))
        
        fig.add_hline(y=75, line_dash="dash", line_color="#ef4444", line_width=1, annotation_text="Limite Crítico")
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(15, 23, 42, 0.5)',
            font={'color': '#e2e8f0', 'family': 'Inter'},
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode='x unified',
            yaxis_title="Temperatura (°C)",
            xaxis=dict(showgrid=True, gridcolor='rgba(100, 116, 139, 0.1)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(100, 116, 139, 0.1)'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        stat_col1.metric("Mancal Atual", f"{pump_data['mancal']:.1f} °C")
        stat_col2.metric("Óleo Atual", f"{pump_data['oleo']:.1f} °C")
        stat_col3.metric("Mancal Médio", f"{historical_df['mancal'].mean():.1f} °C")
        stat_col4.metric("Óleo Médio", f"{historical_df['oleo'].mean():.1f} °C")
    
    with tab4:
        # Gráfico dual para energia
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=historical_df['timestamp'],
            y=historical_df['corrente'],
            mode='lines',
            name='Corrente',
            line=dict(color='#8b5cf6', width=2.5),
            yaxis='y'
        ))
        
        fig.add_trace(go.Scatter(
            x=historical_df['timestamp'],
            y=historical_df['potencia'],
            mode='lines',
            name='Potência',
            line=dict(color='#06b6d4', width=2.5),
            yaxis='y2'
        ))
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(15, 23, 42, 0.5)',
            font={'color': '#e2e8f0', 'family': 'Inter'},
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode='x unified',
            xaxis=dict(showgrid=True, gridcolor='rgba(100, 116, 139, 0.1)'),
            yaxis=dict(
                title="Corrente (A)",
                showgrid=True,
                gridcolor='rgba(100, 116, 139, 0.1)'
            ),
            yaxis2=dict(
                title="Potência (kW)",
                overlaying='y',
                side='right',
                showgrid=False
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        stat_col1.metric("Corrente Atual", f"{pump_data['corrente']:.1f} A")
        stat_col2.metric("Potência Atual", f"{pump_data['potencia']:.1f} kW")
        stat_col3.metric("Corrente Média", f"{historical_df['corrente'].mean():.1f} A")
        stat_col4.metric("Potência Média", f"{historical_df['potencia'].mean():.1f} kW")

# ======================== VIEW: ALARMES ========================
elif st.session_state.view == 'alarmes':
    
    st.markdown("### 🚨 Central de Alarmes")
    
    # Filtros de alarmes com melhor estilo
    filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 6])
    
    with filter_col1:
        tipo_filter = st.multiselect(
            "🔔 Tipo",
            ["CRÍTICO", "ALERTA", "FALHA"],
            default=["CRÍTICO", "ALERTA", "FALHA"],
            key="alarm_tipo_filter"
        )
    
    with filter_col2:
        ack_filter = st.selectbox(
            "✓ Status",
            ["Todos", "Não Reconhecidos", "Reconhecidos"],
            key="alarm_ack_filter"
        )
    
    # Dados de alarmes
    df_alarmes = get_alarmes()
    
    # Aplicar filtros
    df_alarmes_filtered = df_alarmes[df_alarmes['tipo'].isin(tipo_filter)]
    if ack_filter == "Não Reconhecidos":
        df_alarmes_filtered = df_alarmes_filtered[df_alarmes_filtered['ack'] == False]
    elif ack_filter == "Reconhecidos":
        df_alarmes_filtered = df_alarmes_filtered[df_alarmes_filtered['ack'] == True]
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # KPIs de alarmes
    k1, k2, k3, k4 = st.columns(4)
    
    with k1:
        total_alarmes = len(df_alarmes_filtered)
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Total de Alarmes</div>
                <div class="kpi-value">{total_alarmes}</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k2:
        criticos = len(df_alarmes_filtered[df_alarmes_filtered['tipo'] == 'CRÍTICO'])
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Críticos</div>
                <div class="kpi-value txt-red">{criticos}</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k3:
        nao_ack = len(df_alarmes_filtered[df_alarmes_filtered['ack'] == False])
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Não Reconhecidos</div>
                <div class="kpi-value txt-orange">{nao_ack}</div>
            </div>
        ''', unsafe_allow_html=True)
    
    with k4:
        ack = len(df_alarmes_filtered[df_alarmes_filtered['ack'] == True])
        st.markdown(f'''
            <div class="kpi-card">
                <div class="kpi-label">Reconhecidos</div>
                <div class="kpi-value txt-green">{ack}</div>
            </div>
        ''', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Tabela de alarmes
    if len(df_alarmes_filtered) == 0:
        st.info("✅ Nenhum alarme encontrado com os filtros aplicados.")
    else:
        for idx, row in df_alarmes_filtered.iterrows():
            
            tipo_color = {
                "CRÍTICO": "#ef4444",
                "ALERTA": "#f59e0b",
                "FALHA": "#64748b"
            }[row['tipo']]
            
            tipo_bg = {
                "CRÍTICO": "rgba(239, 68, 68, 0.1)",
                "ALERTA": "rgba(245, 158, 11, 0.1)",
                "FALHA": "rgba(100, 116, 139, 0.1)"
            }[row['tipo']]
            
            ack_status = "✓ Reconhecido" if row['ack'] else "⚠ Pendente"
            ack_color = "#10b981" if row['ack'] else "#f59e0b"
            
            st.markdown(f"""
                <div style='background: {tipo_bg}; border-left: 4px solid {tipo_color}; padding: 15px; border-radius: 8px; margin: 10px 0;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div>
                            <div style='font-size: 0.85rem; color: #94a3b8; margin-bottom: 5px;'>{row['timestamp']}</div>
                            <div style='font-size: 1.2rem; font-weight: 600; color: white; margin-bottom: 5px;'>{row['bomba']}</div>
                            <div style='font-size: 1rem; color: #e2e8f0;'>{row['mensagem']}</div>
                        </div>
                        <div style='text-align: right;'>
                            <div style='background: {tipo_bg}; border: 1px solid {tipo_color}; color: {tipo_color}; padding: 6px 12px; border-radius: 6px; font-weight: 600; margin-bottom: 8px;'>{row['tipo']}</div>
                            <div style='color: {ack_color}; font-size: 0.9rem; font-weight: 600;'>{ack_status}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

# ======================== VIEW: RELATÓRIOS ========================
elif st.session_state.view == 'relatorios':
    
    st.markdown("### 📄 Geração de Relatórios")
    
    st.info("🚧 Módulo de relatórios em desenvolvimento. Em breve você poderá gerar relatórios personalizados em PDF e Excel.")
    
    # Preview de funcionalidades
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
            #### Relatórios Disponíveis:
            - 📊 Relatório de Performance Mensal
            - 🔧 Histórico de Manutenções
            - ⚠️ Análise de Alarmes
            - 📈 Tendências de Operação
            - 💰 Análise de Consumo Energético
        """)
    
    with col2:
        st.markdown("""
            #### Formatos de Exportação:
            - 📄 PDF (Relatório Completo)
            - 📊 Excel (Dados Brutos)
            - 📈 CSV (Séries Temporais)
            - 🖼️ PNG (Gráficos)
        """)

# ======================== VIEW: CONFIGURAÇÃO ========================
elif st.session_state.view == 'config':
    
    st.markdown("### ⚙️ Configurações do Sistema")
    
    st.info("💡 Ajuste os limites de alarmes e ranges dos sensores. As alterações são aplicadas imediatamente.")
    
    # Tabs para organizar configurações
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚙️ Pressão", 
        "〰️ Vibração", 
        "🌡️ Temp. Mancal", 
        "💧 Temp. Óleo", 
        "⚡ Corrente"
    ])
    
    # ========== CONFIGURAÇÃO DE PRESSÃO ==========
    with tab1:
        st.markdown("#### Configurações de Pressão")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 📊 Range do Sensor")
            
            min_range = st.number_input(
                "Mínimo (MCA)",
                min_value=0.0,
                max_value=300.0,
                value=float(st.session_state.config['pressao']['min_range']),
                step=5.0,
                key="config_pressao_min"
            )
            
            max_range = st.number_input(
                "Máximo (MCA)",
                min_value=10.0,
                max_value=300.0,
                value=float(st.session_state.config['pressao']['max_range']),
                step=10.0,
                key="config_pressao_max"
            )
            
            if max_range <= min_range:
                st.error("⚠️ O valor máximo deve ser maior que o mínimo!")
        
        with col2:
            st.markdown("##### 🚨 Limites de Alarme")
            
            warning_min = st.number_input(
                "Warning - Pressão Mínima (MCA)",
                min_value=float(min_range),
                max_value=float(max_range),
                value=float(st.session_state.config['pressao']['warning_min']),
                step=5.0,
                help="Pressão abaixo deste valor gera alerta",
                key="config_pressao_warning"
            )
            
            critical_min = st.number_input(
                "Crítico - Pressão Mínima (MCA)",
                min_value=float(min_range),
                max_value=float(warning_min),
                value=float(st.session_state.config['pressao']['critical_min']),
                step=5.0,
                help="Pressão abaixo deste valor gera alarme crítico",
                key="config_pressao_critical"
            )
        
        # Visualização do range
        st.markdown("##### 📈 Visualização dos Limites")
        
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # Zona verde (normal)
        fig.add_trace(go.Scatter(
            x=[warning_min, max_range],
            y=[1, 1],
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.2)',
            line=dict(width=0),
            showlegend=True,
            name='Normal',
            hoverinfo='skip'
        ))
        
        # Zona amarela (warning)
        fig.add_trace(go.Scatter(
            x=[critical_min, warning_min],
            y=[1, 1],
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.2)',
            line=dict(width=0),
            showlegend=True,
            name='Warning',
            hoverinfo='skip'
        ))
        
        # Zona vermelha (crítico)
        fig.add_trace(go.Scatter(
            x=[min_range, critical_min],
            y=[1, 1],
            fill='tozeroy',
            fillcolor='rgba(239, 68, 68, 0.2)',
            line=dict(width=0),
            showlegend=True,
            name='Crítico',
            hoverinfo='skip'
        ))
        
        # Linhas de limite
        fig.add_vline(x=warning_min, line_dash="dash", line_color="#f59e0b", annotation_text="Warning")
        fig.add_vline(x=critical_min, line_dash="dash", line_color="#ef4444", annotation_text="Crítico")
        
        fig.update_layout(
            xaxis_title="Pressão (MCA)",
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            height=200,
            margin=dict(l=10, r=10, t=10, b=40),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(15, 23, 42, 0.5)',
            font=dict(color='#e2e8f0'),
            xaxis=dict(range=[min_range, max_range]),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Botão de salvar
        if st.button("💾 Salvar Configurações de Pressão", type="primary", use_container_width=True):
            st.session_state.config['pressao']['min_range'] = min_range
            st.session_state.config['pressao']['max_range'] = max_range
            st.session_state.config['pressao']['warning_min'] = warning_min
            st.session_state.config['pressao']['critical_min'] = critical_min
            
            # Salvar no banco de dados
            config_to_save = {
                'limite_pressao': mca_to_bar(critical_min)  # Salvar em bar
            }
            if save_config_to_db(config_to_save):
                st.success("✅ Configurações de pressão salvas no banco de dados!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar no banco de dados")
    
    # ========== CONFIGURAÇÃO DE VIBRAÇÃO ==========
    with tab2:
        st.markdown("#### Configurações de Vibração")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 🚨 Limite de Warning")
            
            vibra_warning = st.number_input(
                "Vibração Warning (mm/s)",
                min_value=0.1,
                max_value=10.0,
                value=float(st.session_state.config['vibra']['warning']),
                step=0.1,
                help="Vibração acima deste valor gera alerta",
                key="config_vibra_warning"
            )
        
        with col2:
            st.markdown("##### 🚨 Limite Crítico")
            
            vibra_critical = st.number_input(
                "Vibração Crítica (mm/s)",
                min_value=vibra_warning,
                max_value=10.0,
                value=float(st.session_state.config['vibra']['critical']),
                step=0.1,
                help="Vibração acima deste valor gera alarme crítico",
                key="config_vibra_critical"
            )
        
        # Gauge preview
        st.markdown("##### 📊 Preview do Gauge")
        st.plotly_chart(
            create_gauge_chart(2.5, 5.0, "Vibração (mm/s)", "#10b981", warning_threshold=vibra_warning, critical_threshold=vibra_critical),
            use_container_width=True
        )
        
        if st.button("💾 Salvar Configurações de Vibração", type="primary", use_container_width=True):
            st.session_state.config['vibra']['warning'] = vibra_warning
            st.session_state.config['vibra']['critical'] = vibra_critical
            
            # Salvar no banco
            config_to_save = {'limite_rms': vibra_critical}
            if save_config_to_db(config_to_save):
                st.success("✅ Configurações de vibração salvas no banco de dados!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar no banco de dados")
    
    # ========== CONFIGURAÇÃO DE TEMP. MANCAL ==========
    with tab3:
        st.markdown("#### Configurações de Temperatura do Mancal")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 🚨 Limite de Warning")
            
            mancal_warning = st.number_input(
                "Temperatura Warning (°C)",
                min_value=20,
                max_value=100,
                value=int(st.session_state.config['mancal']['warning']),
                step=5,
                help="Temperatura acima deste valor gera alerta",
                key="config_mancal_warning"
            )
        
        with col2:
            st.markdown("##### 🚨 Limite Crítico")
            
            mancal_critical = st.number_input(
                "Temperatura Crítica (°C)",
                min_value=mancal_warning,
                max_value=100,
                value=int(st.session_state.config['mancal']['critical']),
                step=5,
                help="Temperatura acima deste valor gera alarme crítico",
                key="config_mancal_critical"
            )
        
        # Gauge preview
        st.markdown("##### 📊 Preview do Gauge")
        st.plotly_chart(
            create_gauge_chart(65, 100, "Temp. Mancal (°C)", "#f59e0b", warning_threshold=mancal_warning, critical_threshold=mancal_critical),
            use_container_width=True
        )
        
        if st.button("💾 Salvar Configurações de Temp. Mancal", type="primary", use_container_width=True):
            st.session_state.config['mancal']['warning'] = mancal_warning
            st.session_state.config['mancal']['critical'] = mancal_critical
            
            # Salvar no banco
            config_to_save = {'limite_mancal': float(mancal_critical)}
            if save_config_to_db(config_to_save):
                st.success("✅ Configurações de temperatura do mancal salvas no banco de dados!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar no banco de dados")
    
    # ========== CONFIGURAÇÃO DE TEMP. ÓLEO ==========
    with tab4:
        st.markdown("#### Configurações de Temperatura do Óleo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 🚨 Limite de Warning")
            
            oleo_warning = st.number_input(
                "Temperatura Warning (°C)",
                min_value=20,
                max_value=100,
                value=int(st.session_state.config['oleo']['warning']),
                step=5,
                help="Temperatura acima deste valor gera alerta",
                key="config_oleo_warning"
            )
        
        with col2:
            st.markdown("##### 🚨 Limite Crítico")
            
            oleo_critical = st.number_input(
                "Temperatura Crítica (°C)",
                min_value=oleo_warning,
                max_value=100,
                value=int(st.session_state.config['oleo']['critical']),
                step=5,
                help="Temperatura acima deste valor gera alarme crítico",
                key="config_oleo_critical"
            )
        
        # Gauge preview
        st.markdown("##### 📊 Preview do Gauge")
        st.plotly_chart(
            create_gauge_chart(75, 100, "Temp. Óleo (°C)", "#ef4444", warning_threshold=oleo_warning, critical_threshold=oleo_critical),
            use_container_width=True
        )
        
        if st.button("💾 Salvar Configurações de Temp. Óleo", type="primary", use_container_width=True):
            st.session_state.config['oleo']['warning'] = oleo_warning
            st.session_state.config['oleo']['critical'] = oleo_critical
            
            # Salvar no banco
            config_to_save = {'limite_oleo': float(oleo_critical)}
            if save_config_to_db(config_to_save):
                st.success("✅ Configurações de temperatura do óleo salvas no banco de dados!")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar no banco de dados")
    
    # ========== CONFIGURAÇÃO DE CORRENTE ==========
    with tab5:
        st.markdown("#### Configurações de Corrente")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 🚨 Limite de Warning")
            
            corrente_warning = st.number_input(
                "Corrente Warning (A)",
                min_value=0,
                max_value=600,
                value=int(st.session_state.config['corrente']['warning']),
                step=5,
                help="Corrente acima deste valor gera alerta",
                key="config_corrente_warning"
            )
        
        with col2:
            st.markdown("##### 🚨 Limite Crítico")
            
            corrente_critical = st.number_input(
                "Corrente Crítica (A)",
                min_value=corrente_warning,
                max_value=600,
                value=int(st.session_state.config['corrente']['critical']),
                step=5,
                help="Corrente acima deste valor gera alarme crítico",
                key="config_corrente_critical"
            )
        
        # Gauge preview
        st.markdown("##### 📊 Preview do Gauge")
        st.plotly_chart(
            create_gauge_chart(45, 100, "Corrente (A)", "#8b5cf6", warning_threshold=corrente_warning, critical_threshold=corrente_critical),
            use_container_width=True
        )
        
        if st.button("💾 Salvar Configurações de Corrente", type="primary", use_container_width=True):
            st.session_state.config['corrente']['warning'] = corrente_warning
            st.session_state.config['corrente']['critical'] = corrente_critical
            st.success("✅ Configurações de corrente salvas com sucesso!")
            st.rerun()
    
    st.markdown("---")
    
    # Seção de reset
    st.markdown("### 🔄 Reset de Configurações")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.warning("⚠️ Esta ação irá restaurar todas as configurações para os valores padrão.")
    
    with col2:
        if st.button("🔄 Restaurar Padrões", use_container_width=True):
            st.session_state.config = {
                'pressao': {
                    'min_range': 0,
                    'max_range': 300,
                    'warning_min': 20,
                    'critical_min': 15,
                    'unidade': 'MCA'
                },
                'vibra': {
                    'warning': 1.5,
                    'critical': 3.0,
                    'unidade': 'mm/s'
                },
                'mancal': {
                    'warning': 60,
                    'critical': 75,
                    'unidade': '°C'
                },
                'oleo': {
                    'warning': 70,
                    'critical': 85,
                    'unidade': '°C'
                },
                'corrente': {
                    'warning': 500,
                    'critical': 600,
                    'unidade': 'A'
                }
            }
            st.success("✅ Configurações restauradas para os valores padrão!")
            st.rerun()

# ============================================================================
# 9. RODAPÉ
# ============================================================================

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(f"""
    <div style='text-align: center; color: #64748b; font-size: 0.8rem; padding: 20px; border-top: 1px solid #1e293b;'>
        GS Inima Sistemas © 2025 | Sistema de Monitoramento Industrial v3.0 | Conectado ao Supabase<br>
        Última atualização: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} | Próxima atualização automática em {time_until_refresh}s
    </div>
""", unsafe_allow_html=True)
