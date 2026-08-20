from core.constants import MCA_PER_BAR
from datetime import datetime, timezone, timedelta
import math
import numpy as np
import pandas as pd


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

