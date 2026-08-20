import io
import json
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
)

from core.constants import *
from core.session import allowed_profiles
from services.utils import *
from services.analog_inputs import *
from services.data import *
from services.analytics import *
from services.reports import *
from ui.components import *


def render_details(device_rows, channel_configs):
    supabase = get_supabase()


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
                    width="stretch",
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
                    width="stretch",
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
                            width="stretch",
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
                            width="stretch",
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

