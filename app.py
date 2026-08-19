

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
            --border: #334155;
            --text: #f8fafc;
            --muted: #94a3b8;
            --blue: #3b82f6;
            --green: #10b981;
            --yellow: #f59e0b;
            --red: #ef4444;
            --cyan: #38bdf8;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(59,130,246,.12), transparent 35%),
                linear-gradient(135deg, #0b1020 0%, #070b14 100%);
            color: var(--text);
        }

        /* Botões do aplicativo */
        div.stButton > button {
            width: 100%;
            min-height: 44px;
            border-radius: 10px;
            border: 1px solid #475569;
            background: #1e293b;
            color: #f8fafc;
            font-weight: 750;
            font-size: 0.92rem;
            box-shadow: 0 3px 10px rgba(0,0,0,.15);
        }

        div.stButton > button:hover {
            border-color: #60a5fa;
            background: #263650;
            color: #ffffff;
        }

        div.stButton > button:focus {
            border-color: #60a5fa;
            box-shadow: 0 0 0 2px rgba(59,130,246,.22);
            color: #ffffff;
        }

        /* Botão ativo / primary */
        div.stButton > button[kind="primary"] {
            background: #2563eb;
            border-color: #3b82f6;
            color: #ffffff;
        }

        div.stButton > button[kind="primary"]:hover {
            background: #1d4ed8;
            border-color: #60a5fa;
            color: #ffffff;
        }

        /* Ícones e texto internos */
        div.stButton > button p {
            color: inherit !important;
            font-weight: 750 !important;
        }

        [data-testid="stHeader"] {
            display: none;
        }

        .block-container {
            max-width: 1600px;
            padding-top: 1rem;
            padding-bottom: 2rem;
        }

        .top-card {
            background: linear-gradient(135deg, #1d2740 0%, #151d31 100%);
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 1.3rem 1.5rem;
            margin-bottom: 1rem;
        }

        .device-card {
            background: linear-gradient(135deg, #1e293b 0%, #172033 100%);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 1rem;
            min-height: 360px;
            box-shadow: 0 8px 24px rgba(0,0,0,.18);
        }

        .device-card:hover {
            border-color: rgba(59,130,246,.8);
        }

        .metric {
            background: rgba(15,23,42,.52);
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 10px;
            padding: .7rem;
            min-height: 74px;
        }

        .metric-title {
            color: #94a3b8;
            font-size: .72rem;
            text-transform: uppercase;
            letter-spacing: .3px;
        }

        .metric-value {
            color: #f8fafc;
            font-size: 1.15rem;
            font-weight: 800;
            margin-top: .25rem;
        }

        .location-title {
            margin-top: 1rem;
            margin-bottom: .6rem;
            font-size: 1.1rem;
            font-weight: 800;
        }

        .kpi {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 14px;
            padding: 1rem;
            text-align: center;
        }

        .kpi-value {
            font-size: 1.9rem;
            font-weight: 850;
            line-height: 1.1;
        }

        .muted {
            color: #94a3b8;
            font-size: .82rem;
        }

        .small {
            color: #94a3b8;
            font-size: .74rem;
        }

        .pill-online {
            display: inline-block;
            padding: .26rem .6rem;
            border-radius: 999px;
            background: rgba(16,185,129,.12);
            color: #10b981;
            border: 1px solid rgba(16,185,129,.25);
            font-weight: 700;
            font-size: .72rem;
        }

        .pill-offline {
            display: inline-block;
            padding: .26rem .6rem;
            border-radius: 999px;
            background: rgba(100,116,139,.12);
            color: #94a3b8;
            border: 1px solid rgba(100,116,139,.25);
            font-weight: 700;
            font-size: .72rem;
        }

        .pill-alarm {
            display: inline-block;
            padding: .26rem .6rem;
            border-radius: 999px;
            background: rgba(239,68,68,.12);
            color: #ef4444;
            border: 1px solid rgba(239,68,68,.25);
            font-weight: 700;
            font-size: .72rem;
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
    # A telemetria atual grava os canais diretamente como ai001...ai016.
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
    fs = safe_float(full_scale_v, 4.096)
    if not np.isfinite(raw) or not np.isfinite(fs) or fs <= 0:
        return np.nan
    # ADS1115 em faixa de ±full scale.
    return raw * fs / 32767.0


def engineering_value(raw, config, full_scale_v=4.096):
    """
    Converte a leitura RAW do ADS1115 para valor de engenharia conforme
    configuracao_analogica.

    Modos:
      raw_voltage   -> retorna tensão
      linear_voltage -> tensão source_min/source_max -> eng_min/eng_max
      linear_raw     -> RAW source_min/source_max -> eng_min/eng_max
      linear_4_20mA  -> tensão -> corrente pelo shunt -> eng_min/eng_max
      disabled       -> NaN
    """
    if not config or not bool(config.get("ativo", True)):
        return np.nan

    modo = str(config.get("modo") or "raw_voltage").lower()

    if modo == "disabled":
        return np.nan

    if modo == "raw_voltage":
        return raw_to_voltage(raw, full_scale_v)

    raw_value = safe_float(raw)
    if not np.isfinite(raw_value):
        return np.nan

    source_min = safe_float(config.get("source_min"), 0.0)
    source_max = safe_float(config.get("source_max"), 4.096)
    eng_min = safe_float(config.get("eng_min"), 0.0)
    eng_max = safe_float(config.get("eng_max"), 4.096)

    if modo == "linear_raw":
        if source_max == source_min:
            return np.nan
        ratio = (raw_value - source_min) / (source_max - source_min)
        return eng_min + ratio * (eng_max - eng_min)

    voltage = raw_to_voltage(raw_value, full_scale_v)
    if not np.isfinite(voltage):
        return np.nan

    if modo == "linear_voltage":
        if source_max == source_min:
            return np.nan
        ratio = (voltage - source_min) / (source_max - source_min)
        return eng_min + ratio * (eng_max - eng_min)

    if modo == "linear_4_20ma":
        shunt = safe_float(config.get("shunt_ohms"), 150.0)
        if not np.isfinite(shunt) or shunt <= 0:
            return np.nan

        current_ma = (voltage / shunt) * 1000.0

        # Para transmissor 4-20 mA, a conversão é sempre 4...20 mA.
        ratio = (current_ma - 4.0) / 16.0
        return eng_min + ratio * (eng_max - eng_min)

    return voltage


def raw_display(raw, config, full_scale_v=4.096):
    value = engineering_value(raw, config, full_scale_v)
    if not np.isfinite(value):
        return "—"

    unit = channel_unit(config, "V")
    decimals = int(safe_float(config.get("decimais"), 2)) if config else 2
    decimals = max(0, min(4, decimals))
    return format_value(value, decimals, unit)


def pressure_bar_from_config(raw, config, full_scale_v=4.096):
    value = engineering_value(raw, config, full_scale_v)
    if not np.isfinite(value):
        return np.nan

    unit = str(channel_unit(config, "bar")).strip().lower()

    if unit in ("mca", "m.c.a.", "metros"):
        return value / MCA_PER_BAR

    if unit in ("bar",):
        return value

    return np.nan


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
    Lê os dispositivos do novo schema.
    Compatível com nome_exibicao/local e também com os campos antigos nome/local.
    """
    empty = pd.DataFrame(
        columns=[
            "device_id", "nome_exibicao", "nome", "local",
            "descricao", "ativo", "ordem", "adc_full_scale_v"
        ]
    )

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

        if "nome_exibicao" not in df.columns:
            df["nome_exibicao"] = None

        if "nome" not in df.columns:
            df["nome"] = None

        if "local" not in df.columns:
            df["local"] = "Sem local"

        if "descricao" not in df.columns:
            df["descricao"] = None

        if "ativo" not in df.columns:
            df["ativo"] = True

        if "ordem" not in df.columns:
            df["ordem"] = 999

        if "adc_full_scale_v" not in df.columns:
            df["adc_full_scale_v"] = 4.096

        df["nome_exibicao"] = (
            df["nome_exibicao"]
            .fillna(df["nome"])
            .fillna(df["device_id"])
        )
        df["nome"] = df["nome_exibicao"]

        df["local"] = (
            df["local"]
            .fillna("Sem local")
            .astype(str)
            .replace("", "Sem local")
        )

        df["ativo"] = df["ativo"].fillna(True).astype(bool)
        df["ordem"] = pd.to_numeric(df["ordem"], errors="coerce").fillna(999)
        df["adc_full_scale_v"] = pd.to_numeric(
            df["adc_full_scale_v"], errors="coerce"
        ).fillna(4.096)

        return df

    except Exception as exc:
        st.error("Erro ao carregar os dispositivos.")
        st.exception(exc)
        return empty


@st.cache_data(ttl=30)
def load_channel_configs():
    """
    Novo schema:
      public.configuracao_analogica
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
            key = (
                str(row.get("device_id", "")),
                str(row.get("canal", "")).upper(),
            )
            configs[key] = row

        return configs

    except Exception as exc:
        st.error("Erro ao carregar a configuração das entradas.")
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
        "status"
    ]

    if supabase is None:
        return pd.DataFrame(columns=columns)

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
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(data)

        for col in columns:
            if col not in df.columns:
                df[col] = np.nan

        df["recebido_em"] = pd.to_datetime(
            df["recebido_em"],
            utc=True,
            errors="coerce",
        )

        df = (
            df.sort_values("recebido_em", ascending=False)
            .drop_duplicates("device_id", keep="first")
            .reset_index(drop=True)
        )

        configs = load_channel_configs()
        devices = load_devices()

        device_full_scale = {}
        if not devices.empty:
            for _, d in devices.iterrows():
                device_full_scale[str(d["device_id"])] = safe_float(
                    d.get("adc_full_scale_v"), 4.096
                )

        global_config = load_global_config()

        def row_status(row):
            age = latest_age_seconds(row.get("recebido_em"))
            if age > OFFLINE_AFTER_SECONDS:
                return "Offline"

            device_id = str(row.get("device_id", ""))
            fs = device_full_scale.get(device_id, 4.096)

            # Pressão configurada
            pressure_cfg = configs.get((device_id, "AI004"), {})
            pressure = pressure_bar_from_config(
                row.get("ai004"),
                pressure_cfg,
                fs
            )
            p_min = safe_float(global_config.get("limite_pressao"))

            if np.isfinite(pressure) and np.isfinite(p_min) and pressure < p_min:
                return "Alarme"

            # Vibração
            vibration = [
                safe_float(row.get("x_mm_s")),
                safe_float(row.get("y_mm_s")),
                safe_float(row.get("z_mm_s")),
            ]
            vibration = [v for v in vibration if np.isfinite(v)]

            v_limit = safe_float(global_config.get("limite_rms"))
            if vibration and np.isfinite(v_limit) and max(vibration) > v_limit:
                return "Alarme"

            # Temperaturas por role configurada
            for canal, default_limit_key in [
                ("AI006", "limite_mancal"),
                ("AI007", "limite_oleo"),
            ]:
                cfg = configs.get((device_id, canal), {})
                role = str(cfg.get("role") or "").lower()

                if role not in ("bearing_temp", "oil_temp"):
                    continue

                value = engineering_value(
                    row.get(channel_field(canal)),
                    cfg,
                    fs,
                )
                limit = safe_float(global_config.get(default_limit_key))

                if np.isfinite(value) and np.isfinite(limit) and value > limit:
                    return "Alarme"

            return "Online"

        df["status"] = df.apply(row_status, axis=1)

        return df

    except Exception as exc:
        st.error("Erro ao carregar a telemetria.")
        st.exception(exc)
        return pd.DataFrame(columns=columns)


def build_devices_view():
    """
    Une a lista cadastrada em dispositivos com a última telemetria.
    Dispositivo cadastrado sem telemetria aparece como OFFLINE.
    Dispositivo que transmite mas ainda não está cadastrado também aparece,
    como 'Sem cadastro', para não esconder dados.
    """

    devices = load_devices()
    telemetry = load_telemetry()

    if devices.empty:
        if telemetry.empty:
            return pd.DataFrame()

        result = telemetry.copy()
        result["nome"] = result["device_id"]
        result["local"] = "Não configurado"
        result["descricao"] = None
        result["ordem"] = 999
        return result

    devices = devices[devices["ativo"] == True].copy()

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

    result["nome"] = (
        result["nome_device"]
        .fillna(result["device_id"])
        if "nome_device" in result.columns
        else result["device_id"]
    )

    result["local"] = (
        result["local_device"].fillna("Sem local")
        if "local_device" in result.columns
        else "Sem local"
    )

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

    result["status"] = result["status"].fillna("Offline")

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
            df["recebido_em"],
            utc=True,
            errors="coerce"
        )

        for col in [
            "ai001", "ai002", "ai003", "ai004",
            "ai005", "ai006", "ai007", "ai008",
            "x_mm_s", "y_mm_s", "z_mm_s",
            "x_rms", "y_rms", "z_rms"
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        configs = load_channel_configs()
        devices = load_devices()

        fs = 4.096
        if not devices.empty:
            d = devices[devices["device_id"].astype(str) == str(device_id)]
            if not d.empty:
                fs = safe_float(d.iloc[0].get("adc_full_scale_v"), 4.096)

        pressure_cfg = configs.get((str(device_id), "AI004"), {})
        df["pressao_bar"] = df["ai004"].apply(
            lambda raw: pressure_bar_from_config(raw, pressure_cfg, fs)
        )
        df["pressao_mca"] = df["pressao_bar"] * MCA_PER_BAR

        df["vibra"] = df[["x_mm_s", "y_mm_s", "z_mm_s"]].max(
            axis=1,
            skipna=True,
        )

        for canal in [f"AI{i:03d}" for i in range(1, 9)]:
            cfg = configs.get((str(device_id), canal), {})
            field = channel_field(canal)
            eng_name = f"{field}_eng"

            df[eng_name] = df[field].apply(
                lambda raw, c=cfg: engineering_value(raw, c, fs)
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

    config = load_global_config()
    channel_configs = load_channel_configs()
    devices = load_devices()

    for _, row in df.iterrows():
        device_id = str(row.get("device_id", "—"))
        when = row.get("recebido_em")

        fs = 4.096
        if not devices.empty:
            d = devices[devices["device_id"].astype(str) == device_id]
            if not d.empty:
                fs = safe_float(d.iloc[0].get("adc_full_scale_v"), 4.096)

        pressure_cfg = channel_configs.get((device_id, "AI004"), {})
        pressure = pressure_bar_from_config(
            row.get("ai004"),
            pressure_cfg,
            fs
        )

        p_limit = safe_float(config.get("limite_pressao"))

        if np.isfinite(pressure) and np.isfinite(p_limit) and pressure < p_limit:
            alarms.append({
                "Equipamento": device_id,
                "Grandeza": channel_display_name(pressure_cfg, "AI004"),
                "Valor": pressure,
                "Limite": p_limit,
                "Unidade": "bar",
                "Data/Hora": when,
            })

        v_limit = safe_float(config.get("limite_rms"))
        for axis in ["x", "y", "z"]:
            value = safe_float(row.get(f"{axis}_mm_s"))

            if np.isfinite(value) and np.isfinite(v_limit) and value > v_limit:
                alarms.append({
                    "Equipamento": device_id,
                    "Grandeza": f"Vibração {axis.upper()}",
                    "Valor": value,
                    "Limite": v_limit,
                    "Unidade": "mm/s RMS",
                    "Data/Hora": when,
                })

        for canal, limit_key in [
            ("AI006", "limite_mancal"),
            ("AI007", "limite_oleo"),
        ]:
            cfg = channel_configs.get((device_id, canal), {})
            role = str(cfg.get("role") or "").lower()

            value = engineering_value(
                row.get(channel_field(canal)),
                cfg,
                fs
            )
            limit = safe_float(config.get(limit_key))

            if (
                np.isfinite(value)
                and np.isfinite(limit)
                and value > limit
                and role in ("bearing_temp", "oil_temp")
            ):
                alarms.append({
                    "Equipamento": device_id,
                    "Grandeza": channel_display_name(cfg, canal),
                    "Valor": value,
                    "Limite": limit,
                    "Unidade": channel_unit(cfg, "°C"),
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

    config = load_global_config()
    configs = load_channel_configs()
    devices = load_devices()

    score = 100

    vibration = [
        safe_float(row.get("x_mm_s")),
        safe_float(row.get("y_mm_s")),
        safe_float(row.get("z_mm_s")),
    ]
    vibration = [v for v in vibration if np.isfinite(v)]

    vib_limit = safe_float(config.get("limite_rms"))
    if vibration and np.isfinite(vib_limit):
        peak = max(vibration)
        if peak > vib_limit:
            score -= 35
        elif peak > vib_limit * 0.7:
            score -= 15

    device_id = str(row.get("device_id", ""))
    fs = 4.096
    if not devices.empty:
        d = devices[devices["device_id"].astype(str) == device_id]
        if not d.empty:
            fs = safe_float(d.iloc[0].get("adc_full_scale_v"), 4.096)

    for canal, limit_key in [("AI006", "limite_mancal"), ("AI007", "limite_oleo")]:
        cfg = configs.get((device_id, canal), {})
        value = engineering_value(row.get(channel_field(canal)), cfg, fs)
        limit = safe_float(config.get(limit_key))

        if np.isfinite(value) and np.isfinite(limit):
            if value > limit:
                score -= 20
            elif value > limit * 0.9:
                score -= 10

    pressure_cfg = configs.get((device_id, "AI004"), {})
    pressure = pressure_bar_from_config(
        row.get("ai004"),
        pressure_cfg,
        fs,
    )
    p_limit = safe_float(config.get("limite_pressao"))

    if np.isfinite(pressure) and np.isfinite(p_limit) and pressure < p_limit:
        score -= 25

    return int(max(0, min(100, score)))


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
        load_telemetry.clear()
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
        load_telemetry.clear()
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

    fs = 4.096
    if not devices.empty:
        d = devices[devices["device_id"].astype(str) == str(device_id)]
        if not d.empty:
            fs = safe_float(d.iloc[0].get("adc_full_scale_v"), 4.096)

    pressure_cfg = channel_configs.get((str(device_id), "AI004"), {})
    pressure_bar = pressure_bar_from_config(
        row.get("ai004"),
        pressure_cfg,
        fs
    )

    data = [
        ["Parâmetro", "Valor"],
        ["Status", str(row.get("status", "—"))],
        [
            channel_display_name(pressure_cfg, "AI004"),
            format_value(pressure_bar, 2, "bar")
        ],
        [
            "Pressão",
            format_value(
                bar_to_mca(pressure_bar),
                2,
                "MCA"
            )
        ],
        [
            channel_display_name(
                channel_configs.get((str(device_id), "AI006"), {}),
                "AI006"
            ),
            raw_display(
                row.get("ai006"),
                channel_configs.get((str(device_id), "AI006"), {}),
                fs
            ),
        ],
        [
            channel_display_name(
                channel_configs.get((str(device_id), "AI007"), {}),
                "AI007"
            ),
            raw_display(
                row.get("ai007"),
                channel_configs.get((str(device_id), "AI007"), {}),
                fs
            ),
        ],
        [
            channel_display_name(
                channel_configs.get((str(device_id), "AI008"), {}),
                "AI008"
            ),
            raw_display(
                row.get("ai008"),
                channel_configs.get((str(device_id), "AI008"), {}),
                fs
            ),
        ],
        ["Vibração X", format_value(row.get("x_mm_s"), 3, "mm/s RMS")],
        ["Vibração Y", format_value(row.get("y_mm_s"), 3, "mm/s RMS")],
        ["Vibração Z", format_value(row.get("z_mm_s"), 3, "mm/s RMS")],
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

                        device_fs = safe_float(
                            row.get("adc_full_scale_v"),
                            4.096
                        )

                        pressure_cfg = channel_configs.get((device_id, "AI004"), {})
                        pressure_bar = pressure_bar_from_config(
                            row.get("ai004"),
                            pressure_cfg,
                            device_fs,
                        )
                        pressure_mca = (
                            bar_to_mca(pressure_bar)
                            if np.isfinite(pressure_bar)
                            else np.nan
                        )

                        last = row.get("recebido_em")
                        last_text = (
                            pd.to_datetime(last).strftime("%d/%m/%Y %H:%M:%S")
                            if pd.notna(last)
                            else "sem leitura"
                        )

                        def channel_metric(canal, default_unit):
                            cfg = channel_configs.get((device_id, canal), {})
                            label = channel_display_name(cfg, canal)
                            value = engineering_value(
                                row.get(channel_field(canal)),
                                cfg,
                                device_fs,
                            )
                            unit = channel_unit(cfg, default_unit)
                            decimals = int(safe_float(cfg.get("decimais"), 2))
                            return label, format_value(value, decimals, unit)

                        temp6_label, temp6_value = channel_metric("AI006", "V")
                        temp7_label, temp7_value = channel_metric("AI007", "V")
                        temp8_label, temp8_value = channel_metric("AI008", "V")

                        vibration_values = [
                            safe_float(row.get("x_mm_s")),
                            safe_float(row.get("y_mm_s")),
                            safe_float(row.get("z_mm_s")),
                        ]
                        vibration_values = [
                            x for x in vibration_values if np.isfinite(x)
                        ]
                        vibration_max = max(vibration_values) if vibration_values else np.nan

                        pressure_text = (
                            format_value(pressure_bar, 2, "bar")
                            if np.isfinite(pressure_bar)
                            else "—"
                        )
                        mca_text = (
                            format_value(pressure_mca, 1, "MCA")
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

            device_fs = safe_float(row.get("adc_full_scale_v"), 4.096)
            pressure_cfg = channel_configs.get((selected, "AI004"), {})
            pressure_bar = pressure_bar_from_config(
                row.get("ai004"),
                pressure_cfg,
                device_fs,
            )
            pressure_mca = (
                bar_to_mca(pressure_bar)
                if np.isfinite(pressure_bar)
                else np.nan
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    channel_display_name(pressure_cfg, "AI004"),
                    format_value(pressure_bar, 2, "bar"),
                )

            with c2:
                st.metric(
                    "Pressão",
                    format_value(pressure_mca, 1, "MCA"),
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
                        ["ai006_eng", "ai007_eng", "ai008_eng"],
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
                        "Entradas configuradas",
                        "Engenharia",
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
                            "adc_full_scale_v": 4.096,
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
                value=str(
                    device_row.get("nome_exibicao")
                    or device_row.get("nome")
                    or selected_device
                ),
            )

            location = st.text_input(
                "Local",
                value=str(device_row.get("local") or ""),
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

            adc_full_scale = st.number_input(
                "ADS1115 Full Scale (V)",
                min_value=0.256,
                max_value=6.144,
                value=float(
                    safe_float(device_row.get("adc_full_scale_v"), 4.096)
                ),
                step=0.256,
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
                    "adc_full_scale_v": float(adc_full_scale),
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
            "As entradas são configuradas por dispositivo. O AXION envia apenas "
            "o RAW do ADS1115; a escala, unidade e função são definidas aqui."
        )

        for canal_num in range(1, 9):
            canal = f"AI{canal_num:03d}"
            cfg = channel_configs.get((selected_device, canal), {})

            with st.expander(
                f"{canal} — {channel_display_name(cfg, canal)}",
                expanded=False,
            ):
                with st.form(f"channel_form_{selected_device}_{canal}"):

                    channel_name = st.text_input(
                        "Nome exibido",
                        value=str(
                            cfg.get("nome_exibicao")
                            or cfg.get("nome")
                            or canal
                        ),
                    )

                    role_options = {
                        "generic": "Genérico",
                        "pressure": "Pressão",
                        "bearing_temp": "Temperatura Mancal",
                        "oil_temp": "Temperatura Óleo",
                        "aux_temp": "Temperatura 3",
                    }

                    current_role = str(cfg.get("role") or "generic")
                    if current_role not in role_options:
                        current_role = "generic"

                    role = st.selectbox(
                        "Função",
                        list(role_options.keys()),
                        index=list(role_options.keys()).index(current_role),
                        format_func=lambda value: role_options[value],
                    )

                    mode_options = {
                        "raw_voltage": "RAW → Volts",
                        "linear_voltage": "Volts → escala linear",
                        "linear_raw": "RAW → escala linear",
                        "linear_4_20ma": "4-20 mA → escala de engenharia",
                        "disabled": "Desativada",
                    }

                    current_mode = str(cfg.get("modo") or "raw_voltage")
                    if current_mode not in mode_options:
                        current_mode = "raw_voltage"

                    mode = st.selectbox(
                        "Conversão",
                        list(mode_options.keys()),
                        index=list(mode_options.keys()).index(current_mode),
                        format_func=lambda value: mode_options[value],
                    )

                    channel_unit_value = st.text_input(
                        "Unidade",
                        value=str(cfg.get("unidade") or "V"),
                    )

                    active_channel = st.checkbox(
                        "Entrada ativa",
                        value=bool(cfg.get("ativo", True)),
                    )

                    c1, c2 = st.columns(2)

                    with c1:
                        source_min = st.number_input(
                            "Entrada mínima",
                            value=float(safe_float(cfg.get("source_min"), 0)),
                        )

                    with c2:
                        source_max = st.number_input(
                            "Entrada máxima",
                            value=float(safe_float(cfg.get("source_max"), 4.096)),
                        )

                    c3, c4 = st.columns(2)

                    with c3:
                        eng_min = st.number_input(
                            "Engenharia mínima",
                            value=float(safe_float(cfg.get("eng_min"), 0)),
                        )

                    with c4:
                        eng_max = st.number_input(
                            "Engenharia máxima",
                            value=float(safe_float(cfg.get("eng_max"), 4.096)),
                        )

                    c5, c6 = st.columns(2)

                    with c5:
                        shunt_ohms = st.number_input(
                            "Resistor shunt (Ω)",
                            min_value=1.0,
                            value=float(safe_float(cfg.get("shunt_ohms"), 150)),
                            disabled=mode != "linear_4_20ma",
                        )

                    with c6:
                        decimals = st.number_input(
                            "Casas decimais",
                            min_value=0,
                            max_value=4,
                            value=int(safe_float(cfg.get("decimais"), 2)),
                            step=1,
                        )

                    a1, a2 = st.columns(2)
                    with a1:
                        alarm_min = st.number_input(
                            "Alarme mínimo",
                            value=float(safe_float(cfg.get("alarme_min"), 0)),
                        )
                    with a2:
                        alarm_max = st.number_input(
                            "Alarme máximo",
                            value=float(safe_float(cfg.get("alarme_max"), 0)),
                        )

                    save_channel = st.form_submit_button(
                        "Salvar entrada",
                        type="primary",
                    )

                if save_channel:
                    payload = {
                        "nome_exibicao": channel_name.strip() or canal,
                        "role": role,
                        "modo": mode,
                        "unidade": channel_unit_value.strip() or "V",
                        "source_min": float(source_min),
                        "source_max": float(source_max),
                        "eng_min": float(eng_min),
                        "eng_max": float(eng_max),
                        "shunt_ohms": float(shunt_ohms),
                        "decimais": int(decimals),
                        "ativo": active_channel,
                        "alarme_min": float(alarm_min),
                        "alarme_max": float(alarm_max),
                    }

                    ok, error = update_channel(
                        selected_device,
                        canal,
                        payload,
                    )

                    if ok:
                        st.success(f"{canal} atualizado.")
                        st.rerun()
                    else:
                        st.error(
                            f"Não foi possível salvar {canal}."
                        )
                        st.code(error or "Erro desconhecido")

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
                "Limite temperatura mancal (°C)",
                value=float(
                    safe_float(load_global_config().get("limite_mancal"), 75.0)
                ),
                step=1.0,
            )

            oil_limit = st.number_input(
                "Limite temperatura óleo (°C)",
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
