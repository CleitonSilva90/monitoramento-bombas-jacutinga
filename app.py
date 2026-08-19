
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
            --bg: #080c16;
            --surface: #111827;
            --surface-2: #151f33;
            --border: #28364d;
            --text: #f8fafc;
            --muted: #8fa0b8;
            --muted-2: #66758c;
            --blue: #587cff;
            --blue-soft: rgba(88,124,255,.12);
            --green: #25d58c;
            --green-soft: rgba(37,213,140,.12);
            --red: #ff626b;
            --red-soft: rgba(255,98,107,.12);
        }

        * {
            box-sizing: border-box;
        }

        .stApp {
            background:
                radial-gradient(circle at 15% 0%, rgba(88,124,255,.07), transparent 28%),
                radial-gradient(circle at 100% 0%, rgba(37,213,140,.04), transparent 24%),
                var(--bg);
            color: var(--text);
        }

        .block-container {
            max-width: 1500px;
            padding: .85rem 1rem 2rem;
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

        [data-testid="stHeader"] {
            display: none;
        }

        /* Header */
        .top-card {
            background: linear-gradient(180deg, #121b2c 0%, #0f1726 100%);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: .82rem 1rem;
            box-shadow: 0 8px 28px rgba(0,0,0,.12);
        }

        .brand-title {
            color: #ffffff;
            font-size: 1.25rem;
            font-weight: 900;
            letter-spacing: -.025em;
            line-height: 1.05;
        }

        .brand-accent {
            color: #7696ff;
        }

        .brand-sub {
            margin-top: .28rem;
            color: #8797ac;
            font-size: .68rem;
            font-weight: 650;
        }

        /* Navigation */
        div.stButton > button {
            width: 100%;
            min-height: 44px;
            border-radius: 10px;
            border: 1px solid #33445d;
            background: #111a2b;
            color: #dbe5f1;
            font-weight: 750;
            font-size: .80rem;
            box-shadow: none;
        }

        div.stButton > button:hover {
            border-color: #5a7dff;
            background: #18243a;
            color: #ffffff;
        }

        div.stButton > button[kind="primary"] {
            background: linear-gradient(180deg, #587cff 0%, #4669e7 100%);
            border-color: #6488ff;
            color: #ffffff;
            box-shadow: 0 5px 16px rgba(88,124,255,.20);
        }

        div.stButton > button[kind="primary"]:hover {
            background: linear-gradient(180deg, #6689ff 0%, #5074f1 100%);
        }

        div.stButton > button p {
            color: inherit !important;
            font-weight: 750 !important;
        }

        /* Typography */
        .page-kicker {
            margin-top: .25rem;
            color: #677890;
            font-size: .66rem;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: .12em;
        }

        .page-title,
        h1, h2, h3 {
            color: #f8fafc !important;
            letter-spacing: -.03em;
        }

        .page-title {
            margin-top: .12rem;
            margin-bottom: .6rem;
            font-size: 1.55rem;
            font-weight: 900;
        }

        .muted {
            color: #a8b4c4 !important;
            font-size: .77rem;
            font-weight: 600;
        }

        .small {
            color: #8797ac !important;
            font-size: .70rem;
            font-weight: 700;
        }

        /* KPI */
        .kpi {
            background: linear-gradient(180deg, #111a2b 0%, #0f1725 100%);
            border: 1px solid var(--border);
            border-radius: 13px;
            padding: .82rem .95rem;
            min-height: 88px;
            box-shadow: 0 7px 22px rgba(0,0,0,.08);
        }

        .kpi-value {
            margin-top: .18rem;
            font-size: 1.75rem;
            line-height: 1;
            font-weight: 900;
            color: #ffffff;
        }

        /* Location */
        .location-title {
            margin-top: 1.1rem;
            margin-bottom: .55rem;
            color: #dbe7f5;
            font-size: .82rem;
            font-weight: 850;
            letter-spacing: .01em;
        }

        .location-title::before {
            content: "";
            display: inline-block;
            width: 7px;
            height: 7px;
            margin-right: 7px;
            border-radius: 50%;
            background: var(--blue);
            box-shadow: 0 0 10px rgba(88,124,255,.45);
            vertical-align: middle;
        }

        /* Device card */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(180deg, rgba(17,26,43,.98) 0%, rgba(13,20,33,.98) 100%) !important;
            border-color: #28364d !important;
            border-radius: 15px !important;
            box-shadow: 0 9px 28px rgba(0,0,0,.12);
        }

        [data-testid="stVerticalBlockBorderWrapper"] > div {
            padding-top: .7rem !important;
            padding-bottom: .72rem !important;
        }

        /* Device header native elements */
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] {
            color: #74859c !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] h3 {
            font-size: 1.18rem !important;
            font-weight: 900 !important;
            margin-bottom: .05rem !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] hr {
            border-color: rgba(148,163,184,.10) !important;
            margin: .55rem 0 .7rem !important;
        }

        /* Metrics */
        [data-testid="stMetric"] {
            padding: .18rem 0 !important;
        }

        [data-testid="stMetricLabel"] {
            color: #8798ad !important;
            font-size: .66rem !important;
            font-weight: 800 !important;
            letter-spacing: .02em !important;
        }

        [data-testid="stMetricValue"] {
            color: #ffffff !important;
            font-size: 1.08rem !important;
            font-weight: 900 !important;
            letter-spacing: -.02em !important;
        }

        [data-testid="stMetricDelta"] {
            color: #92a2b7 !important;
            font-size: .66rem !important;
            font-weight: 700 !important;
        }

        /* Section labels */
        [data-testid="stVerticalBlockBorderWrapper"] .stCaption,
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"] {
            color: #75869c !important;
        }

        /* Status */
        .pill-online,
        .pill-offline,
        .pill-alarm {
            display: inline-flex;
            align-items: center;
            padding: .31rem .60rem;
            border-radius: 999px;
            font-size: .65rem;
            font-weight: 850;
            letter-spacing: .04em;
        }

        .pill-online {
            color: #48e49c;
            background: var(--green-soft);
            border: 1px solid rgba(37,213,140,.28);
        }

        .pill-offline {
            color: #cbd5e1;
            background: rgba(100,116,139,.10);
            border: 1px solid rgba(148,163,184,.20);
        }

        .pill-alarm {
            color: #ff858c;
            background: var(--red-soft);
            border: 1px solid rgba(255,98,107,.26);
        }

        /* Forms */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        textarea,
        input {
            background: #121c2e !important;
            color: #f8fafc !important;
            border-color: #3a4b63 !important;
        }

        div[data-baseweb="select"] span,
        div[data-baseweb="select"] input {
            color: #f8fafc !important;
        }

        [data-testid="stForm"] label,
        [data-testid="stForm"] label p,
        [data-testid="stForm"] label span {
            color: #d9e2ee !important;
            font-weight: 750 !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid #2a3a52;
            border-radius: 11px;
            background: #10192a;
        }

        [data-testid="stExpander"] summary {
            color: #f3f7fb !important;
            font-weight: 800 !important;
        }


        /* Gauge cards */
        [data-testid="stVerticalBlockBorderWrapper"] .js-plotly-plot {
            margin: -.15rem 0 -.1rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"] .plot-container {
            background: transparent !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetricLabel"] {
            color: #7e90a8 !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetricValue"] {
            font-size: 1.08rem !important;
        }

        .gauge-summary {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: .25rem;
            text-align: center;
        }

        .gauge-summary-label {
            color: #687991;
            font-size: .56rem;
            font-weight: 850;
            text-transform: uppercase;
        }

        .gauge-summary-value {
            color: #dbe7f5;
            font-size: .72rem;
            font-weight: 800;
            margin-top: .08rem;
        }

        /* Mobile */
        @media (max-width: 900px) {
            .block-container {
                padding: .65rem .65rem 1.25rem;
            }

            .top-card {
                padding: .75rem .85rem;
            }

            .brand-title {
                font-size: 1.08rem;
            }

            .page-title {
                font-size: 1.32rem;
            }

            .kpi {
                min-height: 80px;
            }

            .kpi-value {
                font-size: 1.48rem;
            }

            [data-testid="stMetricValue"] {
                font-size: 1.0rem !important;
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


def to_sao_paulo_time(value):
    """
    Converte timestamps UTC para o horário de São Paulo somente na
    apresentação. O banco continua armazenando UTC.
    """
    try:
        ts = pd.to_datetime(value, utc=True, errors="coerce")

        if pd.isna(ts):
            return pd.NaT

        return ts.tz_convert(
            "America/Sao_Paulo"
        )

    except Exception:
        return pd.NaT


def format_local_datetime(value, fmt="%d/%m/%Y %H:%M:%S"):
    ts = to_sao_paulo_time(value)

    if pd.isna(ts):
        return "sem leitura"

    return ts.strftime(fmt)


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


def is_channel_active(configs, device_id, canal):
    cfg = get_channel_config(
        configs,
        device_id,
        canal
    )

    if not cfg:
        return False

    return bool(cfg.get("ativo", True))


def get_channel_config(configs, device_id, canal):
    return configs.get(
        (str(device_id), str(canal).upper()),
        {}
    )


def get_channel_value(row, configs, device_id, canal, full_scale_v=4.096):
    cfg = get_channel_config(configs, device_id, canal)
    raw = row.get(channel_field(canal))
    return convert_channel_value(raw, cfg, full_scale_v)


def status_badge(status):
    status = str(status)

    if status == "Online":
        return "<span class='pill-online'>ONLINE</span>"

    if status == "Alarme":
        return "<span class='pill-alarm'>ALARME</span>"

    return "<span class='pill-offline'>OFFLINE</span>"


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

@st.cache_data(ttl=60)
def load_locations():
    """Carrega os locais ativos."""
    defaults = [
        "Jacutinga",
        "Intermediária",
    ]

    if supabase is None:
        return defaults

    try:
        response = (
            supabase
            .table("locais")
            .select("nome, ativo, ordem")
            .eq("ativo", True)
            .order("ordem")
            .order("nome")
            .execute()
        )

        names = [
            str(row.get("nome", "")).strip()
            for row in (response.data or [])
            if str(row.get("nome", "")).strip()
        ]

        return names or defaults

    except Exception:
        return defaults


def create_location(nome, ordem=999):
    if supabase is None:
        return False, "Supabase indisponível."

    nome = str(nome).strip()

    if not nome:
        return False, "Informe o nome do local."

    try:
        response = (
            supabase
            .table("locais")
            .insert({
                "nome": nome,
                "ativo": True,
                "ordem": int(ordem),
            })
            .select("id, nome")
            .execute()
        )

        if not response.data:
            return False, "O Supabase não confirmou o cadastro do local."

        load_locations.clear()
        return True, None

    except Exception as exc:
        return False, str(exc)


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
    Carrega public.configuracao_analogica.
    Chave usada pela interface: (device_id, "AI004").
    """
    if supabase is None:
        return {}

    try:
        response = (
            supabase
            .table("configuracao_analogica")
            .select("*")
            .order("device_id")
            .order("canal")
            .execute()
        )

        configs = {}

        for row in response.data or []:
            device_id = str(row.get("device_id", "")).strip()

            try:
                canal_number = int(row.get("canal"))
            except (TypeError, ValueError):
                continue

            if canal_number < 1 or canal_number > 16:
                continue

            canal = channel_name_from_number(canal_number)
            normalized = dict(row)

            normalized["canal"] = canal
            normalized["nome_exibicao"] = (
                row.get("nome_exibicao")
                or row.get("nome")
                or canal
            )
            normalized["tipo_entrada"] = (
                row.get("tipo_entrada")
                or (
                    "4–20 mA"
                    if str(row.get("modo", "")).lower() == "linear_4_20ma"
                    else "0–3 V"
                )
            )
            normalized["shunt_150r"] = bool(
                row.get(
                    "shunt_150r",
                    str(row.get("modo", "")).lower() == "linear_4_20ma"
                )
            )
            normalized["unidade"] = row.get("unidade") or "Sem unidade"

            configs[(device_id, canal)] = normalized

        return configs

    except Exception as exc:
        st.error("Erro ao carregar configurações das entradas.")
        st.exception(exc)
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
            # STATUS DE COMUNICAÇÃO:
            # Online/Offline depende exclusivamente da idade da telemetria.
            # Alarmes de processo não devem fazer o equipamento parecer offline.
            age = latest_age_seconds(
                row.get("recebido_em")
            )

            if age > OFFLINE_AFTER_SECONDS:
                return "Offline"

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

def normalize_channel_number(canal):
    """Converte AI001...AI016 ou 1...16 para o número do canal."""
    text = str(canal).strip().upper()
    if text.startswith("AI"):
        text = text[2:]
    number = int(text)
    if number < 1 or number > 16:
        raise ValueError(f"Canal inválido: {canal}")
    return number


def channel_name_from_number(number):
    return f"AI{int(number):03d}"


def update_channel(device_id, canal, payload):
    """
    Salva a configuração da AI.
    A interface usa AI004; o banco usa canal=4.
    """
    if supabase is None:
        return False, "Supabase indisponível."

    try:
        device_id = str(device_id).strip()
        canal_db = normalize_channel_number(canal)

        data = {
            "device_id": device_id,
            "canal": canal_db,
            **payload,
        }

        response = (
            supabase
            .table("configuracao_analogica")
            .upsert(
                data,
                on_conflict="device_id,canal",
            )
            .select("*")
            .execute()
        )

        rows = response.data or []

        if not rows:
            return False, (
                f"Supabase não retornou a configuração salva "
                f"para {device_id}/{channel_name_from_number(canal_db)}."
            )

        # O PostgREST/Supabase Python pode retornar uma lista mesmo
        # quando o upsert afeta apenas uma linha.
        saved = rows[0]

        if (
            str(saved.get("device_id")).strip() != device_id
            or int(saved.get("canal")) != canal_db
        ):
            return False, (
                "A linha retornada pelo Supabase não corresponde "
                "ao canal solicitado."
            )

        # Confirma no banco o valor efetivamente gravado.
        verify = (
            supabase
            .table("configuracao_analogica")
            .select(
                "device_id,canal,nome_exibicao,tipo_entrada,"
                "shunt_150r,unidade,eng_min,eng_max,ativo,"
                "alarme_min,alarme_max"
            )
            .eq("device_id", device_id)
            .eq("canal", canal_db)
            .limit(1)
            .execute()
        )

        verified_rows = verify.data or []

        if not verified_rows:
            return False, (
                f"Não foi possível confirmar no Supabase a configuração "
                f"de {device_id}/{channel_name_from_number(canal_db)}."
            )

        verified = verified_rows[0]

        expected_checks = {
            "nome_exibicao": data.get("nome_exibicao"),
            "tipo_entrada": data.get("tipo_entrada"),
            "shunt_150r": data.get("shunt_150r"),
            "unidade": data.get("unidade"),
            "ativo": data.get("ativo"),
        }

        for field, expected in expected_checks.items():
            if verified.get(field) != expected:
                return False, (
                    f"Supabase confirmou um valor diferente em '{field}'."
                )

        load_channel_configs.clear()
        return True, None

    except ValueError as exc:
        return False, str(exc)

    except Exception as exc:
        return False, str(exc)


def update_device(device_id, payload):
    if supabase is None:
        return False, "Supabase indisponível."

    try:
        response = (
            supabase
            .table("dispositivos")
            .update(payload)
            .eq("device_id", str(device_id).strip())
            .select("*")
            .single()
            .execute()
        )

        if not response.data:
            return False, (
                f"Dispositivo {device_id} não foi localizado "
                "para atualização."
            )

        load_devices.clear()
        load_telemetry.clear()
        return True, None

    except Exception as exc:
        return False, str(exc)



def build_report_statistics(
    device_id,
    history,
):
    """
    Constrói estatísticas de engenharia para o período selecionado.

    Retorna uma lista de dicionários com:
      nome, unidade, media, minimo, maximo, ultimo, leituras
    """
    if history.empty:
        return []

    configs = load_channel_configs()
    devices = load_devices()

    full_scale_v = 4.096

    if not devices.empty:
        match = devices[
            devices["device_id"].astype(str)
            == str(device_id)
        ]
        if not match.empty:
            full_scale_v = safe_float(
                match.iloc[0].get("adc_full_scale_v"),
                4.096
            )

    stats = []

    # Entradas analógicas ativas.
    for canal_num in range(1, 17):
        canal = f"AI{canal_num:03d}"

        if not is_channel_active(
            configs,
            device_id,
            canal
        ):
            continue

        cfg = get_channel_config(
            configs,
            device_id,
            canal
        )

        values = history.apply(
            lambda row: get_channel_value(
                row,
                configs,
                device_id,
                canal,
                full_scale_v
            ),
            axis=1,
        )

        values = pd.to_numeric(
            values,
            errors="coerce"
        ).dropna()

        if values.empty:
            continue

        nome = channel_display_name(
            cfg,
            canal
        )

        unidade = channel_unit(
            cfg,
            ""
        )

        stats.append({
            "categoria": "Entrada analógica",
            "nome": nome,
            "canal": canal,
            "unidade": unidade,
            "media": float(values.mean()),
            "minimo": float(values.min()),
            "maximo": float(values.max()),
            "ultimo": float(values.iloc[-1]),
            "leituras": int(values.count()),
        })

    # Vibração por eixo.
    for axis in ["x", "y", "z"]:
        column = f"{axis}_mm_s"

        if column not in history.columns:
            continue

        values = pd.to_numeric(
            history[column],
            errors="coerce"
        ).dropna()

        if values.empty:
            continue

        stats.append({
            "categoria": "Vibracao",
            "nome": f"Vibracao {axis.upper()}",
            "canal": axis.upper(),
            "unidade": "mm/s RMS",
            "media": float(values.mean()),
            "minimo": float(values.min()),
            "maximo": float(values.max()),
            "ultimo": float(values.iloc[-1]),
            "leituras": int(values.count()),
        })

    # RMS de aceleracao por eixo.
    for axis in ["x", "y", "z"]:
        column = f"{axis}_rms"

        if column not in history.columns:
            continue

        values = pd.to_numeric(
            history[column],
            errors="coerce"
        ).dropna()

        if values.empty:
            continue

        stats.append({
            "categoria": "Aceleracao RMS",
            "nome": f"RMS {axis.upper()}",
            "canal": axis.upper(),
            "unidade": "g RMS",
            "media": float(values.mean()),
            "minimo": float(values.min()),
            "maximo": float(values.max()),
            "ultimo": float(values.iloc[-1]),
            "leituras": int(values.count()),
        })

    return stats


def generate_service_report_pdf(
    device_id,
    row,
    history,
    period_label,
):
    """
    Gera o relatório de serviço do ativo em PDF.
    O banco permanece em UTC; datas do relatório são exibidas em
    America/Sao_Paulo.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"Relatorio de Servico AXION - {device_id}",
        author="AXION",
    )

    styles = getSampleStyleSheet()
    story = []

    device_name = str(
        row.get("nome", device_id)
    )
    local = str(
        row.get("local", "Sem local")
    )
    status = str(
        row.get("status", "Offline")
    )

    received = history["timestamp"] if (
        not history.empty
        and "timestamp" in history.columns
    ) else pd.Series(dtype="datetime64[ns, UTC]")

    if not history.empty and "recebido_em" in history.columns:
        start_ts = history["recebido_em"].min()
        end_ts = history["recebido_em"].max()
        start_text = format_local_datetime(
            start_ts,
            "%d/%m/%Y %H:%M"
        )
        end_text = format_local_datetime(
            end_ts,
            "%d/%m/%Y %H:%M"
        )
    else:
        start_text = "Sem dados"
        end_text = "Sem dados"

    story.append(
        Paragraph(
            "RELATORIO DE SERVICO - AXION",
            styles["Title"],
        )
    )

    story.append(
        Paragraph(
            f"<b>Ativo:</b> {device_name}<br/>"
            f"<b>Device ID:</b> {device_id}<br/>"
            f"<b>Local:</b> {local}<br/>"
            f"<b>Status no momento do relatorio:</b> {status}<br/>"
            f"<b>Periodo:</b> {period_label}<br/>"
            f"<b>Inicio dos dados:</b> {start_text}<br/>"
            f"<b>Fim dos dados:</b> {end_text}<br/>"
            f"<b>Total de registros analisados:</b> {len(history)}",
            styles["BodyText"],
        )
    )

    story.append(
        Spacer(1, 16)
    )

    if history.empty:
        story.append(
            Paragraph(
                "Nao existem dados para o periodo selecionado.",
                styles["BodyText"],
            )
        )
        doc.build(story)
        buffer.seek(0)
        return buffer

    stats = build_report_statistics(
        device_id,
        history,
    )

    if not stats:
        story.append(
            Paragraph(
                "Nao existem entradas ativas com dados validos "
                "para este periodo.",
                styles["BodyText"],
            )
        )
        doc.build(story)
        buffer.seek(0)
        return buffer

    story.append(
        Paragraph(
            "Resumo do comportamento do ativo",
            styles["Heading2"],
        )
    )

    summary_rows = [
        [
            "Categoria",
            "Grandeza",
            "Unidade",
            "Media",
            "Minimo",
            "Maximo",
            "Ultimo",
        ]
    ]

    for item in stats:
        summary_rows.append([
            item["categoria"],
            item["nome"],
            item["unidade"] or "-",
            f'{item["media"]:.3f}',
            f'{item["minimo"]:.3f}',
            f'{item["maximo"]:.3f}',
            f'{item["ultimo"]:.3f}',
        ])

    summary_table = Table(
        summary_rows,
        repeatRows=1,
        colWidths=[
            82, 115, 62, 62, 62, 62, 62
        ],
    )

    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#f8fafc"),
            ]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )

    story.append(summary_table)
    story.append(
        Spacer(1, 14)
    )

    # Qualitative interpretation based only on the measured values.
    story.append(
        Paragraph(
            "Comportamento no periodo",
            styles["Heading2"],
        )
    )

    highest_variation = None

    for item in stats:
        span = item["maximo"] - item["minimo"]

        if highest_variation is None or span > highest_variation[0]:
            highest_variation = (
                span,
                item,
            )

    if highest_variation:
        item = highest_variation[1]

        story.append(
            Paragraph(
                f"A maior faixa de variacao observada foi em "
                f"<b>{item['nome']}</b>, com {item['minimo']:.3f} "
                f"a {item['maximo']:.3f} {item['unidade']}.",
                styles["BodyText"],
            )
        )

    story.append(
        Spacer(1, 8)
    )

    story.append(
        Paragraph(
            "Observacao: este relatorio apresenta estatisticas "
            "calculadas a partir das leituras armazenadas no Supabase "
            "no periodo selecionado. Valores de minimo, maximo e media "
            "nao representam diagnostico automatico de falha.",
            styles["BodyText"],
        )
    )

    story.append(
        Spacer(1, 14)
    )

    story.append(
        Paragraph(
            f"Gerado em {format_local_datetime(pd.Timestamp.now(tz='UTC'))}",
            styles["BodyText"],
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer

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

top = st.columns([2, 1, 1, 1, 1])

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
        "📄  Relatórios",
        use_container_width=True,
        type="primary" if st.session_state.view == "reports" else "secondary",
    ):
        st.session_state.view = "reports"
        st.rerun()

with top[4]:
    if st.button(
        "⚙️  Configuração",
        use_container_width=True,
        type="primary" if st.session_state.view == "config" else "secondary",
    ):
        st.session_state.view = "config"
        st.rerun()

st.caption(
    f"Atualização automática a cada {REFRESH_SECONDS}s • "
    f"Última atualização: {format_local_datetime(datetime.now(timezone.utc))}"
)


# ============================================================
# DADOS ATUAIS
# ============================================================

device_rows = build_devices_view()
channel_configs = load_channel_configs()



def analog_gauge(
    title,
    value,
    unit,
    scale_min,
    scale_max,
    alarm_min=None,
    alarm_max=None,
):
    """
    Gauge compacto para uma entrada analógica.
    A escala vem da configuração da entrada; não há valores fixos
    de engenharia no firmware.
    """
    value = safe_float(value)
    scale_min = safe_float(scale_min, 0)
    scale_max = safe_float(scale_max, 100)

    if not np.isfinite(value):
        value = scale_min

    if not np.isfinite(scale_min):
        scale_min = 0

    if not np.isfinite(scale_max) or scale_max <= scale_min:
        scale_max = scale_min + 1

    # Mantém o ponteiro visível quando a leitura passa levemente do limite.
    display_value = max(
        scale_min,
        min(value, scale_max)
    )

    bar_color = "#22c55e"

    if np.isfinite(safe_float(alarm_max)) and value > safe_float(alarm_max):
        bar_color = "#ef4444"
    elif np.isfinite(safe_float(alarm_min)) and value < safe_float(alarm_min):
        bar_color = "#ef4444"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=display_value,
            number={
                "font": {
                    "size": 30,
                    "color": "#f8fafc",
                },
                "suffix": f" {unit}" if unit else "",
            },
            title={
                "text": title,
                "font": {
                    "size": 13,
                    "color": "#9aa9bd",
                },
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [scale_min, scale_max],
                    "tickfont": {
                        "size": 9,
                        "color": "#71829a",
                    },
                },
                "bar": {
                    "color": bar_color,
                    "thickness": 0.22,
                },
                "bgcolor": "#0d1422",
                "borderwidth": 0,
            },
        )
    )

    if np.isfinite(safe_float(alarm_max)):
        fig.add_hline(
            y=safe_float(alarm_max),
            line_width=0,
            opacity=0,
        )

    fig.update_layout(
        height=235,
        margin={
            "l": 18,
            "r": 18,
            "t": 28,
            "b": 8,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={
            "color": "#f8fafc",
        },
    )

    return fig


# ============================================================
# DASHBOARD
# ============================================================

if st.session_state.view == "dashboard":

    if device_rows.empty:
        st.markdown(
            "<div class='page-kicker'>Visão geral</div>"
            "<div class='page-title'>Monitoramento</div>",
            unsafe_allow_html=True,
        )

        st.info(
            "Nenhum equipamento cadastrado. "
            "Use Configuração → Cadastrar novo equipamento."
        )

    else:
        # --------------------------------------------------------
        # Cabeçalho
        # --------------------------------------------------------

        st.markdown(
            "<div class='page-kicker'>Visão geral</div>"
            "<div class='page-title'>Monitoramento</div>",
            unsafe_allow_html=True,
        )

        total = len(device_rows)
        online = int(
            (device_rows["status"] == "Online").sum()
        )
        alarms = int(
            sum(
                health_score(row) < 80
                for _, row in device_rows.iterrows()
            )
        )

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
                    <div class="kpi-value" style="color:#22c55e;">{online}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with k3:
            st.markdown(
                f"""
                <div class="kpi">
                    <div class="small">ALARMES</div>
                    <div class="kpi-value" style="color:#ff626b;">{alarms}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.caption(
            f"Atualização automática a cada {REFRESH_SECONDS}s • "
            f"Última atualização: "
            f"{format_local_datetime(datetime.now(timezone.utc))}"
        )

        # --------------------------------------------------------
        # Equipamentos por local
        # --------------------------------------------------------

        locations = (
            device_rows["local"]
            .fillna("Sem local")
            .astype(str)
            .unique()
            .tolist()
        )

        for location in locations:

            subset = (
                device_rows[
                    device_rows["local"].astype(str) == str(location)
                ]
                .sort_values(
                    ["ordem", "nome"]
                )
            )

            st.markdown(
                f"<div class='location-title'>LOCAL: {location}</div>",
                unsafe_allow_html=True,
            )

            # Um equipamento usa toda a largura.
            # Dois dividem a área.
            # Três ou mais usam três colunas.
            col_count = min(
                3,
                max(1, len(subset))
            )

            for row_start in range(
                0,
                len(subset),
                col_count
            ):
                row_items = subset.iloc[
                    row_start:row_start + col_count
                ]

                columns = st.columns(
                    col_count
                )

                for index, (_, row) in enumerate(
                    row_items.iterrows()
                ):

                    with columns[index]:

                        device_id = str(
                            row.get(
                                "device_id",
                                "—"
                            )
                        )

                        name = (
                            str(row.get("nome"))
                            if pd.notna(row.get("nome"))
                            and str(row.get("nome")).strip()
                            else device_id
                        )

                        score = health_score(row)

                        full_scale_v = safe_float(
                            row.get(
                                "adc_full_scale_v"
                            ),
                            4.096
                        )

                        last = row.get(
                            "recebido_em"
                        )

                        last_text = format_local_datetime(
                            last
                        )

                        # ----------------------------
                        # Entradas ativas
                        # ----------------------------

                        active_ai = []

                        for canal_num in range(1, 9):
                            canal_name = (
                                f"AI{canal_num:03d}"
                            )

                            if is_channel_active(
                                channel_configs,
                                device_id,
                                canal_name
                            ):
                                active_ai.append(
                                    canal_name
                                )

                        # ----------------------------
                        # Seleção das grandezas principais
                        # ----------------------------

                        candidates = []

                        for canal in active_ai:

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
                                ""
                            )

                            value = get_channel_value(
                                row,
                                channel_configs,
                                device_id,
                                canal,
                                full_scale_v
                            )

                            candidates.append({
                                "canal": canal,
                                "label": label,
                                "unit": unit,
                                "value": value,
                                "eng_min": safe_float(
                                    cfg.get(
                                        "eng_min"
                                    ),
                                    0
                                ),
                                "eng_max": safe_float(
                                    cfg.get(
                                        "eng_max"
                                    ),
                                    100
                                ),
                                "alarm_min": safe_float(
                                    cfg.get(
                                        "alarme_min"
                                    )
                                ),
                                "alarm_max": safe_float(
                                    cfg.get(
                                        "alarme_max"
                                    )
                                ),
                            })

                        # Pressão primeiro.
                        pressure_candidates = [
                            item for item in candidates
                            if (
                                "press" in item["label"].lower()
                                or item["unit"].lower()
                                in {"bar", "mca"}
                            )
                        ]

                        temperature_candidates = [
                            item for item in candidates
                            if (
                                item["unit"].lower()
                                in {"°c", "c"}
                                or "temp" in item["label"].lower()
                            )
                            and item not in pressure_candidates
                        ]

                        other_candidates = [
                            item for item in candidates
                            if item not in pressure_candidates
                            and item not in temperature_candidates
                        ]

                        main_gauges = (
                            pressure_candidates
                            + temperature_candidates
                            + other_candidates
                        )[:3]

                        # ----------------------------
                        # Cabeçalho do equipamento
                        # ----------------------------

                        with st.container(
                            border=True
                        ):

                            header_left, header_right = st.columns(
                                [3.2, 1]
                            )

                            with header_left:

                                st.caption(
                                    str(location)
                                )

                                st.subheader(
                                    name
                                )

                                st.caption(
                                    device_id
                                )

                            with header_right:

                                status = str(
                                    row.get(
                                        "status",
                                        "Offline"
                                    )
                                )

                                st.markdown(
                                    status_badge(
                                        status
                                    ),
                                    unsafe_allow_html=True,
                                )

                                st.metric(
                                    "Saúde",
                                    str(score),
                                )

                            st.divider()

                            # ----------------------------
                            # Gauges principais
                            # ----------------------------

                            if main_gauges:

                                gauge_columns = st.columns(
                                    len(main_gauges)
                                )

                                for gauge_col, item in zip(
                                    gauge_columns,
                                    main_gauges
                                ):

                                    with gauge_col:

                                        st.plotly_chart(
                                            analog_gauge(
                                                item["label"],
                                                item["value"],
                                                item["unit"],
                                                item["eng_min"],
                                                item["eng_max"],
                                                item["alarm_min"],
                                                item["alarm_max"],
                                            ),
                                            use_container_width=True,
                                            config={
                                                "displayModeBar": False,
                                                "responsive": True,
                                            },
                                        )

                                        # Min/max atuais do período
                                        # ficam abaixo do mostrador,
                                        # sem depender da aba Relatórios.
                                        history_short = load_history(
                                            device_id,
                                            7
                                        )

                                        values = pd.Series(
                                            dtype=float
                                        )

                                        if not history_short.empty:
                                            values = pd.to_numeric(
                                                history_short.apply(
                                                    lambda hist_row: get_channel_value(
                                                        hist_row,
                                                        channel_configs,
                                                        device_id,
                                                        item["canal"],
                                                        full_scale_v,
                                                    ),
                                                    axis=1,
                                                ),
                                                errors="coerce"
                                            ).dropna()

                                        if not values.empty:
                                            avg = float(
                                                values.mean()
                                            )
                                            minimum = float(
                                                values.min()
                                            )
                                            maximum = float(
                                                values.max()
                                            )

                                            st.markdown(
                                                f"""
                                                <div style="
                                                    display:grid;
                                                    grid-template-columns:repeat(3,1fr);
                                                    gap:.25rem;
                                                    margin-top:-.2rem;
                                                    margin-bottom:.2rem;
                                                    text-align:center;
                                                ">
                                                    <div>
                                                        <div style="color:#697991;font-size:.58rem;font-weight:800;text-transform:uppercase;">Média</div>
                                                        <div style="color:#dbe7f5;font-size:.72rem;font-weight:800;">{avg:.2f} {item["unit"]}</div>
                                                    </div>
                                                    <div>
                                                        <div style="color:#697991;font-size:.58rem;font-weight:800;text-transform:uppercase;">Mín.</div>
                                                        <div style="color:#dbe7f5;font-size:.72rem;font-weight:800;">{minimum:.2f} {item["unit"]}</div>
                                                    </div>
                                                    <div>
                                                        <div style="color:#697991;font-size:.58rem;font-weight:800;text-transform:uppercase;">Máx.</div>
                                                        <div style="color:#dbe7f5;font-size:.72rem;font-weight:800;">{maximum:.2f} {item["unit"]}</div>
                                                    </div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )

                            # ----------------------------
                            # Vibração principal
                            # ----------------------------

                            st.markdown(
                                "<div class='small' style='margin-top:.45rem;'>VIBRAÇÃO · mm/s RMS</div>",
                                unsafe_allow_html=True,
                            )

                            vibration_columns = st.columns(
                                4
                            )

                            vibration_axes = [
                                ("Vibração máx.", "max"),
                                ("X", "x_mm_s"),
                                ("Y", "y_mm_s"),
                                ("Z", "z_mm_s"),
                            ]

                            vibration_values = [
                                safe_float(
                                    row.get(
                                        "x_mm_s"
                                    )
                                ),
                                safe_float(
                                    row.get(
                                        "y_mm_s"
                                    )
                                ),
                                safe_float(
                                    row.get(
                                        "z_mm_s"
                                    )
                                ),
                            ]

                            valid_vibration = [
                                value
                                for value in vibration_values
                                if np.isfinite(value)
                            ]

                            vibration_max = (
                                max(
                                    valid_vibration
                                )
                                if valid_vibration
                                else np.nan
                            )

                            for col, item in zip(
                                vibration_columns,
                                vibration_axes
                            ):

                                with col:

                                    if item[1] == "max":
                                        value = vibration_max
                                    else:
                                        value = row.get(
                                            f"{item[1]}"
                                        )

                                    st.metric(
                                        item[0],
                                        format_value(
                                            value,
                                            3
                                        ),
                                    )

                            # ----------------------------
                            # Outras entradas ativas
                            # ----------------------------

                            extra_candidates = [
                                item
                                for item in candidates
                                if item not in main_gauges
                            ]

                            if extra_candidates:

                                st.markdown(
                                    "<div class='small' style='margin-top:.35rem;'>OUTRAS ENTRADAS ATIVAS</div>",
                                    unsafe_allow_html=True,
                                )

                                extra_columns = st.columns(
                                    min(
                                        4,
                                        len(
                                            extra_candidates
                                        )
                                    )
                                )

                                for col, item in zip(
                                    extra_columns,
                                    extra_candidates
                                ):

                                    with col:

                                        st.metric(
                                            item["label"],
                                            format_value(
                                                item["value"],
                                                2,
                                                item["unit"]
                                            ),
                                        )

                            # ----------------------------
                            # Rodapé
                            # ----------------------------

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

    devices = (
        device_rows["device_id"].astype(str).tolist()
        if not device_rows.empty
        else []
    )

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

            history = load_history(
                selected,
                period_days
            )

            # ------------------------------------------------
            # CONFIGURAÇÃO DO DISPOSITIVO
            # ------------------------------------------------

            device_cfg = load_devices()
            full_scale_v = safe_float(
                row.get("adc_full_scale_v"),
                4.096
            )

            if not device_cfg.empty:
                device_match = device_cfg[
                    device_cfg["device_id"].astype(str)
                    == str(selected)
                ]

                if not device_match.empty:
                    full_scale_v = safe_float(
                        device_match.iloc[0].get(
                            "adc_full_scale_v"
                        ),
                        4.096
                    )

            # ------------------------------------------------
            # STATUS / CABEÇALHO
            # ------------------------------------------------

            st.markdown(
                f"## {row.get('nome', selected)}"
            )

            st.markdown(
                f"{status_badge(str(row.get('status', 'Offline')))} "
                f"<span class='muted'>{selected}</span>",
                unsafe_allow_html=True,
            )

            # ------------------------------------------------
            # ENTRADAS ATIVAS
            # ------------------------------------------------

            active_ai = []

            for canal_num in range(1, 9):
                canal_name = f"AI{canal_num:03d}"

                if is_channel_active(
                    channel_configs,
                    selected,
                    canal_name
                ):
                    active_ai.append(canal_name)

            # ------------------------------------------------
            # PRESSÃO
            # ------------------------------------------------

            pressure_active = "AI004" in active_ai

            pressure = np.nan
            pressure_unit = ""
            pressure_mca = np.nan

            if pressure_active:
                pressure_cfg = get_channel_config(
                    channel_configs,
                    selected,
                    "AI004"
                )

                pressure = get_channel_value(
                    row,
                    channel_configs,
                    selected,
                    "AI004",
                    full_scale_v
                )

                pressure_unit = channel_unit(
                    pressure_cfg,
                    ""
                )

                if pressure_unit.lower() == "bar":
                    pressure_mca = bar_to_mca(
                        pressure
                    )

            # ------------------------------------------------
            # MÉTRICAS PRINCIPAIS
            # ------------------------------------------------

            main_metrics = []

            if pressure_active:
                main_metrics.append(
                    (
                        "Pressão",
                        format_value(
                            pressure,
                            int(
                                safe_float(
                                    pressure_cfg.get(
                                        "decimais"
                                    ),
                                    2
                                )
                            ),
                            pressure_unit
                        )
                    )
                )

                if np.isfinite(pressure_mca):
                    main_metrics.append(
                        (
                            "Pressão",
                            format_value(
                                pressure_mca,
                                1,
                                "MCA"
                            )
                        )
                    )

            main_metrics.extend([
                (
                    "Vibração X",
                    format_value(
                        row.get("x_mm_s"),
                        3,
                        "mm/s"
                    )
                ),
                (
                    "Vibração Z",
                    format_value(
                        row.get("z_mm_s"),
                        3,
                        "mm/s"
                    )
                ),
            ])

            metric_columns = st.columns(
                min(4, len(main_metrics))
            )

            for index, metric_data in enumerate(
                main_metrics[:4]
            ):
                with metric_columns[index]:
                    st.metric(
                        metric_data[0],
                        metric_data[1]
                    )

            # ------------------------------------------------
            # ENTRADAS ANALÓGICAS ATIVAS
            # ------------------------------------------------

            active_analog_channels = [
                canal
                for canal in active_ai
            ]

            if active_analog_channels:
                st.markdown(
                    "### Entradas analógicas"
                )

                analog_columns = st.columns(
                    min(4, len(active_analog_channels))
                )

                for index, canal in enumerate(
                    active_analog_channels
                ):
                    cfg = get_channel_config(
                        channel_configs,
                        selected,
                        canal
                    )

                    label = channel_display_name(
                        cfg,
                        canal
                    )

                    unit = channel_unit(
                        cfg,
                        ""
                    )

                    value = get_channel_value(
                        row,
                        channel_configs,
                        selected,
                        canal,
                        full_scale_v
                    )

                    decimals = int(
                        safe_float(
                            cfg.get("decimais"),
                            2
                        )
                    )

                    with analog_columns[
                        index % len(analog_columns)
                    ]:
                        st.metric(
                            label,
                            format_value(
                                value,
                                decimals,
                                unit
                            )
                        )

            # ------------------------------------------------
            # VIBRAÇÃO
            # ------------------------------------------------

            st.markdown(
                "### Vibração"
            )

            if not history.empty:
                st.plotly_chart(
                    line_chart(
                        history,
                        [
                            "x_mm_s",
                            "y_mm_s",
                            "z_mm_s"
                        ],
                        [
                            "X",
                            "Y",
                            "Z"
                        ],
                        "Velocidade de vibração",
                        "mm/s RMS",
                    ),
                    use_container_width=True,
                )

                st.plotly_chart(
                    line_chart(
                        history,
                        [
                            "x_rms",
                            "y_rms",
                            "z_rms"
                        ],
                        [
                            "X RMS",
                            "Y RMS",
                            "Z RMS"
                        ],
                        "Aceleração RMS",
                        "g RMS",
                    ),
                    use_container_width=True,
                )

                # Pressão histórica somente quando AI004 está ativa
                # e possui unidade bar.
                if pressure_active:
                    if (
                        "pressao_mca" in history.columns
                        and history["pressao_mca"].notna().any()
                    ):
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

                # Gráficos somente das AIs ativas.
                active_chart_channels = [
                    canal
                    for canal in active_ai
                    if canal != "AI004"
                ]

                if active_chart_channels:
                    chart_columns = []
                    chart_labels = []

                    for canal in active_chart_channels:
                        if canal in history.columns:
                            chart_columns.append(canal)

                            cfg = get_channel_config(
                                channel_configs,
                                selected,
                                canal
                            )

                            chart_labels.append(
                                channel_display_name(
                                    cfg,
                                    canal
                                )
                            )

                    if chart_columns:
                        st.plotly_chart(
                            line_chart(
                                history,
                                chart_columns,
                                chart_labels,
                                "Entradas analógicas",
                                "Valor",
                            ),
                            use_container_width=True,
                        )

            else:
                st.info(
                    "Sem dados históricos para o período selecionado."
                )

            # ------------------------------------------------
            # ÚLTIMA LEITURA
            # ------------------------------------------------

            last = row.get("recebido_em")

            st.caption(
                f"Última leitura: "
                f"{format_local_datetime(last)}"
            )


# ============================================================
# RELATÓRIOS
# ============================================================

elif st.session_state.view == "reports":

    st.markdown("## Relatorios de servico")

    st.caption(
        "Selecione o ativo e o periodo para analisar o comportamento "
        "das leituras e exportar um relatorio em PDF."
    )

    report_devices = (
        device_rows["device_id"].astype(str).tolist()
        if not device_rows.empty
        else []
    )

    if not report_devices:
        st.info(
            "Nenhum dispositivo disponível para gerar relatório."
        )
    else:
        selected_report_device = st.selectbox(
            "Ativo",
            report_devices,
            index=(
                report_devices.index(
                    st.session_state.device_id
                )
                if st.session_state.device_id
                in report_devices
                else 0
            ),
        )

        period_label = st.selectbox(
            "Periodo de analise",
            [
                "24 horas",
                "3 dias",
                "7 dias",
                "30 dias",
            ],
            index=2,
        )

        period_days = {
            "24 horas": 1,
            "3 dias": 3,
            "7 dias": 7,
            "30 dias": 30,
        }[period_label]

        report_history = load_history(
            selected_report_device,
            period_days,
        )

        selected_rows = device_rows[
            device_rows["device_id"].astype(str)
            == selected_report_device
        ]

        if selected_rows.empty:
            st.warning(
                "Dispositivo sem dados atuais."
            )
        else:
            report_row = selected_rows.iloc[0]

            st.markdown(
                f"### {report_row.get('nome', selected_report_device)}"
            )

            if report_history.empty:
                st.warning(
                    "Nao existem leituras no periodo selecionado."
                )
            else:
                report_stats = build_report_statistics(
                    selected_report_device,
                    report_history,
                )

                if report_stats:
                    stats_df = pd.DataFrame([
                        {
                            "Categoria": item["categoria"],
                            "Grandeza": item["nome"],
                            "Unidade": item["unidade"] or "-",
                            "Media": item["media"],
                            "Minimo": item["minimo"],
                            "Maximo": item["maximo"],
                            "Ultimo": item["ultimo"],
                            "Leituras": item["leituras"],
                        }
                        for item in report_stats
                    ])

                    st.dataframe(
                        stats_df,
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info(
                        "Nao existem canais ativos com dados validos "
                        "no periodo selecionado."
                    )

                c1, c2, c3 = st.columns(3)

                with c1:
                    st.metric(
                        "Leituras analisadas",
                        f"{len(report_history):,}".replace(",", "."),
                    )

                with c2:
                    first_time = report_history["recebido_em"].min()
                    st.metric(
                        "Inicio",
                        format_local_datetime(
                            first_time,
                            "%d/%m/%Y %H:%M",
                        ),
                    )

                with c3:
                    last_time = report_history["recebido_em"].max()
                    st.metric(
                        "Fim",
                        format_local_datetime(
                            last_time,
                            "%d/%m/%Y %H:%M",
                        ),
                    )

                st.markdown(
                    "### Tendencia das principais leituras"
                )

                if "vibra" in report_history.columns:
                    st.plotly_chart(
                        line_chart(
                            report_history,
                            ["vibra"],
                            ["Vibracao maxima"],
                            "Vibracao maxima no periodo",
                            "mm/s RMS",
                        ),
                        use_container_width=True,
                    )

                active_configs = []

                for canal_num in range(1, 17):
                    canal = f"AI{canal_num:03d}"

                    if not is_channel_active(
                        channel_configs,
                        selected_report_device,
                        canal
                    ):
                        continue

                    cfg = get_channel_config(
                        channel_configs,
                        selected_report_device,
                        canal
                    )

                    active_configs.append(
                        (
                            canal,
                            channel_display_name(
                                cfg,
                                canal
                            ),
                            channel_unit(
                                cfg,
                                ""
                            ),
                        )
                    )

                if active_configs:
                    for canal, label, unit in active_configs:
                        if canal not in report_history.columns:
                            continue

                        st.plotly_chart(
                            line_chart(
                                report_history,
                                [canal],
                                [label],
                                label,
                                unit or "Valor",
                            ),
                            use_container_width=True,
                        )

                pdf_buffer = generate_service_report_pdf(
                    selected_report_device,
                    report_row,
                    report_history,
                    period_label,
                )

                filename = (
                    f"AXION_"
                    f"{selected_report_device}_"
                    f"Relatorio_"
                    f"{period_label.replace(' ', '_')}.pdf"
                )

                st.download_button(
                    "Baixar relatorio PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )

# ============================================================
# CONFIGURAÇÃO
# ============================================================

elif st.session_state.view == "config":

    st.markdown("## Configuração")

    devices = load_devices()

    st.markdown("### Locais")

    with st.expander("➕ Cadastrar novo local", expanded=False):
        with st.form("new_location_form"):
            location_name = st.text_input(
                "Nome do local",
                placeholder="Ex.: Estação Norte",
            )

            location_order = st.number_input(
                "Ordem de exibição",
                min_value=1,
                value=1,
                step=1,
            )

            create_location_button = st.form_submit_button(
                "Cadastrar local",
                type="primary",
            )

        if create_location_button:
            ok_location, location_error = create_location(
                location_name,
                int(location_order),
            )

            if ok_location:
                st.success(
                    f"Local '{location_name.strip()}' cadastrado."
                )
                st.rerun()
            else:
                st.error("Não foi possível cadastrar o local.")
                st.code(
                    location_error or "Erro desconhecido"
                )

    st.markdown("### Equipamentos")

    with st.expander("➕ Cadastrar novo equipamento", expanded=False):
        st.caption(
            "Primeiro conecte o AXION ao AXION Configurator e confirme o Device ID. "
            "Depois informe aqui exatamente esse identificador. O site criará o "
            "equipamento e as entradas AI001–AI008 automaticamente."
        )

        with st.form("new_device_form"):
            new_device_id = st.text_input(
                "Device ID do AXION",
                placeholder="Ex.: AXION-000002",
                help=(
                    "Use exatamente o Device ID exibido pelo AXION Configurator."
                ),
            )

            new_device_name = st.text_input(
                "Nome exibido",
                placeholder="Ex.: Bomba 02",
            )

            location_options = load_locations()
            location_choices = location_options + ["➕ Criar novo local"]

            new_device_location_choice = st.selectbox(
                "Local",
                location_choices,
            )

            if new_device_location_choice == "➕ Criar novo local":
                new_device_location = st.text_input(
                    "Nome do novo local",
                    placeholder="Ex.: Estação Norte",
                    help=(
                        "Cadastre o novo local. Ele ficará disponível "
                        "para os próximos equipamentos."
                    ),
                ).strip()
            else:
                new_device_location = new_device_location_choice

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
            device_id_value = new_device_id.strip()
            device_name_value = (
                new_device_name.strip()
                or device_id_value
            )

            if not device_id_value:
                st.error("Informe o Device ID.")

            elif supabase is None:
                st.error("Supabase indisponível.")

            else:
                try:
                    # --------------------------------------------
                    # 1. Verifica se o equipamento já existe.
                    # --------------------------------------------
                    existing = (
                        supabase
                        .table("dispositivos")
                        .select("device_id")
                        .eq("device_id", device_id_value)
                        .limit(1)
                        .execute()
                    )

                    if existing.data:
                        st.error(
                            f"O equipamento {device_id_value} já está cadastrado."
                        )
                    else:
                        # ----------------------------------------
                        # 2. Cria o local, quando necessário.
                        # ----------------------------------------
                        if new_device_location_choice == "➕ Criar novo local":
                            if not new_device_location:
                                st.error("Informe o nome do novo local.")
                                st.stop()

                            existing_location = (
                                supabase
                                .table("locais")
                                .select("id")
                                .eq("nome", new_device_location)
                                .limit(1)
                                .execute()
                            )

                            if existing_location.data:
                                st.error(
                                    f"O local '{new_device_location}' já está cadastrado."
                                )
                                st.stop()

                            ok_location, location_error = create_location(
                                new_device_location
                            )

                            if not ok_location:
                                st.error("Não foi possível criar o local.")
                                st.code(
                                    location_error or "Erro desconhecido"
                                )
                                st.stop()

                        # ----------------------------------------
                        # 3. Cria o dispositivo.
                        # ----------------------------------------
                        device_payload = {
                            "device_id": device_id_value,
                            "nome_exibicao": device_name_value,
                            "local": new_device_location,
                            "descricao": (
                                new_device_description.strip()
                                or None
                            ),
                            "ativo": new_device_active,
                            "ordem": int(new_device_order),
                            "adc_full_scale_v": 4.096,
                        }

                        device_response = (
                            supabase
                            .table("dispositivos")
                            .insert(device_payload)
                            .select("device_id")
                            .execute()
                        )

                        if not device_response.data:
                            raise RuntimeError(
                                "O Supabase não confirmou o cadastro do equipamento."
                            )

                        # ----------------------------------------
                        # 3. Cria automaticamente AI001...AI008.
                        # Começam desativadas e genéricas.
                        # ----------------------------------------
                        channel_rows = []

                        for canal_num in range(1, 9):
                            channel_rows.append({
                                "device_id": device_id_value,
                                "canal": canal_num,
                                "nome_exibicao": (
                                    f"AI{canal_num:03d}"
                                ),
                                "role": "generic",
                                "modo": "linear_voltage",
                                "unidade": "",
                                "source_min": 0.0,
                                "source_max": 3.0,
                                "eng_min": 0.0,
                                "eng_max": 100.0,
                                "shunt_ohms": 150.0,
                                "decimais": 2,
                                "ativo": False,
                                "alarme_min": None,
                                "alarme_max": None,
                                "tipo_entrada": "0–3 V",
                                "shunt_150r": False,
                            })

                        (
                            supabase
                            .table("configuracao_analogica")
                            .upsert(
                                channel_rows,
                                on_conflict="device_id,canal",
                            )
                            .execute()
                        )

                        load_devices.clear()
                        load_channel_configs.clear()
                        load_locations.clear()
                        load_telemetry.clear()

                        st.success(
                            f"{device_name_value} cadastrado com sucesso."
                        )

                        st.info(
                            "As AI001–AI008 foram criadas como inativas. "
                            "Configure as entradas desejadas na seção abaixo. "
                            "Depois, use o AXION Configurator para provisionar o "
                            "token e calibrar a vibração."
                        )

                        st.session_state.device_id = device_id_value
                        st.rerun()

                except Exception as exc:
                    st.error(
                        "Não foi possível cadastrar o equipamento."
                    )
                    st.code(
                        str(exc)
                    )


    if devices.empty:
        st.info(
            "Nenhum equipamento cadastrado ainda. "
            "Use 'Cadastrar novo equipamento' acima."
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
