import numpy as np
import pandas as pd
import streamlit as st

from services.utils import *


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

