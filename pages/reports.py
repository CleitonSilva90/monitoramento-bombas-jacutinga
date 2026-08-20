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


def render_reports(device_rows, channel_configs):
    supabase = get_supabase()


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
                        width="stretch",
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
                        width="stretch",
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
                            width="stretch",
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
                        width="stretch",
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
                    width="stretch",
                )

    # ============================================================
    # CONFIGURAÇÃO
    # ============================================================

