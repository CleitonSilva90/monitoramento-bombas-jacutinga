from datetime import datetime, timezone, timedelta
import json
import math
import numpy as np
import pandas as pd
import streamlit as st
from supabase import create_client

from core.constants import *
from .utils import *
from .analog_inputs import *


_supabase_client = None

def set_supabase_client(client):
    global _supabase_client
    _supabase_client = client

def get_supabase():
    return _supabase_client

@st.cache_data(ttl=60)
def load_locations():
    supabase = get_supabase()
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
    supabase = get_supabase()
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
    supabase = get_supabase()
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
    supabase = get_supabase()
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
    supabase = get_supabase()
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


@st.cache_data(ttl=10)
def load_telemetry():
    supabase = get_supabase()
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
    supabase = get_supabase()
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
    supabase = get_supabase()
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
    supabase = get_supabase()
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


def get_current_device_alarms(row):
    supabase = get_supabase()
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
    supabase = get_supabase()
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


def update_channel(device_id, canal, payload):
    supabase = get_supabase()
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
    supabase = get_supabase()
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

