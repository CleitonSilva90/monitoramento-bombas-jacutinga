



import math
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
        :root { --page:#f4f6f8; --surface:#fff; --border:#d8dee6; --text:#1f2937; --muted:#6f7b8b; --blue:#536fca; --green:#39b985; --red:#e45b63; --shadow:0 5px 18px rgba(31,41,55,.055); }
        *{box-sizing:border-box}
        .stApp{background:linear-gradient(180deg,#f8fafc 0%,#f2f5f7 100%);color:var(--text)}
        .block-container{max-width:1500px;padding:.8rem 1rem 2rem}
        [data-testid="stHeader"]{display:none}
        .top-card{background:#fff;border:1px solid var(--border);border-radius:14px;padding:.85rem 1rem;box-shadow:var(--shadow)}
        .brand-title{color:#162033;font-size:1.25rem;font-weight:900;line-height:1.05;letter-spacing:-.025em}.brand-accent{color:var(--blue)}.brand-sub{margin-top:.3rem;color:#7a8594;font-size:.68rem;font-weight:650}
        div.stButton>button{width:100%;min-height:42px;border-radius:10px;border:1px solid #c8d0da;background:#fff;color:#344054;font-weight:750;font-size:.79rem;box-shadow:0 2px 6px rgba(31,41,55,.035)}
        div.stButton>button:hover{background:#f4f7fc;border-color:#8ca2d7;color:#234a9f}
        div.stButton>button[kind="primary"]{background:#536fca;border-color:#536fca;color:#fff;box-shadow:0 4px 12px rgba(83,111,201,.18)}
        div.stButton>button p{color:inherit!important;font-weight:750!important}
        .page-kicker{color:#7a8594;font-size:.64rem;font-weight:850;text-transform:uppercase;letter-spacing:.11em}.page-title,h1,h2,h3{color:#1c2635!important;letter-spacing:-.03em}.page-title{margin-top:.1rem;margin-bottom:.55rem;font-size:1.5rem;font-weight:900}
        .muted{color:#7b8594!important}.small{color:#7c8796!important;font-size:.67rem;font-weight:800}
        .kpi{background:#fff;border:1px solid var(--border);border-radius:13px;padding:.8rem .95rem;min-height:82px;box-shadow:var(--shadow)}.kpi-value{color:#182233;font-size:1.72rem;line-height:1;font-weight:900}
        .location-title{margin-top:1rem;margin-bottom:.55rem;color:#2f3a4a;font-size:.81rem;font-weight:850}.location-title::before{content:"";display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:#657fd1;vertical-align:middle}
        [data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid #d9dfe6!important;border-radius:15px!important;box-shadow:var(--shadow)}
        [data-testid="stVerticalBlockBorderWrapper"]>div{padding-top:.65rem!important;padding-bottom:.65rem!important}[data-testid="stVerticalBlockBorderWrapper"] h3{color:#162033!important;font-size:1.16rem!important;font-weight:900!important}[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"]{color:#798594!important}[data-testid="stVerticalBlockBorderWrapper"] hr{border-color:#e5e8ed!important;margin:.55rem 0 .7rem!important}
        [data-testid="stMetricLabel"]{color:#707c8b!important;font-size:.65rem!important;font-weight:800!important}[data-testid="stMetricValue"]{color:#172131!important;font-size:1.05rem!important;font-weight:900!important}[data-testid="stMetricDelta"]{color:#7b8594!important;font-size:.64rem!important}
        .pill-online,.pill-offline,.pill-alarm{display:inline-flex;align-items:center;padding:.3rem .58rem;border-radius:999px;font-size:.63rem;font-weight:850}.pill-online{color:#21825b;background:#e6f7ef;border:1px solid #bce7d1}.pill-offline{color:#5f6b79;background:#f1f3f5;border:1px solid #dfe4e9}.pill-alarm{color:#b43b44;background:#fdebec;border:1px solid #f2c4c7}
        .compact-gauge{width:100%;background:#fff;border:1px solid #e0e5eb;border-radius:12px;padding:.62rem .72rem .50rem;box-shadow:0 2px 9px rgba(31,41,55,.035)}
        .compact-gauge-head{display:flex;align-items:baseline;justify-content:space-between;gap:.55rem}
        .compact-gauge-title{color:#4a586a;font-size:.72rem;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .compact-gauge-value{color:#172132;font-size:1.04rem;font-weight:900;white-space:nowrap}
        .compact-gauge-track{height:9px;margin-top:.46rem;border-radius:999px;background:#e7ebef;overflow:hidden}
        .compact-gauge-fill{height:100%;border-radius:999px;min-width:2%}
        .compact-gauge-range{display:flex;justify-content:space-between;margin-top:.24rem;color:#657183;font-size:.58rem;font-weight:800}
        div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,textarea,input{background:#fff!important;color:#1f2937!important;border-color:#cbd4de!important}div[data-baseweb="select"] span,div[data-baseweb="select"] input{color:#1f2937!important}
        [data-testid="stForm"] label,[data-testid="stForm"] label p,[data-testid="stForm"] label span{color:#4c5665!important;font-weight:750!important}[data-testid="stExpander"]{background:#fff;border:1px solid #d9dfe6;border-radius:11px}[data-testid="stExpander"] summary{color:#263242!important;font-weight:800!important}
        @media(max-width:900px){.block-container{padding:.55rem .5rem 1.2rem}.brand-title{font-size:1.08rem}.page-title{font-size:1.3rem}.kpi{min-height:76px}.kpi-value{font-size:1.42rem}}
        [data-testid="stPlotlyChart"]{
            background:#ffffff!important;
            border:1px solid #dfe4ea!important;
            border-radius:14px!important;
            padding:.35rem .35rem .15rem!important;
            box-shadow:0 3px 12px rgba(31,41,55,.035);
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



@st.cache_data(ttl=30)
def load_alarm_events(device_id, days):
    """
    Carrega eventos de alarme cujo intervalo se sobrepõe ao período solicitado.
    Horários são mantidos em UTC no banco e convertidos apenas na apresentação.
    """
    if supabase is None or not device_id:
        return pd.DataFrame()

    start = (
        datetime.now(timezone.utc)
        - timedelta(days=days)
    )

    try:
        response = (
            supabase
            .table("alarm_eventos")
            .select(
                "id,device_id,grandeza,canal,unidade,"
                "motivo,valor_inicio,valor_fim,limite,"
                "inicio_em,fim_em,ativo"
            )
            .eq("device_id", str(device_id))
            .lt("inicio_em", datetime.now(timezone.utc).isoformat())
            .or_(
                "fim_em.is.null,"
                f"fim_em.gte.{start.isoformat()}"
            )
            .order("inicio_em", desc=False)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        for col in [
            "inicio_em",
            "fim_em",
        ]:
            if col in df.columns:
                df[col] = pd.to_datetime(
                    df[col],
                    utc=True,
                    errors="coerce",
                )

        return df

    except Exception as exc:
        st.error("Erro ao carregar histórico de alarmes.")
        st.exception(exc)
        return pd.DataFrame()


# ============================================================
# ALARMES
# ============================================================

def get_current_device_alarms(row):
    """
    Retorna os alarmes ativos da leitura atual do equipamento.
    """
    try:
        alarms = build_alarms(
            pd.DataFrame([row])
        )

        if alarms.empty:
            return alarms

        return alarms[
            alarms["Equipamento"].astype(str)
            == str(row.get("device_id", ""))
        ].copy()

    except Exception:
        return pd.DataFrame()

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

    palette = [
        "#3b82f6",
        "#f59e0b",
        "#e85b63",
        "#39b985",
        "#8b5cf6",
        "#06b6d4",
    ]

    valid_series = []

    for index, (col, label) in enumerate(zip(columns, labels)):
        if col not in df.columns:
            continue

        series = pd.to_numeric(
            df[col],
            errors="coerce",
        )

        if not series.notna().any():
            continue

        valid_series.append(series)

        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=series,
                mode="lines",
                name=label,
                line={
                    "width": 2.4,
                    "color": palette[index % len(palette)],
                },
                connectgaps=False,
                hovertemplate=(
                    "%{x|%d/%m/%Y %H:%M}<br>"
                    "<b>%{y:.3f}</b><extra></extra>"
                ),
            )
        )

    y_min = None
    y_max = None

    if valid_series:
        combined = pd.concat(
            valid_series,
            axis=0,
            ignore_index=True,
        ).dropna()

        if not combined.empty:
            data_min = float(combined.min())
            data_max = float(combined.max())
            span = data_max - data_min

            padding = (
                max(abs(data_max) * 0.15, 0.05)
                if span <= 0
                else span * 0.12
            )

            y_min = data_min - padding
            y_max = data_max + padding

            if data_min >= 0:
                y_min = min(
                    0.0,
                    data_min - padding,
                )

    fig.update_layout(
        title={
            "text": title,
            "font": {
                "size": 15,
                "color": "#243041",
            },
            "x": 0,
            "xanchor": "left",
        },
        height=350,
        margin=dict(
            l=58,
            r=18,
            t=52,
            b=54,
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        font={
            "color": "#374151",
            "size": 11,
        },
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.25,
            "xanchor": "left",
            "x": 0,
            "font": {
                "size": 10,
                "color": "#4b5563",
            },
        },
        xaxis={
            "showgrid": True,
            "gridcolor": "#e5e7eb",
            "zeroline": False,
            "linecolor": "#cfd6df",
            "tickfont": {
                "size": 10,
                "color": "#697586",
            },
        },
        yaxis={
            "title": {
                "text": yaxis,
                "font": {
                    "size": 11,
                    "color": "#667085",
                },
            },
            "showgrid": True,
            "gridcolor": "#e5e7eb",
            "zeroline": True,
            "zerolinecolor": "#cfd6df",
            "linecolor": "#cfd6df",
            "tickfont": {
                "size": 10,
                "color": "#697586",
            },
        },
    )

    if y_min is not None and y_max is not None:
        fig.update_yaxes(
            range=[y_min, y_max]
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
    alarm_events=None,
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

    # ------------------------------------------------------------
    # HISTÓRICO DE ALARMES
    # ------------------------------------------------------------

    if alarm_events is not None and not alarm_events.empty:
        story.append(
            Paragraph(
                "Historico de alarmes",
                styles["Heading2"],
            )
        )

        alarm_rows = [[
            "Grandeza",
            "Inicio",
            "Fim",
            "Duracao",
            "Inicio",
            "Fim",
            "Limite",
            "Motivo",
        ]]

        for _, event in alarm_events.iterrows():
            start_dt = event.get("inicio_em")
            end_dt = event.get("fim_em")

            start_text = format_local_datetime(
                start_dt,
                "%d/%m/%Y %H:%M",
            )

            if pd.isna(end_dt):
                end_text = "ATIVO"
                duration_text = "Em andamento"
            else:
                end_text = format_local_datetime(
                    end_dt,
                    "%d/%m/%Y %H:%M",
                )

                try:
                    duration_seconds = (
                        pd.Timestamp(end_dt)
                        - pd.Timestamp(start_dt)
                    ).total_seconds()

                    total_minutes = max(
                        0,
                        int(duration_seconds // 60)
                    )

                    days_part = total_minutes // 1440
                    hours_part = (
                        total_minutes % 1440
                    ) // 60
                    minutes_part = (
                        total_minutes % 60
                    )

                    if days_part:
                        duration_text = (
                            f"{days_part}d "
                            f"{hours_part}h "
                            f"{minutes_part}min"
                        )
                    elif hours_part:
                        duration_text = (
                            f"{hours_part}h "
                            f"{minutes_part}min"
                        )
                    else:
                        duration_text = (
                            f"{minutes_part}min"
                        )

                except Exception:
                    duration_text = "—"

            unit = str(
                event.get("unidade") or ""
            )

            value_start = format_value(
                event.get("valor_inicio"),
                2,
                unit,
            )

            value_end = (
                "—"
                if pd.isna(event.get("valor_fim"))
                else format_value(
                    event.get("valor_fim"),
                    2,
                    unit,
                )
            )

            limit = format_value(
                event.get("limite"),
                2,
                unit,
            )

            alarm_rows.append([
                str(event.get("grandeza") or "Alarme"),
                start_text,
                end_text,
                duration_text,
                value_start,
                value_end,
                limit,
                str(event.get("motivo") or ""),
            ])

        alarm_table = Table(
            alarm_rows,
            repeatRows=1,
            colWidths=[
                88,
                72,
                72,
                65,
                55,
                55,
                55,
                92,
            ],
        )

        alarm_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b4232d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#fff7f7"),
                ]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ])
        )

        story.append(alarm_table)
        story.append(Spacer(1, 12))

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



def analog_gauge_html(
    title,
    value,
    unit,
    scale_min,
    scale_max,
    alarm_min=None,
    alarm_max=None,
):
    raw_value = safe_float(value)
    smin = safe_float(scale_min, 0)
    smax = safe_float(scale_max, 100)

    if not np.isfinite(smin):
        smin = 0.0
    if not np.isfinite(smax) or smax <= smin:
        smax = smin + 1.0
    if not np.isfinite(raw_value):
        raw_value = smin

    pct = max(0.0, min(1.0, (raw_value - smin) / (smax - smin)))

    alarm_low = safe_float(alarm_min)
    alarm_high = safe_float(alarm_max)
    critical = ((np.isfinite(alarm_low) and raw_value < alarm_low) or
                (np.isfinite(alarm_high) and raw_value > alarm_high))

    color = "#e45b63" if critical else "#39b985"

    return f'''
    <div class="compact-gauge">
        <div class="compact-gauge-head">
            <div class="compact-gauge-title">{title}</div>
            <div class="compact-gauge-value">{format_value(raw_value, 2, unit)}</div>
        </div>
        <div class="compact-gauge-track">
            <div class="compact-gauge-fill" style="width:{pct * 100:.1f}%;background:{color};"></div>
        </div>
        <div class="compact-gauge-range">
            <span>{format_value(smin, 0, "")}</span>
            <span>{format_value(smax, 0, "")}</span>
        </div>
    </div>
    '''

def render_alarm_card(
    grandeza,
    reason,
    value_text,
    limit_text,
    when_text,
):
    html = (
        '<div style="'
        'margin:.35rem 0 .45rem;'
        'padding:.55rem .7rem;'
        'border-radius:10px;'
        'background:#fff3f3;'
        'border:1px solid #f1c6c9;'
        '">'
        f'<div style="color:#b33a43;font-size:.80rem;font-weight:900;">'
        f'{grandeza}'
        '</div>'
        f'<div style="color:#5b6573;font-size:.73rem;margin-top:.10rem;">'
        f'{reason}'
        '</div>'
        f'<div style="color:#253043;font-size:.78rem;font-weight:850;margin-top:.18rem;">'
        f'Valor: {value_text} &nbsp; • &nbsp; Limite: {limit_text}'
        '</div>'
        f'<div style="color:#6f7b8b;font-size:.66rem;margin-top:.13rem;">'
        f'{when_text}'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


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
        alarms = 0

        for _, dashboard_row in device_rows.iterrows():
            current_alarms = get_current_device_alarms(
                dashboard_row
            )

            if not current_alarms.empty:
                alarms += len(current_alarms)

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

        if alarms > 0:
            st.markdown(
                f"""
                <div style="
                    margin:.55rem 0 .25rem;
                    padding:.65rem .8rem;
                    border-radius:11px;
                    background:#fff4f4;
                    border:1px solid #f1c5c8;
                    color:#a93640;
                    font-size:.78rem;
                    font-weight:850;
                ">
                    {alarms} alarme(s) ativo(s).
                    Consulte cada equipamento para ver a grandeza,
                    o valor atual e o limite que foi excedido.
                </div>
                """,
                unsafe_allow_html=True,
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
                                "exibir_gauge": bool(
                                    cfg.get("exibir_gauge", True)
                                ),
                            })

                        # Entradas ativas com 'Exibir gauge no dashboard' habilitado viram gauges.
                        # A quantidade não é limitada: quando uma nova AI é
                        # ativada, ela automaticamente ganha seu próprio gauge.
                        active_gauges = [
                            item
                            for item in candidates
                            if bool(item.get("exibir_gauge", True))
                        ]

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

                            if active_gauges:

                                # Quatro gauges por linha deixam o cartão
                                # muito mais compacto quando existem várias AIs.
                                for gauge_start in range(
                                    0,
                                    len(active_gauges),
                                    4
                                ):
                                    gauge_row = active_gauges[
                                        gauge_start:gauge_start + 4
                                    ]

                                    gauge_columns = st.columns(
                                        len(gauge_row),
                                        gap="small",
                                    )

                                    for gauge_col, item in zip(
                                        gauge_columns,
                                        gauge_row
                                    ):
                                        with gauge_col:
                                            st.markdown(
                                                analog_gauge_html(
                                                    item["label"], item["value"], item["unit"],
                                                    item["eng_min"], item["eng_max"],
                                                    item["alarm_min"], item["alarm_max"],
                                                ),
                                                unsafe_allow_html=True,
                                            )

                                            # Min/max atuais do período
                                            # ficam abaixo do mostrador,
                                            # sem depender da aba Relatórios.
                                            if "history_short" not in locals():
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
                                                avg = float(values.mean())
                                                minimum = float(values.min())
                                                maximum = float(values.max())
                                                minimum = max(item["eng_min"], min(minimum, item["eng_max"]))
                                                maximum = max(item["eng_min"], min(maximum, item["eng_max"]))
                                                avg = max(item["eng_min"], min(avg, item["eng_max"]))

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
                                                            <div style="color:#4f5d6d;font-size:.70rem;font-weight:900;text-transform:uppercase;">Média</div>
                                                            <div style="color:#344054;font-size:.74rem;font-weight:900;">{avg:.2f} {item["unit"]}</div>
                                                        </div>
                                                        <div>
                                                            <div style="color:#4f5d6d;font-size:.70rem;font-weight:900;text-transform:uppercase;">Mín.</div>
                                                            <div style="color:#344054;font-size:.74rem;font-weight:900;">{minimum:.2f} {item["unit"]}</div>
                                                        </div>
                                                        <div>
                                                            <div style="color:#4f5d6d;font-size:.70rem;font-weight:900;text-transform:uppercase;">Máx.</div>
                                                            <div style="color:#344054;font-size:.74rem;font-weight:900;">{maximum:.2f} {item["unit"]}</div>
                                                        </div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )

                            # ----------------------------
                            # Alarmes ativos
                            # ----------------------------

                            current_alarms = get_current_device_alarms(
                                row
                            )

                            if not current_alarms.empty:
                                st.markdown(
                                    "<div class='small' style='margin-top:.55rem;'>ALARMES ATIVOS</div>",
                                    unsafe_allow_html=True,
                                )

                                for _, alarm in current_alarms.iterrows():
                                    value_text = format_value(
                                        alarm.get("Valor"),
                                        2,
                                        alarm.get("Unidade", "")
                                    )

                                    limit_text = format_value(
                                        alarm.get("Limite"),
                                        2,
                                        alarm.get("Unidade", "")
                                    )

                                    if alarm.get("Valor") < alarm.get("Limite"):
                                        reason = "Abaixo do limite mínimo"
                                    else:
                                        reason = "Acima do limite máximo"

                                    when_text = format_local_datetime(
                                        alarm.get("Data/Hora")
                                    )

                                    render_alarm_card(
                                        alarm.get("Grandeza", "Alarme"),
                                        reason,
                                        value_text,
                                        limit_text,
                                        when_text,
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
            # ALARMES ATIVOS
            # ------------------------------------------------

            current_alarms = get_current_device_alarms(
                row
            )

            if not current_alarms.empty:
                st.markdown(
                    "### Alarmes ativos"
                )

                for _, alarm in current_alarms.iterrows():
                    value_text = format_value(
                        alarm.get("Valor"),
                        2,
                        alarm.get("Unidade", "")
                    )

                    limit_text = format_value(
                        alarm.get("Limite"),
                        2,
                        alarm.get("Unidade", "")
                    )

                    reason = (
                        "Abaixo do limite mínimo"
                        if alarm.get("Valor") < alarm.get("Limite")
                        else "Acima do limite máximo"
                    )

                    st.error(
                        f"{alarm.get('Grandeza', 'Alarme')} — "
                        f"{reason}. "
                        f"Valor: {value_text} | "
                        f"Limite: {limit_text} | "
                        f"{format_local_datetime(alarm.get('Data/Hora'))}"
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

        report_alarm_events = load_alarm_events(
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

                st.markdown(
                    "### Historico de alarmes"
                )

                if report_alarm_events.empty:
                    st.info(
                        "Nenhum evento de alarme registrado no período."
                    )
                else:
                    alarm_view = report_alarm_events.copy()

                    alarm_view["Inicio"] = alarm_view[
                        "inicio_em"
                    ].apply(
                        lambda value: format_local_datetime(
                            value,
                            "%d/%m/%Y %H:%M"
                        )
                    )

                    alarm_view["Fim"] = alarm_view[
                        "fim_em"
                    ].apply(
                        lambda value: (
                            "ATIVO"
                            if pd.isna(value)
                            else format_local_datetime(
                                value,
                                "%d/%m/%Y %H:%M"
                            )
                        )
                    )

                    alarm_view["Valor inicial"] = alarm_view.apply(
                        lambda item: format_value(
                            item.get("valor_inicio"),
                            2,
                            item.get("unidade", "")
                        ),
                        axis=1,
                    )

                    alarm_view["Valor final"] = alarm_view.apply(
                        lambda item: (
                            "—"
                            if pd.isna(item.get("valor_fim"))
                            else format_value(
                                item.get("valor_fim"),
                                2,
                                item.get("unidade", "")
                            )
                        ),
                        axis=1,
                    )

                    alarm_view["Limite"] = alarm_view.apply(
                        lambda item: format_value(
                            item.get("limite"),
                            2,
                            item.get("unidade", "")
                        ),
                        axis=1,
                    )

                    alarm_view = alarm_view.rename(
                        columns={
                            "grandeza": "Grandeza",
                            "motivo": "Motivo",
                        }
                    )

                    st.dataframe(
                        alarm_view[
                            [
                                "Grandeza",
                                "Inicio",
                                "Fim",
                                "Valor inicial",
                                "Valor final",
                                "Limite",
                                "Motivo",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

                pdf_buffer = generate_service_report_pdf(
                    selected_report_device,
                    report_row,
                    report_history,
                    period_label,
                    report_alarm_events,
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
                                "exibir_gauge": True,
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

            exibir_gauge_atual = bool(
                cfg.get("exibir_gauge", True)
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

                    exibir_gauge = st.checkbox(
                        "Exibir gauge no dashboard",
                        value=exibir_gauge_atual,
                        help=(
                            "Quando ativado, esta entrada aparece como "
                            "mostrador analógico no Dashboard. Desative "
                            "para manter a leitura disponível sem criar gauge."
                        ),
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
                        "exibir_gauge": exibir_gauge,
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
        st.info(
            "Os limites de alarme das entradas analógicas são configurados "
            "diretamente em cada AI. Ao salvar a entrada, os valores mínimo "
            "e máximo passam a ser usados imediatamente pelo sistema de alarmes."
        )

        st.markdown(
            "<div class='small' style='margin-top:.35rem;'>"
            "A vibração dos eixos X/Y/Z é uma aquisição nativa do AXION e "
            "possui tratamento separado dos limites das entradas analógicas."
            "</div>",
            unsafe_allow_html=True,
        )


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
