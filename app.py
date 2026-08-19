



import io
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
from supabase import create_client

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="AXION | Monitoramento Industrial",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

REFRESH_SECONDS = 30
OFFLINE_AFTER_SECONDS = 120
MCA_PER_BAR = 10.197


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
        return create_client(url, key)
    except Exception as exc:
        st.error(f"Não foi possível conectar ao Supabase: {exc}")
        return None


supabase = init_supabase()


# ============================================================
# ESTADO
# ============================================================

if "view" not in st.session_state:
    st.session_state.view = "dashboard"

if "device_id" not in st.session_state:
    st.session_state.device_id = None

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now().timestamp()


# ============================================================
# AUTO REFRESH REAL
# ============================================================

if AUTOREFRESH_AVAILABLE:
    st_autorefresh(
        interval=REFRESH_SECONDS * 1000,
        limit=None,
        key="axion_auto_refresh",
    )
else:
    st.warning(
        "Atualização automática indisponível: instale "
        "`streamlit-autorefresh` no ambiente do dashboard."
    )


# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
    <style>
        :root {
            --bg: #0b1020;
            --card: #1d2740;
            --card2: #162038;
            --border: #475569;
            --border-strong: #64748b;
            --text: #f8fafc;
            --text-strong: #ffffff;
            --muted: #d1d5db;
            --muted-strong: #e2e8f0;
            --blue: #1d4ed8;
            --blue-dark: #1e3a8a;
            --green: #047857;
            --green-bg: #d1fae5;
            --yellow: #b45309;
            --yellow-bg: #fef3c7;
            --red: #b91c1c;
            --red-bg: #fee2e2;
            --cyan: #0369a1;
        }

        * {
            box-sizing: border-box;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(59,130,246,.12), transparent 35%),
                linear-gradient(135deg, #0b1020 0%, #070b14 100%);
            color: var(--text);
        }

        body,
        .stApp,
        .stMarkdown,
        p,
        label,
        span,
        div {
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
        }

        .block-container {
            max-width: 1600px;
            padding-top: 1rem;
            padding-bottom: 2rem;
        }

        /* ---------------- Buttons ---------------- */

        div.stButton > button {
            width: 100%;
            min-height: 46px;
            border-radius: 10px;
            border: 1px solid #64748b;
            background: #1e293b;
            color: #f8fafc;
            font-weight: 750;
            font-size: 0.95rem;
            box-shadow: 0 2px 7px rgba(15,23,42,.08);
        }

        div.stButton > button:hover {
            border-color: #60a5fa;
            background: #263650;
            color: #ffffff;
        }

        div.stButton > button:focus {
            border-color: #60a5fa;
            box-shadow: 0 0 0 3px rgba(59,130,246,.25);
            color: #ffffff;
        }

        div.stButton > button[kind="primary"] {
            background: #2563eb;
            border-color: #1d4ed8;
            color: #ffffff;
        }

        div.stButton > button[kind="primary"]:hover {
            background: #1d4ed8;
            border-color: #1e40af;
            color: #ffffff;
        }

        div.stButton > button p {
            color: inherit !important;
            font-weight: 750 !important;
        }

        /* ---------------- Header / cards ---------------- */

        .top-card {
            background: linear-gradient(135deg, #1d2740 0%, #151d31 100%);
            border: 1px solid #475569;
            border-radius: 18px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 7px 22px rgba(15,23,42,.06);
        }

        .device-card {
            background: linear-gradient(135deg, #1e293b 0%, #172033 100%);
            border: 1px solid #475569;
            border-radius: 16px;
            padding: 1rem;
            min-height: 360px;
            box-shadow: 0 7px 20px rgba(15,23,42,.07);
        }

        .device-card:hover {
            border-color: #60a5fa;
            box-shadow: 0 9px 24px rgba(37,99,235,.10);
        }

        .metric {
            background: rgba(15,23,42,.52);
            border: 1px solid rgba(148,163,184,.24);
            border-radius: 10px;
            padding: .7rem;
            min-height: 74px;
        }

        .metric-title {
            color: #e2e8f0;
            font-size: .74rem;
            text-transform: uppercase;
            letter-spacing: .35px;
            font-weight: 700;
        }

        .metric-value {
            color: #ffffff;
            font-size: 1.2rem;
            font-weight: 850;
            margin-top: .25rem;
        }

        .location-title {
            margin-top: 1rem;
            margin-bottom: .6rem;
            font-size: 1.1rem;
            font-weight: 850;
            color: #f8fafc;
        }

        .kpi {
            background: #1e293b;
            border: 1px solid #475569;
            border-radius: 14px;
            padding: 1rem;
            text-align: center;
            box-shadow: 0 4px 14px rgba(15,23,42,.05);
        }

        .kpi-value {
            font-size: 1.95rem;
            font-weight: 900;
            line-height: 1.1;
            color: #ffffff;
        }

        .muted {
            color: #cbd5e1 !important;
            font-size: .84rem;
            font-weight: 500;
        }

        .small {
            color: #cbd5e1 !important;
            font-size: .76rem;
            font-weight: 700;
        }

        /* ---------------- Status ---------------- */

        .pill-online {
            display: inline-block;
            padding: .32rem .62rem;
            border-radius: 999px;
            background: rgba(16,185,129,.16);
            color: #34d399;
            border: 1px solid rgba(16,185,129,.35);
            font-weight: 800;
            font-size: .74rem;
        }

        .pill-offline {
            display: inline-block;
            padding: .32rem .62rem;
            border-radius: 999px;
            background: rgba(100,116,139,.16);
            color: #e2e8f0;
            border: 1px solid rgba(148,163,184,.32);
            font-weight: 800;
            font-size: .74rem;
        }

        .pill-alarm {
            display: inline-block;
            padding: .32rem .62rem;
            border-radius: 999px;
            background: rgba(239,68,68,.16);
            color: #f87171;
            border: 1px solid rgba(239,68,68,.35);
            font-weight: 850;
            font-size: .74rem;
        }

        /* ---------------- Streamlit native text / inputs ---------------- */

        [data-testid="stHeader"] {
            display: none;
        }

        [data-testid="stMetricLabel"] {
            color: #e2e8f0 !important;
            font-weight: 750 !important;
        }

        [data-testid="stMetricValue"] {
            color: #ffffff !important;
            font-weight: 900 !important;
        }

        [data-testid="stMetricDelta"] {
            color: #cbd5e1 !important;
            font-weight: 700 !important;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        textarea,
        input {
            background: #162038 !important;
            color: #f8fafc !important;
            border-color: #64748b !important;
        }

        div[data-baseweb="select"] span,
        div[data-baseweb="select"] input {
            color: #f8fafc !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid #475569;
            border-radius: 12px;
            background: #162038;
        }

        [data-testid="stExpander"] summary {
            color: #f8fafc !important;
            font-weight: 750 !important;
        }


        /* ---------------- Configuration forms ---------------- */

        [data-testid="stForm"] {
            color: #f8fafc !important;
        }

        [data-testid="stForm"] label,
        [data-testid="stForm"] label p,
        [data-testid="stForm"] label span {
            color: #e2e8f0 !important;
            font-weight: 700 !important;
        }

        [data-testid="stForm"] input,
        [data-testid="stForm"] textarea {
            color: #ffffff !important;
            background: #162038 !important;
            -webkit-text-fill-color: #ffffff !important;
            border-color: #94a3b8 !important;
            opacity: 1 !important;
        }

        [data-testid="stForm"] input::placeholder,
        [data-testid="stForm"] textarea::placeholder {
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
            opacity: 1 !important;
        }

        /* Campos somente leitura / desabilitados */
        [data-testid="stForm"] input:disabled,
        [data-testid="stForm"] textarea:disabled {
            color: #cbd5e1 !important;
            -webkit-text-fill-color: #cbd5e1 !important;
            background: #111a2e !important;
            border-color: #64748b !important;
            opacity: 1 !important;
        }

        [data-testid="stForm"] [data-baseweb="select"] > div {
            background: #162038 !important;
            border-color: #94a3b8 !important;
        }

        [data-testid="stForm"] [data-baseweb="select"] span,
        [data-testid="stForm"] [data-baseweb="select"] input {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        [data-testid="stForm"] [data-testid="stCheckbox"] label,
        [data-testid="stForm"] [data-testid="stCheckbox"] label p {
            color: #f8fafc !important;
            font-weight: 750 !important;
        }

        [data-testid="stForm"] button {
            color: #ffffff !important;
            background: #2563eb !important;
            border-color: #3b82f6 !important;
        }

        [data-testid="stForm"] button:hover {
            background: #1d4ed8 !important;
            border-color: #60a5fa !important;
        }

        /* Títulos/descrições dentro da configuração */
        [data-testid="stExpander"] p,
        [data-testid="stExpander"] small {
            color: #cbd5e1 !important;
        }

        /* ---------------- Responsive / mobile ---------------- */

        @media (max-width: 900px) {
            .block-container {
                padding: .65rem .65rem 1.25rem .65rem;
            }

            .top-card {
                padding: 1rem;
                border-radius: 14px;
            }

            .top-card div[style*="font-size:2rem"] {
                font-size: 1.45rem !important;
            }

            .device-card {
                min-height: 0;
                padding: .85rem;
                border-radius: 14px;
            }

            .location-title {
                font-size: 1rem;
                margin-top: .75rem;
            }

            .metric-value,
            [data-testid="stMetricValue"] {
                font-size: 1.08rem !important;
            }

            [data-testid="stMetricLabel"] {
                font-size: .78rem !important;
            }

            .kpi-value {
                font-size: 1.6rem;
            }

            div.stButton > button {
                min-height: 48px;
                font-size: .92rem;
            }
        }

        @media (min-width: 901px) {
            [data-testid="stMetricValue"] {
                font-size: 1.35rem !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# AUXILIARES
# ============================================================

def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default
        value = float(value)
        return value if np.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def format_value(value, decimals=2, unit=""):
    value = safe_float(value)
    if not np.isfinite(value):
        return "—"
    return f"{value:.{decimals}f}{(' ' + unit) if unit else ''}"


def bar_to_mca(value):
    value = safe_float(value)
    return value * MCA_PER_BAR if np.isfinite(value) else np.nan


def latest_age_seconds(recebido_em):
    try:
        ts = pd.to_datetime(recebido_em, utc=True)
        now = pd.Timestamp.now(tz="UTC")
        return max(0, (now - ts).total_seconds())
    except Exception:
        return float("inf")



def channel_prefix(canal):
    return str(canal).lower()


def channel_field(canal):
    return channel_prefix(canal)


def channel_display_name(config, canal):
    if not config:
        return canal

    return (
        config.get("nome_exibicao")
        or config.get("nome")
        or config.get("descricao")
        or canal
    )


def channel_unit(config, default=""):
    if not config:
        return default

    return config.get("unidade") or default


def raw_to_voltage(raw, full_scale_v=4.096):
    raw = safe_float(raw)
    full_scale_v = safe_float(full_scale_v, 4.096)

    if not np.isfinite(raw) or not np.isfinite(full_scale_v):
        return np.nan

    # ADS1115 configured as signed 16-bit full scale.
    return (raw / 32767.0) * full_scale_v


def linear_map(value, source_min, source_max, eng_min, eng_max):
    value = safe_float(value)
    source_min = safe_float(source_min)
    source_max = safe_float(source_max)
    eng_min = safe_float(eng_min)
    eng_max = safe_float(eng_max)

    if not all(np.isfinite(v) for v in [
        value, source_min, source_max, eng_min, eng_max
    ]):
        return np.nan

    if source_max == source_min:
        return np.nan

    return eng_min + (
        (value - source_min)
        * (eng_max - eng_min)
        / (source_max - source_min)
    )


def convert_channel_value(raw, config, full_scale_v=4.096):
    """
    Converte o RAW de uma AI conforme public.configuracao_analogica.

    Modos:
      raw_voltage     -> volts
      linear_raw      -> mapeia RAW diretamente
      linear_voltage  -> RAW -> volts -> escala de engenharia
      linear_4_20mA   -> RAW -> volts -> mA (via shunt) -> escala de engenharia
      disabled        -> NaN
    """
    if not config:
        return raw_to_voltage(raw, full_scale_v)

    modo = str(config.get("modo") or "raw_voltage").lower()

    if modo == "disabled":
        return np.nan

    if modo == "raw_voltage":
        return raw_to_voltage(raw, full_scale_v)

    if modo == "linear_raw":
        return linear_map(
            raw,
            config.get("source_min", 0),
            config.get("source_max", 32767),
            config.get("eng_min", 0),
            config.get("eng_max", 100),
        )

    voltage = raw_to_voltage(raw, full_scale_v)

    if modo == "linear_voltage":
        return linear_map(
            voltage,
            0.0,
            3.0,
            config.get("eng_min", 0),
            config.get("eng_max", 100),
        )

    if modo == "linear_4_20ma":
        shunt = safe_float(config.get("shunt_ohms"), 150.0)
        if not np.isfinite(shunt) or shunt <= 0:
            return np.nan

        current_ma = (voltage / shunt) * 1000.0

        return linear_map(
            current_ma,
            4.0,
            20.0,
            config.get("eng_min", 0),
            config.get("eng_max", 100),
        )

    # Compatibilidade com qualquer modo desconhecido.
    return raw_to_voltage(raw, full_scale_v)


def get_channel_config(configs, device_id, canal):
    return configs.get(
        (str(device_id), str(canal).upper()),
        {}
    )


def get_channel_value(row, configs, device_id, canal, full_scale_v=4.096):
    cfg = get_channel_config(configs, device_id, canal)
    raw = row.get(channel_field(canal))
    return convert_channel_value(raw, cfg, full_scale_v)


def get_default_config():
    return {
        "limite_pressao": 2.0,
        "limite_mancal": 75.0,
        "limite_oleo": 80.0,
        "limite_rms": 5.0,
    }


# ============================================================
# CONFIGURAÇÕES DO BANCO
# ============================================================

@st.cache_data(ttl=30)
def load_devices():
    """
    Carrega public.dispositivos usando o schema atual.

    Campos principais:
      device_id
      nome_exibicao
      local
      descricao
      ativo
      ordem
      adc_full_scale_v
    """
    empty = pd.DataFrame(columns=[
        "device_id",
        "nome_exibicao",
        "nome",
        "local",
        "descricao",
        "ativo",
        "ordem",
        "adc_full_scale_v",
    ])

    if supabase is None:
        return empty

    try:
        response = (
            supabase
            .table("dispositivos")
            .select("*")
            .execute()
        )

        data = response.data or []
        if not data:
            return empty

        df = pd.DataFrame(data)

        if "device_id" not in df.columns:
            return empty

        defaults = {
            "nome_exibicao": None,
            "nome": None,
            "local": "Sem local",
            "descricao": None,
            "ativo": True,
            "ordem": 999,
            "adc_full_scale_v": 4.096,
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        df["nome_exibicao"] = (
            df["nome_exibicao"]
            .fillna(df["nome"])
            .fillna(df["device_id"])
            .astype(str)
            .str.strip()
        )

        df["nome"] = df["nome_exibicao"]

        df["local"] = (
            df["local"]
            .fillna("Sem local")
            .astype(str)
            .str.strip()
        )

        df.loc[df["local"] == "", "local"] = "Sem local"

        df["descricao"] = df["descricao"].where(
            df["descricao"].notna(), None
        )

        df["ativo"] = (
            df["ativo"]
            .fillna(True)
            .astype(bool)
        )

        df["ordem"] = pd.to_numeric(
            df["ordem"],
            errors="coerce"
        ).fillna(999)

        df["adc_full_scale_v"] = pd.to_numeric(
            df["adc_full_scale_v"],
            errors="coerce"
        ).fillna(4.096)

        return df

    except Exception as exc:
        st.error(f"Erro ao carregar dispositivos: {exc}")
        return empty


@st.cache_data(ttl=30)
def load_channel_configs():
    """
    Carrega a configuração atual de public.configuracao_analogica.

    Normaliza o nome da coluna para manter compatibilidade com partes
    antigas do dashboard.
    """
    if supabase is None:
        return {}

    try:
        response = (
            supabase
            .table("configuracao_analogica")
            .select("*")
            .execute()
        )

        configs = {}

        for row in response.data or []:
            canal_num = row.get("canal")

            try:
                canal = f"AI{int(canal_num):03d}"
            except (TypeError, ValueError):
                canal = str(
                    row.get("canal", "")
                ).upper()

            normalized = dict(row)

            normalized["nome_exibicao"] = (
                row.get("nome_exibicao")
                or row.get("nome")
                or canal
            )

            normalized["unidade"] = (
                row.get("unidade")
                or ""
            )

            configs[(
                str(row.get("device_id", "")),
                canal
            )] = normalized

        return configs

    except Exception as exc:
        st.error(
            f"Erro ao carregar configuração das entradas: {exc}"
        )
        return {}


@st.cache_data(ttl=30)
def load_global_config():
    config = get_default_config()

    if supabase is None:
        return config

    try:
        response = (
            supabase
            .table("configuracoes")
            .select("*")
            .eq("id", 1)
            .limit(1)
            .execute()
        )

        if response.data:
            config.update(response.data[0])

    except Exception:
        pass

    return config


# ============================================================
# TELEMETRIA
# ============================================================

@st.cache_data(ttl=10)
def load_telemetry():
    columns = [
        "device_id",
        "timestamp_dispositivo",
        "recebido_em",
        "ai001", "ai002", "ai003", "ai004",
        "ai005", "ai006", "ai007", "ai008",
        "x_mm_s", "x_rms",
        "y_mm_s", "y_rms",
        "z_mm_s", "z_rms",
    ]

    if supabase is None:
        return pd.DataFrame(columns=columns + ["status"])

    try:
        response = (
            supabase
            .table("telemetria")
            .select("*")
            .order("recebido_em", desc=True)
            .limit(1000)
            .execute()
        )

        data = response.data or []
        if not data:
            return pd.DataFrame(columns=columns + ["status"])

        df = pd.DataFrame(data)

        for col in columns:
            if col not in df.columns:
                df[col] = np.nan

        df["recebido_em"] = pd.to_datetime(
            df["recebido_em"],
            utc=True,
            errors="coerce",
        )

        # Última leitura por dispositivo para o dashboard.
        df = (
            df.sort_values("recebido_em", ascending=False)
            .drop_duplicates("device_id", keep="first")
            .reset_index(drop=True)
        )

        global_config = load_global_config()
        channel_configs = load_channel_configs()

        def row_status(row):
            age = latest_age_seconds(row.get("recebido_em"))
            if age > OFFLINE_AFTER_SECONDS:
                return "Offline"

            device_id = str(row.get("device_id", ""))
            device_cfg = load_devices()
            full_scale = 4.096

            if not device_cfg.empty:
                selected_device = device_cfg[
                    device_cfg["device_id"].astype(str) == device_id
                ]
                if not selected_device.empty:
                    full_scale = safe_float(
                        selected_device.iloc[0].get("adc_full_scale_v"),
                        4.096
                    )

            # Alarmes por canal, quando configurados.
            for canal in range(1, 17):
                canal_name = f"AI{canal:03d}"
                cfg = get_channel_config(
                    channel_configs,
                    device_id,
                    canal_name
                )

                if not cfg or not bool(cfg.get("ativo", True)):
                    continue

                value = get_channel_value(
                    row,
                    channel_configs,
                    device_id,
                    canal_name,
                    full_scale
                )

                if not np.isfinite(value):
                    continue

                alarm_min = safe_float(cfg.get("alarme_min"))
                alarm_max = safe_float(cfg.get("alarme_max"))

                if np.isfinite(alarm_min) and value < alarm_min:
                    return "Alarme"

                if np.isfinite(alarm_max) and value > alarm_max:
                    return "Alarme"

            # Compatibilidade com os limites globais de vibração.
            vibration = [
                safe_float(row.get("x_mm_s")),
                safe_float(row.get("y_mm_s")),
                safe_float(row.get("z_mm_s")),
            ]
            vibration = [
                v for v in vibration
                if np.isfinite(v)
            ]

            v_limit = safe_float(
                global_config.get("limite_rms")
            )

            if (
                vibration
                and np.isfinite(v_limit)
                and max(vibration) > v_limit
            ):
                return "Alarme"

            return "Online"

        df["status"] = df.apply(
            row_status,
            axis=1
        )

        return df

    except Exception as exc:
        st.error("Erro ao carregar a telemetria.")
        st.exception(exc)
        return pd.DataFrame(columns=columns + ["status"])


def build_devices_view():
    """
    Une dispositivos com a última telemetria.
    O cadastro do dispositivo é a fonte oficial de nome/local.
    """
    devices = load_devices()
    telemetry = load_telemetry()

    if devices.empty:
        if telemetry.empty:
            return pd.DataFrame()

        result = telemetry.copy()
        result["nome"] = result["device_id"].astype(str)
        result["local"] = "Sem cadastro"
        result["descricao"] = None
        result["ordem"] = 999
        result["ativo"] = True
        result["adc_full_scale_v"] = 4.096
        return result

    devices = devices[
        devices["ativo"] == True
    ].copy()

    if telemetry.empty:
        result = devices.copy()
        result["status"] = "Offline"
        return result

    result = devices.merge(
        telemetry,
        on="device_id",
        how="left",
        suffixes=("_device", ""),
    )

    # Campos do cadastro são prioritários.
    result["nome"] = (
        result["nome_exibicao"]
        if "nome_exibicao" in result.columns
        else result["device_id"]
    )

    result["nome"] = (
        result["nome"]
        .fillna(result["device_id"])
        .astype(str)
    )

    if "local" in result.columns:
        result["local"] = (
            result["local"]
            .fillna("Sem local")
            .astype(str)
        )
        result.loc[
            result["local"].str.strip() == "",
            "local"
        ] = "Sem local"
    else:
        result["local"] = "Sem local"

    result["descricao"] = (
        result["descricao_device"]
        if "descricao_device" in result.columns
        else None
    )

    result["ordem"] = (
        result["ordem_device"].fillna(999)
        if "ordem_device" in result.columns
        else 999
    )

    result["adc_full_scale_v"] = pd.to_numeric(
        result.get("adc_full_scale_v", 4.096),
        errors="coerce"
    ).fillna(4.096)

    result["status"] = (
        result["status"]
        .fillna("Offline")
    )

    return result


@st.cache_data(ttl=30)
def load_history(device_id, days):
    if supabase is None or not device_id:
        return pd.DataFrame()

    start = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        response = (
            supabase
            .table("telemetria")
            .select("*")
            .eq("device_id", device_id)
            .gte("recebido_em", start.isoformat())
            .order("recebido_em", desc=False)
            .execute()
        )

        data = response.data or []
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        df["timestamp"] = pd.to_datetime(
            df["recebido_em"], utc=True, errors="coerce"
        )

        numeric_cols = [
            "ai001", "ai002", "ai003", "ai004",
            "ai005", "ai006", "ai007", "ai008",
            "x_mm_s",
            "y_mm_s",
            "z_mm_s",
            "x_rms",
            "y_rms",
            "z_rms",
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

        configs = load_channel_configs()
        device_cfg = load_devices()
        full_scale = 4.096

        if not device_cfg.empty:
            match = device_cfg[
                device_cfg["device_id"].astype(str)
                == str(device_id)
            ]
            if not match.empty:
                full_scale = safe_float(
                    match.iloc[0].get("adc_full_scale_v"),
                    4.096
                )

        df["pressao"] = df.apply(
            lambda r: get_channel_value(
                r,
                configs,
                str(device_id),
                "AI004",
                full_scale
            ),
            axis=1
        )

        pressure_cfg = get_channel_config(
            configs,
            str(device_id),
            "AI004"
        )

        if str(
            pressure_cfg.get("unidade", "")
        ).lower() == "bar":
            df["pressao_mca"] = df["pressao"].apply(
                bar_to_mca
            )
        else:
            df["pressao_mca"] = np.nan

        for canal in ["AI006", "AI007", "AI008"]:
            df[canal] = df.apply(
                lambda r, c=canal: get_channel_value(
                    r,
                    configs,
                    str(device_id),
                    c,
                    full_scale
                ),
                axis=1
            )

        df["vibra"] = df[
            ["x_mm_s", "y_mm_s", "z_mm_s"]
        ].max(
            axis=1,
            skipna=True,
        )

        return df

    except Exception as exc:
        st.error("Erro ao carregar histórico.")
        st.exception(exc)
        return pd.DataFrame()


# ============================================================
# ALARMES
# ============================================================

def build_alarms(df):
    alarms = []

    if df.empty:
        return pd.DataFrame()

    configs = load_channel_configs()
    devices = load_devices()
    global_config = load_global_config()

    for _, row in df.iterrows():
        device_id = str(
            row.get("device_id", "—")
        )
        when = row.get("recebido_em")

        full_scale = 4.096
        if not devices.empty:
            match = devices[
                devices["device_id"].astype(str) == device_id
            ]
            if not match.empty:
                full_scale = safe_float(
                    match.iloc[0].get("adc_full_scale_v"),
                    4.096
                )

        # Alarmes configurados das AI.
        for canal_num in range(1, 17):
            canal = f"AI{canal_num:03d}"
            cfg = get_channel_config(
                configs,
                device_id,
                canal
            )

            if not cfg or not bool(cfg.get("ativo", True)):
                continue

            value = get_channel_value(
                row,
                configs,
                device_id,
                canal,
                full_scale
            )

            if not np.isfinite(value):
                continue

            alarm_min = safe_float(cfg.get("alarme_min"))
            alarm_max = safe_float(cfg.get("alarme_max"))

            label = channel_display_name(
                cfg,
                canal
            )
            unit = channel_unit(
                cfg,
                ""
            )

            if np.isfinite(alarm_min) and value < alarm_min:
                alarms.append({
                    "Equipamento": device_id,
                    "Grandeza": label,
                    "Valor": value,
                    "Limite": alarm_min,
                    "Unidade": unit,
                    "Data/Hora": when,
                })

            if np.isfinite(alarm_max) and value > alarm_max:
                alarms.append({
                    "Equipamento": device_id,
                    "Grandeza": label,
                    "Valor": value,
                    "Limite": alarm_max,
                    "Unidade": unit,
                    "Data/Hora": when,
                })

        # Vibração.
        v_limit = safe_float(
            global_config.get("limite_rms")
        )

        for axis in ["x", "y", "z"]:
            value = safe_float(
                row.get(f"{axis}_mm_s")
            )

            if (
                np.isfinite(value)
                and np.isfinite(v_limit)
                and value > v_limit
            ):
                alarms.append({
                    "Equipamento": device_id,
                    "Grandeza": f"Vibração {axis.upper()}",
                    "Valor": value,
                    "Limite": v_limit,
                    "Unidade": "mm/s RMS",
                    "Data/Hora": when,
                })

    return pd.DataFrame(alarms)


# ============================================================
# GRÁFICOS
# ============================================================

def line_chart(df, columns, labels, title, yaxis):
    fig = go.Figure()

    for col, label in zip(columns, labels):
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[col],
                    mode="lines",
                    name=label,
                    line={"width": 2},
                    connectgaps=False,
                )
            )

    fig.update_layout(
        title=title,
        height=320,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,.35)",
        font={"color": "#e2e8f0"},
        xaxis={"showgrid": True, "gridcolor": "rgba(148,163,184,.12)"},
        yaxis={
            "title": yaxis,
            "showgrid": True,
            "gridcolor": "rgba(148,163,184,.12)",
        },
        hovermode="x unified",
        legend={"orientation": "h"},
    )

    return fig


def health_score(row):
    if row.get("status") == "Offline":
        return 0

    score = 100
    configs = load_channel_configs()
    devices = load_devices()
    global_config = load_global_config()

    device_id = str(
        row.get("device_id", "")
    )

    full_scale = 4.096
    if not devices.empty:
        match = devices[
            devices["device_id"].astype(str) == device_id
        ]
        if not match.empty:
            full_scale = safe_float(
                match.iloc[0].get("adc_full_scale_v"),
                4.096
            )

    # Alarmes das entradas configuradas.
    for canal_num in range(1, 17):
        canal = f"AI{canal_num:03d}"
        cfg = get_channel_config(
            configs,
            device_id,
            canal
        )

        if not cfg or not bool(cfg.get("ativo", True)):
            continue

        value = get_channel_value(
            row,
            configs,
            device_id,
            canal,
            full_scale
        )

        if not np.isfinite(value):
            continue

        alarm_min = safe_float(cfg.get("alarme_min"))
        alarm_max = safe_float(cfg.get("alarme_max"))

        if np.isfinite(alarm_max):
            if value > alarm_max:
                score -= 20
            elif value > alarm_max * 0.9:
                score -= 10

        if np.isfinite(alarm_min) and value < alarm_min:
            score -= 20

    vibration = [
        safe_float(row.get(f"{a}_mm_s"))
        for a in ["x", "y", "z"]
    ]
    vibration = [
        v for v in vibration
        if np.isfinite(v)
    ]

    vib_limit = safe_float(
        global_config.get("limite_rms")
    )

    if vibration and np.isfinite(vib_limit):
        peak = max(vibration)

        if peak > vib_limit:
            score -= 35
        elif peak > vib_limit * 0.7:
            score -= 15

    return int(
        max(0, min(100, score))
    )


def health_color(score):
    if score >= 80:
        return "#10b981"
    if score >= 60:
        return "#f59e0b"
    return "#ef4444"


# ============================================================
# ATUALIZAÇÃO DE CONFIGURAÇÃO
# ============================================================

def update_channel(device_id, canal, payload):
    if supabase is None:
        return False, "Supabase indisponível."

    try:
        (
            supabase
            .table("configuracao_analogica")
            .update(payload)
            .eq("device_id", device_id)
            .eq("canal", canal)
            .execute()
        )

        load_channel_configs.clear()
        return True, None

    except Exception as exc:
        return False, str(exc)


def update_device(device_id, payload):
    if supabase is None:
        return False, "Supabase indisponível."

    try:
        (
            supabase
            .table("dispositivos")
            .update(payload)
            .eq("device_id", device_id)
            .execute()
        )

        load_devices.clear()
        return True, None

    except Exception as exc:
        return False, str(exc)


# ============================================================
# RELATÓRIO PDF
# ============================================================

def generate_pdf(device_id, row, history):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph(
            f"<b>Relatório AXION — {device_id}</b>",
            styles["Title"],
        )
    )
    story.append(Spacer(1, 0.25 * inch))

    channel_configs = load_channel_configs()
    devices = load_devices()

    full_scale = 4.096
    if not devices.empty:
        match = devices[
            devices["device_id"].astype(str) == str(device_id)
        ]
        if not match.empty:
            full_scale = safe_float(
                match.iloc[0].get("adc_full_scale_v"),
                4.096
            )

    pressure_cfg = get_channel_config(
        channel_configs,
        str(device_id),
        "AI004"
    )

    pressure = get_channel_value(
        row,
        channel_configs,
        str(device_id),
        "AI004",
        full_scale
    )

    pressure_unit = channel_unit(
        pressure_cfg,
        ""
    )

    pressure_mca = (
        bar_to_mca(pressure)
        if pressure_unit.lower() == "bar"
        else np.nan
    )

    data = [
        ["Parâmetro", "Valor"],
        ["Status", str(row.get("status", "—"))],
        ["Pressão", format_value(pressure, 2, pressure_unit)],
        ["Pressão", format_value(pressure_mca, 2, "MCA") if np.isfinite(pressure_mca) else "—"],
        ["AI006", format_value(
            get_channel_value(row, channel_configs, device_id, "AI006", full_scale),
            2,
            channel_unit(get_channel_config(channel_configs, device_id, "AI006"), "")
        )],
        ["AI007", format_value(
            get_channel_value(row, channel_configs, device_id, "AI007", full_scale),
            2,
            channel_unit(get_channel_config(channel_configs, device_id, "AI007"), "")
        )],
        ["AI008", format_value(
            get_channel_value(row, channel_configs, device_id, "AI008", full_scale),
            2,
            channel_unit(get_channel_config(channel_configs, device_id, "AI008"), "")
        )],
        ["Vibração X", format_value(row.get("x_mm_s"), 3, "mm/s RMS")],
        ["Vibração Y", format_value(row.get("y_mm_s"), 3, "mm/s RMS")],
        ["Vibração Z", format_value(row.get("z_mm_s"), 3, "mm/s RMS")],
        ["RMS X", format_value(row.get("x_rms"), 5, "g RMS")],
        ["RMS Y", format_value(row.get("y_rms"), 5, "g RMS")],
        ["RMS Z", format_value(row.get("z_rms"), 5, "g RMS")],
    ]

    table = Table(data, colWidths=[3 * inch, 3 * inch])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ])
    )
    story.append(table)
    story.append(Spacer(1, 0.3 * inch))

    if not history.empty:
        summary = [
            ["Métrica", "Média", "Mínimo", "Máximo"],
            [
                "Pressão (MCA)",
                f"{history['pressao_mca'].mean():.2f}",
                f"{history['pressao_mca'].min():.2f}",
                f"{history['pressao_mca'].max():.2f}",
            ],
            [
                "Vibração (mm/s RMS)",
                f"{history['vibra'].mean():.3f}",
                f"{history['vibra'].min():.3f}",
                f"{history['vibra'].max():.3f}",
            ],
        ]

        table2 = Table(summary)
        table2.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ])
        )
        story.append(table2)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ============================================================
# NAVEGAÇÃO
# ============================================================

top = st.columns([2, 1, 1, 1])

with top[0]:
    st.markdown(
        """
        <div class="top-card">
            <div style="font-size:2rem;font-weight:850;">
                AXION <span style="color:#3b82f6;">| Monitoramento Industrial</span>
            </div>
            <div class="muted">Telemetria via HTTPS → Supabase • Atualização automática: 30 s</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with top[1]:
    if st.button(
        "🏠  Dashboard",
        use_container_width=True,
        type="primary" if st.session_state.view == "dashboard" else "secondary",
    ):
        st.session_state.view = "dashboard"
        st.rerun()

with top[2]:
    if st.button(
        "📊  Detalhes",
        use_container_width=True,
        type="primary" if st.session_state.view == "details" else "secondary",
    ):
        st.session_state.view = "details"
        st.rerun()

with top[3]:
    if st.button(
        "⚙️  Configuração",
        use_container_width=True,
        type="primary" if st.session_state.view == "config" else "secondary",
    ):
        st.session_state.view = "config"
        st.rerun()

st.caption(
    f"Atualização automática a cada {REFRESH_SECONDS}s • "
    f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
)


# ============================================================
# DADOS ATUAIS
# ============================================================

device_rows = build_devices_view()
channel_configs = load_channel_configs()


# ============================================================
# DASHBOARD
# ============================================================

if st.session_state.view == "dashboard":

    st.markdown("## Bombas")

    if device_rows.empty:
        st.info(
            "Nenhum dispositivo cadastrado. "
            "Quando cadastrarmos as bombas em 'Configuração', "
            "elas aparecerão aqui automaticamente."
        )
    else:
        total = len(device_rows)
        online = int((device_rows["status"] == "Online").sum())
        alarms = int((device_rows["status"] == "Alarme").sum())

        k1, k2, k3 = st.columns(3)

        with k1:
            st.markdown(
                f"""
                <div class="kpi">
                    <div class="small">DISPOSITIVOS</div>
                    <div class="kpi-value">{total}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with k2:
            st.markdown(
                f"""
                <div class="kpi">
                    <div class="small">ONLINE</div>
                    <div class="kpi-value" style="color:#10b981;">{online}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with k3:
            st.markdown(
                f"""
                <div class="kpi">
                    <div class="small">ALARMES</div>
                    <div class="kpi-value" style="color:#ef4444;">{alarms}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        locations = (
            device_rows["local"]
            .fillna("Sem local")
            .astype(str)
            .replace("", "Sem local")
            .unique()
            .tolist()
        )

        locations = sorted(
            locations,
            key=lambda x: str(x).lower()
        )

        for location in locations:
            subset = (
                device_rows[
                    device_rows["local"].astype(str) == str(location)
                ]
                .sort_values(["ordem", "nome"])
            )

            st.markdown(
                f"<div class='location-title'>LOCAL: {location}</div>",
                unsafe_allow_html=True,
            )

            # 3 cards por linha, preparado para as 6 bombas.
            for start in range(0, len(subset), 3):
                row_items = subset.iloc[start:start + 3]
                columns = st.columns(3)

                for index, (_, row) in enumerate(row_items.iterrows()):
                    with columns[index]:
                        device_id = str(row.get("device_id", "—"))
                        name = (
                            str(row.get("nome"))
                            if pd.notna(row.get("nome"))
                            and str(row.get("nome")).strip()
                            else device_id
                        )

                        score = health_score(row)
                        color = health_color(score)

                        full_scale_v = safe_float(
                            row.get("adc_full_scale_v"),
                            4.096
                        )

                        pressure_cfg = get_channel_config(
                            channel_configs,
                            device_id,
                            "AI004"
                        )

                        pressure = get_channel_value(
                            row,
                            channel_configs,
                            device_id,
                            "AI004",
                            full_scale_v
                        )

                        pressure_unit = channel_unit(
                            pressure_cfg,
                            "V"
                        )

                        pressure_mca = (
                            bar_to_mca(pressure)
                            if pressure_unit.lower() == "bar"
                            else np.nan
                        )

                        last = row.get("recebido_em")
                        last_text = (
                            pd.to_datetime(last).strftime("%d/%m/%Y %H:%M:%S")
                            if pd.notna(last)
                            else "sem leitura"
                        )

                        def configured_metric(canal, fallback_unit=""):
                            cfg = get_channel_config(
                                channel_configs,
                                device_id,
                                canal
                            )
                            label = channel_display_name(
                                cfg,
                                canal
                            )
                            unit = channel_unit(
                                cfg,
                                fallback_unit
                            )
                            value = get_channel_value(
                                row,
                                channel_configs,
                                device_id,
                                canal,
                                full_scale_v
                            )

                            decimals = int(
                                safe_float(
                                    cfg.get("decimais"),
                                    2
                                )
                            )

                            return (
                                label,
                                format_value(
                                    value,
                                    decimals,
                                    unit
                                )
                            )

                        temp6_label, temp6_value = configured_metric("AI006", "")
                        temp7_label, temp7_value = configured_metric("AI007", "")
                        temp8_label, temp8_value = configured_metric("AI008", "")

                        vibration_values = [
                            safe_float(row.get("x_mm_s")),
                            safe_float(row.get("y_mm_s")),
                            safe_float(row.get("z_mm_s")),
                        ]
                        vibration_values = [
                            x for x in vibration_values if np.isfinite(x)
                        ]
                        vibration_max = max(vibration_values) if vibration_values else np.nan

                        # Pressão é exibida em bar e MCA.
                        pressure_text = format_value(
                            pressure,
                            int(
                                safe_float(
                                    pressure_cfg.get("decimais"),
                                    2
                                )
                            ),
                            pressure_unit
                        )

                        mca_text = (
                            format_value(
                                pressure_mca,
                                1,
                                "MCA"
                            )
                            if np.isfinite(pressure_mca)
                            else "—"
                        )

                        # Renderização nativa do Streamlit.
                        # Evitamos HTML livre dentro do cartão para impedir
                        # que o Streamlit exiba as tags como texto.
                        with st.container(border=True):

                            header_left, header_right = st.columns([3, 1])

                            with header_left:
                                st.caption(str(location))
                                st.subheader(name)
                                st.caption(device_id)

                            with header_right:
                                status = str(row.get("status", "Offline"))
                                if status == "Online":
                                    st.success("ONLINE")
                                elif status == "Alarme":
                                    st.error("ALARME")
                                else:
                                    st.warning("OFFLINE")

                                st.metric(
                                    "Saúde",
                                    str(score),
                                )

                            st.divider()

                            m1, m2 = st.columns(2)

                            with m1:
                                st.metric(
                                    "Pressão",
                                    pressure_text,
                                    mca_text,
                                )

                            with m2:
                                st.metric(
                                    "Vibração máxima",
                                    format_value(vibration_max, 3, "mm/s"),
                                    "RMS",
                                )

                            st.caption("Temperaturas")

                            t1, t2, t3 = st.columns(3)

                            with t1:
                                st.metric(
                                    temp6_label,
                                    temp6_value,
                                )

                            with t2:
                                st.metric(
                                    temp7_label,
                                    temp7_value,
                                )

                            with t3:
                                st.metric(
                                    temp8_label,
                                    temp8_value,
                                )

                            st.caption("Vibração por eixo — mm/s RMS")

                            v1, v2, v3 = st.columns(3)

                            with v1:
                                st.metric(
                                    "X",
                                    format_value(row.get("x_mm_s"), 3),
                                )

                            with v2:
                                st.metric(
                                    "Y",
                                    format_value(row.get("y_mm_s"), 3),
                                )

                            with v3:
                                st.metric(
                                    "Z",
                                    format_value(row.get("z_mm_s"), 3),
                                )

                            st.caption(
                                f"Última leitura: {last_text}"
                            )

                        if st.button(
                            "Ver detalhes",
                            key=f"details_{device_id}",
                            use_container_width=True,
                        ):
                            st.session_state.device_id = device_id
                            st.session_state.view = "details"
                            st.rerun()


# ============================================================
# DETALHES
# ============================================================

elif st.session_state.view == "details":

    devices = device_rows["device_id"].astype(str).tolist() if not device_rows.empty else []

    if not devices:
        st.info("Nenhum dispositivo disponível.")
    else:
        current = (
            st.session_state.device_id
            if st.session_state.device_id in devices
            else devices[0]
        )

        selected = st.selectbox(
            "Equipamento",
            devices,
            index=devices.index(current),
        )

        row_matches = device_rows[
            device_rows["device_id"].astype(str) == selected
        ]

        if row_matches.empty:
            st.warning("Dispositivo sem telemetria.")
        else:
            row = row_matches.iloc[0]

            period_label = st.selectbox(
                "Período",
                ["6 horas", "24 horas", "3 dias", "7 dias"],
                index=1,
            )

            period_days = {
                "6 horas": 0.25,
                "24 horas": 1,
                "3 dias": 3,
                "7 dias": 7,
            }[period_label]

            history = load_history(selected, period_days)

            st.markdown(
                f"## {row.get('nome', selected)}"
            )
            st.markdown(
                f"{status_badge(str(row.get('status', 'Offline')))} "
                f"<span class='muted'>{selected}</span>",
                unsafe_allow_html=True,
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    "Pressão",
                    format_value(pressure, 2, pressure_unit),
                )

            with c2:
                st.metric(
                    "Pressão",
                    format_value(pressure_mca, 1, "MCA") if np.isfinite(pressure_mca) else "—",
                )

            with c3:
                st.metric(
                    "Vibração X",
                    format_value(row.get("x_mm_s"), 3, "mm/s"),
                )

            with c4:
                st.metric(
                    "Vibração Z",
                    format_value(row.get("z_mm_s"), 3, "mm/s"),
                )

            st.markdown("### Temperaturas")
            t1, t2, t3 = st.columns(3)

            for canal, container in [
                ("AI006", t1),
                ("AI007", t2),
                ("AI008", t3),
            ]:
                cfg = channel_configs.get((selected, canal), {})
                with container:
                    st.metric(
                        channel_display_name(cfg, canal),
                        format_value(
                            row.get(channel_field(canal)),
                            1,
                            channel_unit(cfg, "°C"),
                        ),
                    )

            st.markdown("### Vibração")
            if not history.empty:
                st.plotly_chart(
                    line_chart(
                        history,
                        ["x_mm_s", "y_mm_s", "z_mm_s"],
                        ["X", "Y", "Z"],
                        "Velocidade de vibração",
                        "mm/s RMS",
                    ),
                    use_container_width=True,
                )

                st.plotly_chart(
                    line_chart(
                        history,
                        ["x_rms", "y_rms", "z_rms"],
                        ["X RMS", "Y RMS", "Z RMS"],
                        "Aceleração RMS",
                        "g RMS",
                    ),
                    use_container_width=True,
                )

                st.plotly_chart(
                    line_chart(
                        history,
                        ["pressao_mca"],
                        ["Pressão"],
                        "Pressão",
                        "MCA",
                    ),
                    use_container_width=True,
                )

                st.plotly_chart(
                    line_chart(
                        history,
                        ["AI006", "AI007", "AI008"],
                        [
                            channel_display_name(
                                channel_configs.get((selected, "AI006"), {}),
                                "AI006",
                            ),
                            channel_display_name(
                                channel_configs.get((selected, "AI007"), {}),
                                "AI007",
                            ),
                            channel_display_name(
                                channel_configs.get((selected, "AI008"), {}),
                                "AI008",
                            ),
                        ],
                        "Temperaturas",
                        "°C",
                    ),
                    use_container_width=True,
                )
            else:
                st.info("Sem dados históricos para o período selecionado.")


# ============================================================
# CONFIGURAÇÃO
# ============================================================

elif st.session_state.view == "config":

    st.markdown("## Configuração")

    devices = load_devices()

    st.markdown("### Equipamentos")

    with st.expander("➕ Cadastrar novo equipamento", expanded=False):
        st.caption(
            "Cadastre o device_id real do AXION. Não invente o ID: use o mesmo "
            "device_id que aparece no payload MQTT."
        )

        with st.form("new_device_form"):
            new_device_id = st.text_input(
                "Device ID",
                placeholder="Ex.: AXION-001",
            )
            new_device_name = st.text_input(
                "Nome exibido",
                placeholder="Ex.: Bomba 01",
            )
            new_device_location = st.selectbox(
                "Local",
                ["Jacutinga", "Intermédiaria"],
            )
            new_device_description = st.text_input(
                "Descrição",
                placeholder="Ex.: Captação principal",
            )
            new_device_order = st.number_input(
                "Ordem",
                min_value=1,
                value=1,
                step=1,
            )
            new_device_active = st.checkbox(
                "Equipamento ativo",
                value=True,
            )

            create_device = st.form_submit_button(
                "Cadastrar equipamento",
                type="primary",
            )

        if create_device:
            if not new_device_id.strip():
                st.error("Informe o Device ID.")
            elif supabase is None:
                st.error("Supabase indisponível.")
            else:
                try:
                    (
                        supabase
                        .table("dispositivos")
                        .insert({
                            "device_id": new_device_id.strip(),
                            "nome_exibicao": new_device_name.strip() or new_device_id.strip(),
                            "local": new_device_location,
                            "descricao": new_device_description.strip() or None,
                            "ativo": new_device_active,
                            "ordem": int(new_device_order),
                        })
                        .execute()
                    )

                    load_devices.clear()
                    st.success(f"{new_device_id.strip()} cadastrado.")
                    st.rerun()

                except Exception as exc:
                    st.error("Não foi possível cadastrar o equipamento.")
                    st.exception(exc)


    if devices.empty:
        st.info(
            "A tabela dispositivos ainda não possui registros. "
            "Crie o primeiro dispositivo no Supabase para habilitar esta tela."
        )
    else:
        device_options = devices["device_id"].astype(str).tolist()

        selected_device = st.selectbox(
            "Equipamento",
            device_options,
        )

        device_row = devices[
            devices["device_id"].astype(str) == selected_device
        ].iloc[0]

        with st.form("device_form"):
            name = st.text_input(
                "Nome exibido",
                value=str(device_row.get("nome_exibicao") or device_row.get("nome") or selected_device),
            )

            location = st.text_input(
                "Local",
                value=str(device_row.get("local") or "Sem local"),
                help="Ex.: Jacutinga ou Intermédiaria",
            )

            description = st.text_input(
                "Descrição",
                value=str(device_row.get("descricao") or ""),
            )

            order = st.number_input(
                "Ordem",
                min_value=0,
                value=int(safe_float(device_row.get("ordem"), 999)),
                step=1,
            )

            active = st.checkbox(
                "Equipamento ativo",
                value=bool(device_row.get("ativo", True)),
            )

            save_device = st.form_submit_button(
                "Salvar equipamento",
                type="primary",
            )

        if save_device:
            ok, error = update_device(
                selected_device,
                {
                    "nome_exibicao": name.strip() or selected_device,
                    "local": location.strip() or "Sem local",
                    "descricao": description.strip() or None,
                    "ordem": int(order),
                    "ativo": active,
                },
            )

            if ok:
                st.success("Equipamento atualizado.")
                st.rerun()
            else:
                st.error(
                    "Não foi possível salvar o equipamento. "
                    "Verifique as políticas RLS da tabela dispositivos."
                )
                st.code(error or "Erro desconhecido")

        st.markdown("---")
        st.markdown("### Entradas analógicas")

        st.caption(
            "Cada entrada pode ser configurada como 0–3 V ou 4–20 mA. "
            "O shunt de 150 Ω é definido automaticamente pelo tipo elétrico."
        )

        UNIT_OPTIONS = [
            "Sem unidade",
            "bar",
            "MCA",
            "°C",
            "V",
            "%",
            "m",
            "mm",
            "mm/s RMS",
            "RPM",
            "A",
            "Hz",
        ]

        for canal_num in range(1, 9):
            canal = f"AI{canal_num:03d}"
            cfg = channel_configs.get(
                (selected_device, canal),
                {}
            )

            nome_atual = str(
                cfg.get("nome_exibicao")
                or cfg.get("nome")
                or canal
            )

            tipo_raw = str(
                cfg.get("tipo_entrada")
                or ""
            ).strip().lower()

            if (
                tipo_raw in {
                    "4-20ma",
                    "4–20ma",
                    "4–20 ma",
                    "4-20 ma",
                }
                or str(cfg.get("modo", "")).lower() == "linear_4_20ma"
            ):
                tipo_atual = "4–20 mA"
            else:
                tipo_atual = "0–3 V"

            unidade_atual = str(
                cfg.get("unidade") or "Sem unidade"
            )

            if unidade_atual not in UNIT_OPTIONS:
                unidade_atual = "Sem unidade"

            escala_min_atual = safe_float(
                cfg.get("eng_min"),
                0
            )

            escala_max_atual = safe_float(
                cfg.get("eng_max"),
                100
            )

            ativo_atual = bool(
                cfg.get("ativo", True)
            )

            alarme_min_atual = cfg.get("alarme_min")
            alarme_max_atual = cfg.get("alarme_max")

            shunt_ligado = (
                tipo_atual == "4–20 mA"
            )

            with st.expander(
                f"{canal} — {nome_atual}",
                expanded=False,
            ):
                with st.form(
                    f"channel_form_{selected_device}_{canal}"
                ):

                    channel_name = st.text_input(
                        "Nome da função",
                        value=nome_atual,
                        help=(
                            "Digite livremente a função do sensor."
                        ),
                    )

                    tipo_entrada = st.selectbox(
                        "Tipo de entrada",
                        ["0–3 V", "4–20 mA"],
                        index=(
                            1 if tipo_atual == "4–20 mA"
                            else 0
                        ),
                    )

                    # O shunt não é editável.
                    # Ele segue automaticamente o tipo elétrico.
                    st.text_input(
                        "Shunt 150 Ω",
                        value=(
                            "ON — automático"
                            if tipo_entrada == "4–20 mA"
                            else "OFF — automático"
                        ),
                        disabled=True,
                    )

                    unidade = st.selectbox(
                        "Unidade",
                        UNIT_OPTIONS,
                        index=UNIT_OPTIONS.index(
                            unidade_atual
                        ),
                    )

                    escala_min = st.number_input(
                        "Escala mínima",
                        value=float(
                            escala_min_atual
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    escala_max = st.number_input(
                        "Escala máxima",
                        value=float(
                            escala_max_atual
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    ativo = st.checkbox(
                        "Entrada ativa",
                        value=ativo_atual,
                    )

                    alarme_min = st.number_input(
                        "Limite mínimo de alarme",
                        value=float(
                            safe_float(
                                alarme_min_atual,
                                0
                            )
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    alarme_max = st.number_input(
                        "Limite máximo de alarme",
                        value=float(
                            safe_float(
                                alarme_max_atual,
                                0
                            )
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    save_channel = st.form_submit_button(
                        "Salvar entrada",
                        type="primary",
                    )

                if save_channel:

                    if not channel_name.strip():
                        st.error(
                            f"Informe o nome da função de {canal}."
                        )
                        st.stop()

                    tipo_entrada_normalizado = (
                        "4–20 mA"
                        if tipo_entrada == "4–20 mA"
                        else "0–3 V"
                    )

                    shunt_ligado = (
                        tipo_entrada_normalizado == "4–20 mA"
                    )

                    modo_interno = (
                        "linear_4_20ma"
                        if shunt_ligado
                        else "linear_voltage"
                    )

                    # Para 4–20 mA, o domínio elétrico é 4–20 mA.
                    # Para tensão, o domínio elétrico é 0–3 V.
                    if shunt_ligado:
                        source_min = 4.0
                        source_max = 20.0
                    else:
                        source_min = 0.0
                        source_max = 3.0

                    payload = {
                        "nome_exibicao": (
                            channel_name.strip()
                        ),
                        "tipo_entrada": (
                            tipo_entrada_normalizado
                        ),
                        "shunt_150r": shunt_ligado,
                        "modo": modo_interno,
                        "role": "generic",
                        "unidade": (
                            ""
                            if unidade == "Sem unidade"
                            else unidade
                        ),
                        "source_min": source_min,
                        "source_max": source_max,
                        "eng_min": float(
                            escala_min
                        ),
                        "eng_max": float(
                            escala_max
                        ),
                        "shunt_ohms": 150.0,
                        "decimais": 2,
                        "ativo": ativo,
                        "alarme_min": float(
                            alarme_min
                        ),
                        "alarme_max": float(
                            alarme_max
                        ),
                    }

                    ok, error = update_channel(
                        selected_device,
                        canal,
                        payload,
                    )

                    if ok:
                        st.success(
                            f"{canal} atualizado."
                        )
                        st.rerun()
                    else:
                        st.error(
                            f"Não foi possível salvar {canal}."
                        )
                        st.code(
                            error or "Erro desconhecido"
                        )

        st.markdown("---")
        st.markdown("### Limites de alarme")

        with st.form("global_config_form"):
            pressure_limit = st.number_input(
                "Pressão mínima (bar)",
                value=float(
                    safe_float(load_global_config().get("limite_pressao"), 2.0)
                ),
                step=0.1,
            )

            vibration_limit = st.number_input(
                "Vibração máxima (mm/s RMS)",
                value=float(
                    safe_float(load_global_config().get("limite_rms"), 5.0)
                ),
                step=0.1,
            )

            mancal_limit = st.number_input(
                "Limite AI006 (°C)",
                value=float(
                    safe_float(load_global_config().get("limite_mancal"), 75.0)
                ),
                step=1.0,
            )

            oil_limit = st.number_input(
                "Limite AI007 (°C)",
                value=float(
                    safe_float(load_global_config().get("limite_oleo"), 80.0)
                ),
                step=1.0,
            )

            save_limits = st.form_submit_button(
                "Salvar limites",
                type="primary",
            )

        if save_limits:
            try:
                (
                    supabase
                    .table("configuracoes")
                    .update({
                        "limite_pressao": pressure_limit,
                        "limite_rms": vibration_limit,
                        "limite_mancal": mancal_limit,
                        "limite_oleo": oil_limit,
                    })
                    .eq("id", 1)
                    .execute()
                )

                load_global_config.clear()
                st.success("Limites salvos.")
                st.rerun()

            except Exception as exc:
                st.error("Não foi possível salvar os limites.")
                st.exception(exc)


# ============================================================
# RODAPÉ
# ============================================================

st.markdown("---")
st.markdown(
    f"""
    <div class="muted" style="text-align:center;padding:10px;">
        AXION • Atualização automática a cada {REFRESH_SECONDS}s •
        Dados reais do Supabase
    </div>
    """,
    unsafe_allow_html=True,
)
