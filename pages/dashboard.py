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


def render_dashboard(device_rows, channel_configs, locations):
    supabase = get_supabase()


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
                            width="stretch",
                        ):
                            st.session_state.device_id = device_id
                            st.session_state.view = "details"
                            st.rerun()


    # ============================================================
    # DETALHES
    # ============================================================

