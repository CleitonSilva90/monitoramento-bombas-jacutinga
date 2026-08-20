from datetime import datetime, timezone
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.constants import *
from .utils import *
from .data import *
from .analog_inputs import *


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

