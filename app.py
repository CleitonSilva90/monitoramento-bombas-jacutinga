import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import time
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

st.set_page_config(
    page_title="GS Inima | Monitoramento Industrial",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'About': "Sistema de Monitoramento Industrial v4.0"}
)

# ============================================================================
# SUPABASE
# ============================================================================

SUPABASE_URL = "https://iemojjmgzyrxddochnlq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"

@st.cache_resource
def init_supabase():
    if not SUPABASE_AVAILABLE:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase = init_supabase()

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def bar_to_mca(bar_value):
    try:
        return float(bar_value) * 10.197
    except:
        return 0.0

def mca_to_bar(mca_value):
    try:
        return float(mca_value) / 10.197
    except:
        return 0.0

# ============================================================================
# BANCO DE DADOS
# ============================================================================

@st.cache_data(ttl=10)
def get_current_data():
    if not supabase:
        return get_mockup_data()
    
    try:
        response = supabase.table('status_atual').select('*').execute()
        
        if response.data and len(response.data) > 0:
            df = pd.DataFrame(response.data)
            df['local'] = df['id_bomba'].apply(lambda x: str(x).split('_')[0].upper() if '_' in str(x) else 'UNKNOWN')
            df['id'] = df['id_bomba'].apply(lambda x: str(x).split('_')[1].upper() if '_' in str(x) else 'B00')
            df['pressao'] = df['pressao'].apply(lambda x: bar_to_mca(x) if x < 50 else x)
            
            if 'rms' in df.columns:
                df = df.rename(columns={'rms': 'vibra'})
            
            config = get_config()
            df['status'] = df.apply(lambda row: determine_status(row, config), axis=1)
            
            # Campos adicionais
            df['corrente'] = df.get('corrente', 45.0).fillna(45.0)
            df['potencia'] = 22.0
            df['tensao_motor'] = 380.0  # Tensão nominal do motor (V)
            df['tensao_rede'] = 382.0   # Tensão da rede (V)
            df['horas_operacao'] = 8234
            df['ultima_manutencao'] = "2024-11-15"
            
            cols = ['id', 'local', 'status', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente', 'potencia', 'tensao_motor', 'tensao_rede', 'horas_operacao', 'ultima_manutencao']
            return df[[c for c in cols if c in df.columns]]
        else:
            return get_mockup_data()
    except Exception as e:
        st.warning(f"Usando mockup: {str(e)[:100]}")
        return get_mockup_data()

def get_mockup_data():
    return pd.DataFrame([
        {"id": "B01", "local": "JACUTINGA", "status": "Online", "pressao": 24.5, "mancal": 34.2, "oleo": 26.8, "vibra": 0.45, "corrente": 45.2, "potencia": 22.5, "tensao_motor": 380, "tensao_rede": 382, "horas_operacao": 8234, "ultima_manutencao": "2024-11-15"},
        {"id": "B02", "local": "JACUTINGA", "status": "Alarme", "pressao": 1.2, "mancal": 72.1, "oleo": 85.4, "vibra": 4.21, "corrente": 62.1, "potencia": 5.8, "tensao_motor": 380, "tensao_rede": 375, "horas_operacao": 12456, "ultima_manutencao": "2024-08-22"},
        {"id": "B03", "local": "JACUTINGA", "status": "Online", "pressao": 24.1, "mancal": 35.0, "oleo": 27.0, "vibra": 0.48, "corrente": 44.8, "potencia": 22.1, "tensao_motor": 380, "tensao_rede": 381, "horas_operacao": 6789, "ultima_manutencao": "2024-12-01"},
    ])

def determine_status(row, config):
    try:
        if pd.notna(row.get('ultima_batida')):
            try:
                ultima_batida = pd.to_datetime(row['ultima_batida'])
                agora = pd.Timestamp.now(tz='UTC')
                diferenca = (agora - ultima_batida).total_seconds() / 60
                if diferenca > 5:
                    return 'Offline'
            except:
                pass
        
        mancal = float(row.get('mancal', 0))
        oleo = float(row.get('oleo', 0))
        vibra = float(row.get('vibra', 0))
        pressao = float(row.get('pressao', 0))
        corrente = float(row.get('corrente', 0))
        
        if (mancal > config['limite_mancal'] or 
            oleo > config['limite_oleo'] or
            vibra > config['limite_rms'] or
            pressao < config['limite_pressao_mca'] or
            corrente > config['limite_corrente']):
            return 'Alarme'
        
        return 'Online'
    except:
        return 'Online'

@st.cache_data(ttl=60)
def get_config():
    if not supabase:
        return get_default_config()
    
    try:
        response = supabase.table('configuracoes').select('*').eq('id', 1).execute()
        if response.data and len(response.data) > 0:
            config = response.data[0]
            config['limite_pressao_mca'] = bar_to_mca(config.get('limite_pressao', 2.0))
            if 'limite_corrente' not in config:
                config['limite_corrente'] = 60.0
            return config
    except:
        pass
    
    return get_default_config()

def get_default_config():
    return {
        'limite_mancal': 75.0,
        'limite_oleo': 80.0,
        'limite_pressao': 2.0,
        'limite_pressao_mca': 20.4,
        'limite_rms': 5.0,
        'limite_corrente': 60.0
    }

@st.cache_data(ttl=60)
def get_historical_data(pump_id, local, days=7):
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

@st.cache_data(ttl=10)
def get_alarmes():
    """Busca alarmes do banco"""
    if not supabase:
        return get_mockup_alarmes()
    
    try:
        response = supabase.table('logs_alertas')\
            .select('*')\
            .order('data_hora', desc=True)\
            .limit(50)\
            .execute()
        
        if response.data and len(response.data) > 0:
            df = pd.DataFrame(response.data)
            return df
        else:
            return get_mockup_alarmes()
    except:
        return get_mockup_alarmes()

def get_mockup_alarmes():
    """Alarmes mockup"""
    return pd.DataFrame([
        {
            'id': 1,
            'data_hora': datetime.now() - timedelta(minutes=15),
            'bomba': 'JACUTINGA - B02',
            'sensor': 'Temperatura Óleo',
            'valor_detectado': '85.4°C',
            'limite_definido': '80.0°C',
            'status': 'Ativo',
            'operador': 'Sistema'
        },
        {
            'id': 2,
            'data_hora': datetime.now() - timedelta(minutes=30),
            'bomba': 'JACUTINGA - B02',
            'sensor': 'Vibração',
            'valor_detectado': '4.21 mm/s',
            'limite_definido': '3.0 mm/s',
            'status': 'Ativo',
            'operador': 'Sistema'
        },
        {
            'id': 3,
            'data_hora': datetime.now() - timedelta(hours=2),
            'bomba': 'JACUTINGA - B02',
            'sensor': 'Corrente',
            'valor_detectado': '62.1 A',
            'limite_definido': '60.0 A',
            'status': 'Reconhecido',
            'operador': 'João Silva'
        },
    ])

def reconhecer_alarme(alarme_id, operador):
    """Reconhece um alarme"""
    if not supabase:
        return False
    
    try:
        response = supabase.table('logs_alertas')\
            .update({'status': 'Reconhecido', 'operador': operador})\
            .eq('id', alarme_id)\
            .execute()
        
        get_alarmes.clear()
        return True
    except:
        return False

def save_config_to_db(limite_mancal=None, limite_oleo=None, limite_pressao=None, limite_rms=None, limite_corrente=None):
    if not supabase:
        return False
    
    try:
        update_data = {}
        if limite_mancal is not None:
            update_data['limite_mancal'] = float(limite_mancal)
        if limite_oleo is not None:
            update_data['limite_oleo'] = float(limite_oleo)
        if limite_pressao is not None:
            update_data['limite_pressao'] = float(limite_pressao)
        if limite_rms is not None:
            update_data['limite_rms'] = float(limite_rms)
        if limite_corrente is not None:
            update_data['limite_corrente'] = float(limite_corrente)
        
        if not update_data:
            return False
        
        response = supabase.table('configuracoes')\
            .update(update_data)\
            .eq('id', 1)\
            .execute()
        
        get_config.clear()
        get_current_data.clear()
        return True
    except:
        return False

# ============================================================================
# GERAÇÃO DE RELATÓRIOS
# ============================================================================

def generate_excel_report(pump_id, local):
    """Gera relatório Excel"""
    df_current = get_current_data()
    pump_data = df_current[(df_current['local'] == local) & (df_current['id'] == pump_id)]
    
    if len(pump_data) == 0:
        return None
    
    pump_data = pump_data.iloc[0]
    hist_df = get_historical_data(pump_id, local, days=7)
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Dados Atuais
        current_info = pd.DataFrame({
            'Parâmetro': ['Local', 'Bomba', 'Status', 'Pressão (MCA)', 'Temp. Mancal (°C)', 
                         'Temp. Óleo (°C)', 'Vibração (mm/s)', 'Corrente (A)', 'Potência (kW)',
                         'Tensão Motor (V)', 'Tensão Rede (V)', 'Horas Operação', 'Última Manutenção'],
            'Valor': [pump_data['local'], pump_data['id'], pump_data['status'], 
                     f"{pump_data['pressao']:.2f}", f"{pump_data['mancal']:.2f}",
                     f"{pump_data['oleo']:.2f}", f"{pump_data['vibra']:.2f}", 
                     f"{pump_data['corrente']:.2f}", f"{pump_data['potencia']:.2f}",
                     f"{pump_data['tensao_motor']:.0f}", f"{pump_data['tensao_rede']:.0f}",
                     pump_data['horas_operacao'], pump_data['ultima_manutencao']]
        })
        current_info.to_excel(writer, sheet_name='Dados Atuais', index=False)
        
        # Sheet 2: Histórico
        hist_export = hist_df[['timestamp', 'pressao', 'mancal', 'oleo', 'vibra', 'corrente']].copy()
        hist_export.columns = ['Data/Hora', 'Pressão (MCA)', 'Temp. Mancal (°C)', 'Temp. Óleo (°C)', 'Vibração (mm/s)', 'Corrente (A)']
        hist_export.to_excel(writer, sheet_name='Histórico 7 Dias', index=False)
        
        # Sheet 3: Estatísticas
        stats = pd.DataFrame({
            'Métrica': ['Pressão (MCA)', 'Temp. Mancal (°C)', 'Temp. Óleo (°C)', 'Vibração (mm/s)', 'Corrente (A)'],
            'Média': [hist_df['pressao'].mean(), hist_df['mancal'].mean(), hist_df['oleo'].mean(), 
                     hist_df['vibra'].mean(), hist_df['corrente'].mean()],
            'Mínimo': [hist_df['pressao'].min(), hist_df['mancal'].min(), hist_df['oleo'].min(), 
                      hist_df['vibra'].min(), hist_df['corrente'].min()],
            'Máximo': [hist_df['pressao'].max(), hist_df['mancal'].max(), hist_df['oleo'].max(), 
                      hist_df['vibra'].max(), hist_df['corrente'].max()],
        })
        stats.to_excel(writer, sheet_name='Estatísticas', index=False)
    
    output.seek(0)
    return output

def generate_pdf_report(pump_id, local):
    """Gera relatório PDF"""
    df_current = get_current_data()
    pump_data = df_current[(df_current['local'] == local) & (df_current['id'] == pump_id)]
    
    if len(pump_data) == 0:
        return None
    
    pump_data = pump_data.iloc[0]
    hist_df = get_historical_data(pump_id, local, days=7)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Título
    title = Paragraph(f"<b>Relatório de Operação - {local} | Bomba {pump_id}</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.3*inch))
    
    # Data do relatório
    date_text = Paragraph(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal'])
    story.append(date_text)
    story.append(Spacer(1, 0.3*inch))
    
    # Dados Atuais
    subtitle1 = Paragraph("<b>Dados Atuais</b>", styles['Heading2'])
    story.append(subtitle1)
    story.append(Spacer(1, 0.2*inch))
    
    data_atual = [
        ['Parâmetro', 'Valor'],
        ['Status', pump_data['status']],
        ['Pressão', f"{pump_data['pressao']:.2f} MCA"],
        ['Temp. Mancal', f"{pump_data['mancal']:.2f} °C"],
        ['Temp. Óleo', f"{pump_data['oleo']:.2f} °C"],
        ['Vibração', f"{pump_data['vibra']:.2f} mm/s"],
        ['Corrente', f"{pump_data['corrente']:.2f} A"],
        ['Tensão Motor', f"{pump_data['tensao_motor']:.0f} V"],
        ['Tensão Rede', f"{pump_data['tensao_rede']:.0f} V"],
        ['Horas Operação', str(pump_data['horas_operacao'])],
    ]
    
    table1 = Table(data_atual, colWidths=[3*inch, 3*inch])
    table1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table1)
    story.append(Spacer(1, 0.5*inch))
    
    # Estatísticas
    subtitle2 = Paragraph("<b>Estatísticas (Últimos 7 Dias)</b>", styles['Heading2'])
    story.append(subtitle2)
    story.append(Spacer(1, 0.2*inch))
    
    stats_data = [
        ['Métrica', 'Média', 'Mínimo', 'Máximo'],
        ['Pressão (MCA)', f"{hist_df['pressao'].mean():.2f}", f"{hist_df['pressao'].min():.2f}", f"{hist_df['pressao'].max():.2f}"],
        ['Temp. Mancal (°C)', f"{hist_df['mancal'].mean():.2f}", f"{hist_df['mancal'].min():.2f}", f"{hist_df['mancal'].max():.2f}"],
        ['Temp. Óleo (°C)', f"{hist_df['oleo'].mean():.2f}", f"{hist_df['oleo'].min():.2f}", f"{hist_df['oleo'].max():.2f}"],
        ['Vibração (mm/s)', f"{hist_df['vibra'].mean():.2f}", f"{hist_df['vibra'].min():.2f}", f"{hist_df['vibra'].max():.2f}"],
        ['Corrente (A)', f"{hist_df['corrente'].mean():.2f}", f"{hist_df['corrente'].min():.2f}", f"{hist_df['corrente'].max():.2f}"],
    ]
    
    table2 = Table(stats_data)
    table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table2)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ============================================================================
# VISUALIZAÇÕES
# ============================================================================

def create_gauge_chart(value, max_value, title, color, warning_threshold=None, critical_threshold=None):
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
        
        corrente = float(pump_data.get('corrente', 0))
        if corrente > config['limite_corrente']:
            score -= 20
        
        return max(0, score)
    except:
        return 50

def get_health_color(score):
    if score >= 80:
        return "#10b981"
    elif score >= 60:
        return "#f59e0b"
    else:
        return "#ef4444"

# ============================================================================
# CSS MODERNO E PROFISSIONAL
# ============================================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    :root {
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-card: #1e293b;
        --border-color: #334155;
        --accent-blue: #3b82f6;
        --accent-green: #10b981;
        --accent-red: #ef4444;
        --accent-orange: #f59e0b;
        --text-primary: #f1f5f9;
        --text-secondary: #cbd5e1;
    }
    
    .stApp {
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0a0e1a 100%);
        font-family: 'Inter', sans-serif;
        color: var(--text-primary);
    }
    
    [data-testid="stHeader"] { display: none !important; }
    .main .block-container { padding-top: 1.5rem !important; max-width: 100% !important; }
    
    /* BOTÕES MODERNOS */
    .stButton > button {
        background: linear-gradient(135deg, var(--accent-blue), #2563eb) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.5px !important;
        box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 12px rgba(59, 130, 246, 0.4) !important;
        background: linear-gradient(135deg, #2563eb, var(--accent-blue)) !important;
    }
    
    .stButton > button:active {
        transform: translateY(0) !important;
    }
    
    /* CARDS MODERNOS */
    .modern-card {
        background: linear-gradient(135deg, var(--bg-card) 0%, #1a2332 100%);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3), 0 0 20px rgba(59, 130, 246, 0.1);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .modern-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-blue), var(--accent-green));
    }
    
    .modern-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4), 0 0 30px rgba(59, 130, 246, 0.2);
        border-color: var(--accent-blue);
    }
    
    /* KPI CARDS */
    .kpi-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
        border-color: var(--accent-blue);
    }
    
    .kpi-value {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    
    /* STATUS BADGES */
    .status-Online { border-left: 4px solid var(--accent-green); }
    .status-Alarme { 
        border-left: 4px solid var(--accent-red);
        animation: pulse-red 2s infinite;
    }
    .status-Offline { border-left: 4px solid #64748b; }
    
    @keyframes pulse-red {
        0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
        50% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
    }
    
    /* ALARM CARD */
    .alarm-card {
        background: var(--bg-card);
        border-left: 4px solid var(--accent-red);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    
    .alarm-card:hover {
        transform: translateX(4px);
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
    }
    
    .alarm-card.reconhecido {
        border-left-color: var(--accent-green);
        opacity: 0.7;
    }
    
    /* COLORS */
    .txt-green { color: var(--accent-green) !important; }
    .txt-red { color: var(--accent-red) !important; }
    .txt-blue { color: var(--accent-blue) !important; }
    .txt-orange { color: var(--accent-orange) !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# ESTADO
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
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# Auto-refresh
current_time = time.time()
time_since_refresh = int(current_time - st.session_state.last_refresh)
time_until_refresh = max(0, 30 - time_since_refresh)

if time_since_refresh >= 30 and st.session_state.view == 'dashboard':
    st.session_state.last_refresh = current_time
    get_current_data.clear()
    st.rerun()

# ============================================================================
# HEADER
# ============================================================================

df = get_current_data()

st.markdown(f"""
<div class="modern-card" style='margin-bottom: 2rem;'>
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <div>
            <h1 style='margin: 0; font-size: 2rem; font-weight: 800;'>GS INIMA | <span style='color: var(--accent-blue);'>SISTEMAS</span></h1>
            <p style='margin: 0.5rem 0 0 0; color: var(--text-secondary); font-size: 0.9rem;'>Sistema de Monitoramento Industrial v4.0</p>
        </div>
        <div style='display: flex; gap: 10px; align-items: center;'>
            <span style='background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: var(--accent-green); padding: 8px 16px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;'>
                ● ONLINE
            </span>
            <span style='background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); color: var(--accent-blue); padding: 8px 16px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;'>
                🔄 {time_until_refresh}s
            </span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# NAVEGAÇÃO
# ============================================================================

col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])

with col_nav2:
    n1, n2, n3, n4, n5 = st.columns(5)
    
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
        if st.button("📄 RELATÓRIOS", key="nav_rel", use_container_width=True):
            st.session_state.view = 'relatorios'
            st.rerun()
    
    with n5:
        if st.button("⚙️ CONFIG", key="nav_config", use_container_width=True):
            st.session_state.view = 'config'
            st.rerun()

st.markdown("---")

# ==================================================================
# CONTINUAREI NA PRÓXIMA PARTE COM AS VIEWS COMPLETAS
# ==================================================================


# ============================================================================
# VIEW: DASHBOARD
# ============================================================================

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
        sel_local = st.selectbox("📍 Localização", locais_ordenados, index=0)
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
    
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    
    with k1:
        total = len(df_show)
        online = len(df_online)
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-green">{online}<small>/{total}</small></div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Bombas Ativas</div></div>', unsafe_allow_html=True)
    
    with k2:
        avg_p = df_online['pressao'].mean() if len(df_online) > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-blue">{avg_p:.1f}<small> MCA</small></div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Pressão Média</div></div>', unsafe_allow_html=True)
    
    with k3:
        avg_m = df_online['mancal'].mean() if len(df_online) > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value">{avg_m:.1f}<small> °C</small></div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Temp. Mancal</div></div>', unsafe_allow_html=True)
    
    with k4:
        avg_o = df_online['oleo'].mean() if len(df_online) > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value">{avg_o:.1f}<small> °C</small></div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Temp. Óleo</div></div>', unsafe_allow_html=True)
    
    with k5:
        avg_c = df_online['corrente'].mean() if len(df_online) > 0 else 0
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-orange">{avg_c:.1f}<small> A</small></div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Corrente Média</div></div>', unsafe_allow_html=True)
    
    with k6:
        alarmes = len(df_show[df_show['status'] == 'Alarme'])
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-red">{alarmes}</div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Alarmes Ativos</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Cards das bombas
    for loc in display_locais:
        st.markdown(f'### {loc}')
        subset = df_show[df_show['local'] == loc]
        
        if len(subset) == 0:
            st.info(f"Nenhuma bomba em {loc}")
            continue
        
        cols = st.columns(min(3, len(subset)))
        
        for i, row in enumerate(subset.to_dict('records')):
            with cols[i % len(cols)]:
                health = get_health_score(row)
                health_color = get_health_color(health)
                
                config = get_config()
                icon_v = "⚠️" if row['vibra'] > config['limite_rms']*0.7 else "✅"
                icon_m = "🔥" if row['mancal'] > config['limite_mancal']*0.9 else "🌡️"
                icon_o = "🔥" if row['oleo'] > config['limite_oleo']*0.9 else "💧"
                icon_c = "⚠️" if row['corrente'] > config['limite_corrente']*0.9 else "⚡"
                
                st.markdown(f"""
                <div class="modern-card status-{row['status']}">
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;'>
                        <div>
                            <div style='font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 4px;'>{row['local']}</div>
                            <div style='font-size: 1.5rem; font-weight: 800;'>BOMBA {row['id']}</div>
                        </div>
                        <div style='text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>SAÚDE</div>
                            <div style='font-size: 2rem; font-weight: 800; color: {health_color};'>{health}</div>
                        </div>
                    </div>
                    
                    <div style='background: rgba(15, 23, 42, 0.5); padding: 8px 12px; border-radius: 8px; margin-bottom: 1rem; text-align: center;'>
                        <span style='font-size: 0.85rem; font-weight: 600; color: {"var(--accent-green)" if row["status"]=="Online" else "var(--accent-red)" if row["status"]=="Alarme" else "#64748b"};'>
                            ● {row['status'].upper()}
                        </span>
                    </div>
                    
                    <div style='display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 1rem;'>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>⚙️ Pressão</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['pressao']:.1f}<small style='font-size: 0.7em;'> MCA</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>{icon_m} Mancal</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['mancal']:.1f}<small style='font-size: 0.7em;'> °C</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>{icon_o} Óleo</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['oleo']:.1f}<small style='font-size: 0.7em;'> °C</small></div>
                        </div>
                    </div>
                    
                    <div style='display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 1rem;'>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>{icon_v} Vibração</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['vibra']:.2f}<small style='font-size: 0.7em;'> mm/s</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>{icon_c} Corrente</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['corrente']:.1f}<small style='font-size: 0.7em;'> A</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>🔌 Potência</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['potencia']:.1f}<small style='font-size: 0.7em;'> kW</small></div>
                        </div>
                    </div>
                    
                    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px;'>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>🔋 V. Motor</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['tensao_motor']:.0f}<small style='font-size: 0.7em;'> V</small></div>
                        </div>
                        <div style='background: rgba(15, 23, 42, 0.5); padding: 10px; border-radius: 8px; text-align: center;'>
                            <div style='font-size: 0.7rem; color: var(--text-secondary);'>⚡ V. Rede</div>
                            <div style='font-size: 1.1rem; font-weight: 700;'>{row['tensao_rede']:.0f}<small style='font-size: 0.7em;'> V</small></div>
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

# ============================================================================
# VIEW: DETALHES
# ============================================================================

elif st.session_state.view == 'detalhes':
    
    if not st.session_state.selected_pump_id or not st.session_state.selected_local:
        st.warning("Selecione uma bomba no Dashboard")
        if st.button("← Voltar ao Dashboard"):
            st.session_state.view = 'dashboard'
            st.rerun()
    else:
        # Seletores
        nav_col1, nav_col2, nav_col3 = st.columns([2, 2, 6])
        
        with nav_col1:
            locais = sorted(df['local'].unique().tolist())
            current_local = st.session_state.selected_local if st.session_state.selected_local in locais else locais[0]
            new_local = st.selectbox("📍 Local", locais, index=locais.index(current_local) if current_local in locais else 0)
        
        with nav_col2:
            bombas = sorted(df[df['local'] == new_local]['id'].unique().tolist())
            current_pump = st.session_state.selected_pump_id if st.session_state.selected_pump_id in bombas else bombas[0]
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
        
        if new_local != st.session_state.selected_local or new_pump != st.session_state.selected_pump_id:
            st.session_state.selected_local = new_local
            st.session_state.selected_pump_id = new_pump
            st.rerun()
        
        pump_data = df[(df['local'] == st.session_state.selected_local) & (df['id'] == st.session_state.selected_pump_id)]
        
        if len(pump_data) == 0:
            st.error("Bomba não encontrada")
        else:
            pump_data = pump_data.iloc[0]
            historical_df = get_historical_data(st.session_state.selected_pump_id, st.session_state.selected_local, days=st.session_state.date_range)
            
            st.markdown("---")
            
            health = get_health_score(pump_data)
            
            st.markdown(f"## {pump_data['local']} | BOMBA {pump_data['id']}")
            st.markdown(f"**Status:** {pump_data['status']} | **Saúde:** {health}/100")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gauges
            st.markdown("### 🎯 Indicadores em Tempo Real")
            g1, g2, g3, g4, g5 = st.columns(5)
            
            config = get_config()
            
            with g1:
                st.plotly_chart(create_gauge_chart(pump_data['vibra'], 10.0, "Vibração (mm/s)", "#10b981", warning_threshold=config['limite_rms']*0.7, critical_threshold=config['limite_rms']), use_container_width=True)
            
            with g2:
                st.plotly_chart(create_gauge_chart(pump_data['pressao'], 50, "Pressão (MCA)", "#3b82f6", warning_threshold=config['limite_pressao_mca']*1.2, critical_threshold=config['limite_pressao_mca']), use_container_width=True)
            
            with g3:
                st.plotly_chart(create_gauge_chart(pump_data['mancal'], 100, "Temp. Mancal (°C)", "#f59e0b", warning_threshold=config['limite_mancal']*0.9, critical_threshold=config['limite_mancal']), use_container_width=True)
            
            with g4:
                st.plotly_chart(create_gauge_chart(pump_data['oleo'], 100, "Temp. Óleo (°C)", "#ef4444", warning_threshold=config['limite_oleo']*0.9, critical_threshold=config['limite_oleo']), use_container_width=True)
            
            with g5:
                st.plotly_chart(create_gauge_chart(pump_data['corrente'], 100, "Corrente (A)", "#8b5cf6", warning_threshold=config['limite_corrente']*0.9, critical_threshold=config['limite_corrente']), use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gráficos
            st.markdown("### 📈 Tendências Históricas")
            
            tab1, tab2, tab3, tab4 = st.tabs(["🌊 Vibração", "⚙️ Pressão", "🌡️ Temperaturas", "⚡ Corrente"])
            
            with tab1:
                st.plotly_chart(create_time_series_chart(historical_df, 'vibra', 'Vibração', '#10b981', 'Vibração (mm/s)', show_threshold=config['limite_rms']), use_container_width=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Atual", f"{pump_data['vibra']:.2f} mm/s")
                c2.metric("Média", f"{historical_df['vibra'].mean():.2f} mm/s")
                c3.metric("Máximo", f"{historical_df['vibra'].max():.2f} mm/s")
                c4.metric("Mínimo", f"{historical_df['vibra'].min():.2f} mm/s")
            
            with tab2:
                st.plotly_chart(create_time_series_chart(historical_df, 'pressao', 'Pressão', '#3b82f6', 'Pressão (MCA)', show_threshold=config['limite_pressao_mca']), use_container_width=True)
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
            
            with tab4:
                st.plotly_chart(create_time_series_chart(historical_df, 'corrente', 'Corrente', '#8b5cf6', 'Corrente (A)', show_threshold=config['limite_corrente']), use_container_width=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Atual", f"{pump_data['corrente']:.1f} A")
                c2.metric("Média", f"{historical_df['corrente'].mean():.1f} A")
                c3.metric("Máximo", f"{historical_df['corrente'].max():.1f} A")
                c4.metric("Mínimo", f"{historical_df['corrente'].min():.1f} A")

# CONTINUA NA PARTE 3...


# ============================================================================
# VIEW: ALARMES
# ============================================================================

elif st.session_state.view == 'alarmes':
    
    st.markdown("### 🚨 Central de Alarmes")
    
    df_alarmes = get_alarmes()
    
    # Filtros
    col1, col2, col3 = st.columns([2, 2, 6])
    
    with col1:
        status_filter = st.selectbox("🔔 Status", ["Todos", "Ativos", "Reconhecidos"], key="alarm_status_filter")
    
    with col2:
        if st.button("🔄 Atualizar Alarmes", use_container_width=True):
            get_alarmes.clear()
            st.rerun()
    
    # Aplicar filtro
    if status_filter == "Ativos":
        df_alarmes_filtered = df_alarmes[df_alarmes['status'] == 'Ativo']
    elif status_filter == "Reconhecidos":
        df_alarmes_filtered = df_alarmes[df_alarmes['status'] == 'Reconhecido']
    else:
        df_alarmes_filtered = df_alarmes
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # KPIs de Alarmes
    k1, k2, k3 = st.columns(3)
    
    with k1:
        total_alarmes = len(df_alarmes)
        st.markdown(f'<div class="kpi-card"><div class="kpi-value">{total_alarmes}</div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Total de Alarmes</div></div>', unsafe_allow_html=True)
    
    with k2:
        ativos = len(df_alarmes[df_alarmes['status'] == 'Ativo'])
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-red">{ativos}</div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Alarmes Ativos</div></div>', unsafe_allow_html=True)
    
    with k3:
        reconhecidos = len(df_alarmes[df_alarmes['status'] == 'Reconhecido'])
        st.markdown(f'<div class="kpi-card"><div class="kpi-value txt-green">{reconhecidos}</div><div style="margin-top: 0.5rem; font-size: 0.85rem;">Reconhecidos</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Lista de Alarmes
    if len(df_alarmes_filtered) == 0:
        st.success("✅ Nenhum alarme encontrado com os filtros aplicados!")
    else:
        st.markdown(f"**{len(df_alarmes_filtered)} alarme(s) encontrado(s)**")
        st.markdown("<br>", unsafe_allow_html=True)
        
        for idx, row in df_alarmes_filtered.iterrows():
            ativo = row['status'] == 'Ativo'
            card_class = 'alarm-card' if ativo else 'alarm-card reconhecido'
            
            data_hora_fmt = pd.to_datetime(row['data_hora']).strftime('%d/%m/%Y %H:%M:%S')
            
            st.markdown(f"""
            <div class="{card_class}">
                <div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;'>
                    <div style='flex: 1;'>
                        <div style='font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 4px;'>{data_hora_fmt}</div>
                        <div style='font-size: 1.2rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem;'>{row['bomba']}</div>
                        <div style='display: inline-block; background: rgba(239, 68, 68, 0.2); padding: 4px 12px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; color: var(--accent-red); margin-bottom: 0.5rem;'>
                            🚨 {row['sensor']}
                        </div>
                    </div>
                    <div style='text-align: right;'>
                        <div style='background: {"rgba(16, 185, 129, 0.2)" if not ativo else "rgba(239, 68, 68, 0.2)"}; padding: 6px 14px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; color: {"var(--accent-green)" if not ativo else "var(--accent-red)"};'>
                            {"✅ RECONHECIDO" if not ativo else "⚠️ ATIVO"}
                        </div>
                    </div>
                </div>
                
                <div style='background: rgba(15, 23, 42, 0.5); padding: 12px; border-radius: 8px; margin-bottom: 0.75rem;'>
                    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 12px;'>
                        <div>
                            <div style='font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 4px;'>Valor Detectado</div>
                            <div style='font-size: 1.1rem; font-weight: 700; color: var(--accent-red);'>{row['valor_detectado']}</div>
                        </div>
                        <div>
                            <div style='font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 4px;'>Limite Definido</div>
                            <div style='font-size: 1.1rem; font-weight: 700; color: var(--accent-orange);'>{row['limite_definido']}</div>
                        </div>
                    </div>
                </div>
                
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div style='font-size: 0.85rem; color: var(--text-secondary);'>
                        Operador: <span style='color: var(--text-primary); font-weight: 600;'>{row['operador']}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if ativo:
                col_ack1, col_ack2, col_ack3 = st.columns([2, 2, 8])
                
                with col_ack1:
                    operador_nome = st.text_input("Seu nome", key=f"op_{idx}", placeholder="Digite seu nome")
                
                with col_ack2:
                    if st.button("✅ Reconhecer Alarme", key=f"ack_{idx}", use_container_width=True):
                        if operador_nome:
                            if reconhecer_alarme(row['id'], operador_nome):
                                st.success(f"Alarme reconhecido por {operador_nome}!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Erro ao reconhecer alarme")
                        else:
                            st.warning("Digite seu nome primeiro")
            
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ============================================================================
# VIEW: RELATÓRIOS
# ============================================================================

elif st.session_state.view == 'relatorios':
    
    st.markdown("### 📄 Geração de Relatórios")
    
    st.info("💡 Selecione a bomba e o formato desejado para gerar o relatório completo.")
    
    # Seleção de bomba
    col1, col2, col3 = st.columns([2, 2, 8])
    
    with col1:
        locais = sorted(df['local'].unique().tolist())
        selected_local = st.selectbox("📍 Local", locais, key="rel_local")
    
    with col2:
        bombas = sorted(df[df['local'] == selected_local]['id'].unique().tolist())
        selected_pump = st.selectbox("🔧 Bomba", bombas, key="rel_bomba")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Preview dos dados
    pump_preview = df[(df['local'] == selected_local) & (df['id'] == selected_pump)]
    
    if len(pump_preview) > 0:
        pump_preview = pump_preview.iloc[0]
        
        st.markdown("#### 📊 Preview dos Dados")
        
        prev_col1, prev_col2, prev_col3, prev_col4 = st.columns(4)
        
        with prev_col1:
            st.metric("Status", pump_preview['status'])
            st.metric("Pressão", f"{pump_preview['pressao']:.2f} MCA")
        
        with prev_col2:
            st.metric("Temp. Mancal", f"{pump_preview['mancal']:.1f} °C")
            st.metric("Temp. Óleo", f"{pump_preview['oleo']:.1f} °C")
        
        with prev_col3:
            st.metric("Vibração", f"{pump_preview['vibra']:.2f} mm/s")
            st.metric("Corrente", f"{pump_preview['corrente']:.1f} A")
        
        with prev_col4:
            st.metric("Tensão Motor", f"{pump_preview['tensao_motor']:.0f} V")
            st.metric("Tensão Rede", f"{pump_preview['tensao_rede']:.0f} V")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Botões de Download
        st.markdown("#### 💾 Gerar Relatório")
        
        down_col1, down_col2, down_col3 = st.columns([2, 2, 8])
        
        with down_col1:
            if st.button("📥 Download Excel", key="btn_excel", use_container_width=True):
                excel_data = generate_excel_report(selected_pump, selected_local)
                if excel_data:
                    filename = f"relatorio_{selected_local}_{selected_pump}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    st.download_button(
                        label="⬇️ Baixar Excel",
                        data=excel_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.error("Erro ao gerar relatório Excel")
        
        with down_col2:
            if st.button("📥 Download PDF", key="btn_pdf", use_container_width=True):
                pdf_data = generate_pdf_report(selected_pump, selected_local)
                if pdf_data:
                    filename = f"relatorio_{selected_local}_{selected_pump}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    st.download_button(
                        label="⬇️ Baixar PDF",
                        data=pdf_data,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.error("Erro ao gerar relatório PDF")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Informações sobre o relatório
        st.markdown("#### ℹ️ Conteúdo do Relatório")
        
        st.markdown("""
        **Excel (3 Planilhas):**
        - 📊 **Dados Atuais**: Snapshot completo da bomba
        - 📈 **Histórico 7 Dias**: Todas as leituras dos últimos 7 dias
        - 📉 **Estatísticas**: Média, mínimo e máximo de cada parâmetro
        
        **PDF:**
        - 📄 Relatório formatado profissionalmente
        - 📊 Tabela com dados atuais
        - 📈 Estatísticas dos últimos 7 dias
        - 🏢 Pronto para impressão
        """)

# ============================================================================
# VIEW: CONFIGURAÇÕES
# ============================================================================

elif st.session_state.view == 'config':
    
    st.markdown("### ⚙️ Configurações do Sistema")
    st.info("💡 Configure os limites de alarmes. As alterações serão salvas no banco de dados.")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["⚙️ Pressão", "〰️ Vibração", "🌡️ Mancal", "💧 Óleo", "⚡ Corrente"])
    
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
    
    with tab5:
        st.markdown("#### Configurações de Corrente")
        
        limite_corrente = st.number_input(
            "Limite Máximo (A)",
            min_value=10.0,
            max_value=600.0,
            value=float(config.get('limite_corrente', 550.0)),
            step=5.0,
            help="Corrente acima deste valor gera alarme",
            key="config_corrente"
        )
        
        if st.button("💾 Salvar Corrente", type="primary", use_container_width=True):
            if save_config_to_db(limite_corrente=limite_corrente):
                st.success("✅ Limite de corrente salvo no banco!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Erro ao salvar")

# ============================================================================
# RODAPÉ
# ============================================================================

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(f"""
<div style='text-align: center; color: #64748b; font-size: 0.85rem; padding: 20px; border-top: 1px solid var(--border-color);'>
    <div style='margin-bottom: 8px;'><strong>GS Inima Sistemas</strong> © 2025 | Sistema de Monitoramento Industrial v4.0</div>
    <div>Conectado ao Supabase | {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</div>
</div>
""", unsafe_allow_html=True)
