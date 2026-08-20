import numpy as np
import pandas as pd
from .utils import *


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

