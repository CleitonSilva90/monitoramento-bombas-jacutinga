import io
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
)

from core.constants import *
from .utils import *
from .data import *
from .analog_inputs import *


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

