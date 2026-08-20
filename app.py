



import math
import io
import json
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
from core.constants import REFRESH_SECONDS, OFFLINE_AFTER_SECONDS, MCA_PER_BAR
from ui.theme import apply_theme
from core.session import (
    get_supabase_config,
    get_authenticated_supabase,
    get_current_user_profile,
    allowed_profiles,
    logout,
)
from services.data import (
    set_supabase_client,
    get_supabase,
    build_devices_view,
    load_channel_configs,
    load_locations,
)
from pages.dashboard import render_dashboard
from pages.details import render_details
from pages.reports import render_reports
from pages.users import render_users
from pages.configuration import render_configuration
from ui.login import render_login

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

# ============================================================
# SUPABASE
# ============================================================

supabase = None

# ============================================================
# ESTADO
# ============================================================

if "view" not in st.session_state:
    st.session_state.view = "dashboard"

if "device_id" not in st.session_state:
    st.session_state.device_id = None

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now().timestamp()

if "auth_session" not in st.session_state:
    st.session_state.auth_session = None

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None

if "users_feedback" not in st.session_state:
    st.session_state.users_feedback = None


# ============================================================
# AUTENTICAÇÃO
# ============================================================







# ============================================================
# LOGIN
# ============================================================

if not st.session_state.auth_session:
    render_login()
    st.stop()


st.session_state.user_profile = (
    st.session_state.user_profile
    or get_current_user_profile()
)

if not st.session_state.user_profile:
    logout()

if not bool(
    st.session_state.user_profile.get(
        "ativo",
        True,
    )
):
    logout()

supabase = get_authenticated_supabase()
set_supabase_client(supabase)

apply_theme()


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
        :root { --page:#f4f6f8; --surface:#fff; --border:#d8dee6; --text:#1f2937; --muted:#6f7b8b; --blue:#536fca; --green:#39b985; --red:#e45b63; --shadow:0 5px 18px rgba(31,41,55,.055); }
        *{box-sizing:border-box}
        .stApp{background:linear-gradient(180deg,#f8fafc 0%,#f2f5f7 100%);color:var(--text)}
        .block-container{max-width:1500px;padding:.8rem 1rem 2rem}
        [data-testid="stHeader"]{display:none}
        .top-card{background:#fff;border:1px solid var(--border);border-radius:14px;padding:.85rem 1rem;box-shadow:var(--shadow)}
        .brand-title{color:#162033;font-size:1.25rem;font-weight:900;line-height:1.05;letter-spacing:-.025em}.brand-accent{color:var(--blue)}.brand-sub{margin-top:.3rem;color:#7a8594;font-size:.68rem;font-weight:650}
        div.stButton>button{width:100%;min-height:42px;border-radius:10px;border:1px solid #c8d0da;background:#fff;color:#344054;font-weight:750;font-size:.79rem;box-shadow:0 2px 6px rgba(31,41,55,.035)}
        div.stButton>button:hover{background:#f4f7fc;border-color:#8ca2d7;color:#234a9f}
        div.stButton>button[kind="primary"]{background:#536fca;border-color:#536fca;color:#fff;box-shadow:0 4px 12px rgba(83,111,201,.18)}
        div.stButton>button p{color:inherit!important;font-weight:750!important}
        .page-kicker{color:#7a8594;font-size:.64rem;font-weight:850;text-transform:uppercase;letter-spacing:.11em}.page-title,h1,h2,h3{color:#1c2635!important;letter-spacing:-.03em}.page-title{margin-top:.1rem;margin-bottom:.55rem;font-size:1.5rem;font-weight:900}
        .muted{color:#7b8594!important}.small{color:#7c8796!important;font-size:.67rem;font-weight:800}
        .kpi{background:#fff;border:1px solid var(--border);border-radius:13px;padding:.8rem .95rem;min-height:82px;box-shadow:var(--shadow)}.kpi-value{color:#182233;font-size:1.72rem;line-height:1;font-weight:900}
        .location-title{margin-top:1rem;margin-bottom:.55rem;color:#2f3a4a;font-size:.81rem;font-weight:850}.location-title::before{content:"";display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:#657fd1;vertical-align:middle}
        [data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border:1px solid #d9dfe6!important;border-radius:15px!important;box-shadow:var(--shadow)}
        [data-testid="stVerticalBlockBorderWrapper"]>div{padding-top:.65rem!important;padding-bottom:.65rem!important}[data-testid="stVerticalBlockBorderWrapper"] h3{color:#162033!important;font-size:1.16rem!important;font-weight:900!important}[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stCaptionContainer"]{color:#798594!important}[data-testid="stVerticalBlockBorderWrapper"] hr{border-color:#e5e8ed!important;margin:.55rem 0 .7rem!important}
        [data-testid="stMetricLabel"]{color:#707c8b!important;font-size:.65rem!important;font-weight:800!important}[data-testid="stMetricValue"]{color:#172131!important;font-size:1.05rem!important;font-weight:900!important}[data-testid="stMetricDelta"]{color:#7b8594!important;font-size:.64rem!important}
        .pill-online,.pill-offline,.pill-alarm{display:inline-flex;align-items:center;padding:.3rem .58rem;border-radius:999px;font-size:.63rem;font-weight:850}.pill-online{color:#21825b;background:#e6f7ef;border:1px solid #bce7d1}.pill-offline{color:#5f6b79;background:#f1f3f5;border:1px solid #dfe4e9}.pill-alarm{color:#b43b44;background:#fdebec;border:1px solid #f2c4c7}
        .compact-gauge{width:100%;background:#fff;border:1px solid #e0e5eb;border-radius:12px;padding:.42rem .56rem .38rem;box-shadow:0 2px 9px rgba(31,41,55,.035)}
        .compact-gauge-head{display:flex;align-items:baseline;justify-content:space-between;gap:.55rem}
        .compact-gauge-title{color:#4a586a;font-size:.86rem;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .compact-gauge-value{color:#172132;font-size:1.18rem;font-weight:900;white-space:nowrap}
        .compact-gauge-track{height:7px;margin-top:.34rem;border-radius:999px;background:#e7ebef;overflow:hidden}
        .compact-gauge-fill{height:100%;border-radius:999px;min-width:2%}
        .compact-gauge-range{display:flex;justify-content:space-between;margin-top:.24rem;color:#657183;font-size:.58rem;font-weight:800}
        div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,textarea,input{background:#fff!important;color:#1f2937!important;border-color:#cbd4de!important}div[data-baseweb="select"] span,div[data-baseweb="select"] input{color:#1f2937!important}
        [data-testid="stForm"] label,[data-testid="stForm"] label p,[data-testid="stForm"] label span{color:#4c5665!important;font-weight:750!important}[data-testid="stExpander"]{background:#fff;border:1px solid #d9dfe6;border-radius:11px}[data-testid="stExpander"] summary{color:#263242!important;font-weight:800!important}

                        .top-brand-title span{
            color:#536fca;
        }

                        [data-testid="stHorizontalBlock"] .stButton button{
            min-width:38px;
            padding:.35rem .25rem !important;
            font-size:1rem !important;
        }


        /* ========================================================
           AXION — cabeçalho principal
           ======================================================== */

        .axion-brand-line{
            min-height:42px;
            display:flex;
            align-items:center;
            gap:.34rem;
            padding:.22rem 0;
            white-space:nowrap;
        }

        .axion-brand-mark{
            display:inline-flex;
            align-items:center;
            justify-content:center;
            width:26px;
            height:26px;
            border-radius:8px;
            background:#385474;
            color:#ffffff;
            font-size:.78rem;
            font-weight:900;
            box-shadow:0 2px 8px rgba(56,84,116,.18);
        }

        .axion-brand-name{
            color:#172132;
            font-size:1.10rem;
            font-weight:900;
            letter-spacing:-.035em;
        }

        .axion-brand-separator{
            color:#a0a9b5;
            font-size:.95rem;
        }

        .axion-brand-title{
            color:#536fca;
            font-size:.94rem;
            font-weight:800;
        }

        [data-testid="stHorizontalBlock"] div.stButton>button{
            min-height:42px;
            padding:.35rem .45rem !important;
            border-radius:10px !important;
            font-size:.69rem !important;
            font-weight:850 !important;
        }

        [data-testid="stHorizontalBlock"] div.stButton>button[kind="primary"]{
            background:#385474 !important;
            border-color:#385474 !important;
            color:#ffffff !important;
            box-shadow:0 3px 9px rgba(56,84,116,.14);
        }

        [data-testid="stHorizontalBlock"] div.stButton>button[kind="secondary"]{
            background:#ffffff !important;
            border-color:#d7dee7 !important;
            color:#385474 !important;
        }

        [data-testid="stHorizontalBlock"] div.stButton>button:hover{
            border-color:#8da0b2 !important;
            background:#f6f8fa !important;
        }

        .account-line{
            min-height:38px;
            display:flex;
            align-items:center;
            gap:.48rem;
            padding:.18rem .40rem;
            color:#344054;
            font-size:.69rem;
        }

        .account-line span{
            padding:.15rem .40rem;
            border-radius:999px;
            background:#eef2ff;
            border:1px solid #dce4ff;
            color:#536fca;
            font-size:.56rem;
            font-weight:850;
        }

        @media(max-width:900px){
            .axion-brand-line{
                min-height:38px;
            }

            .axion-brand-title{
                font-size:.78rem;
            }

            .axion-brand-name{
                font-size:1rem;
            }
        }

{.block-container{padding:.55rem .5rem 1.2rem}.brand-title{font-size:1.08rem}.page-title{font-size:1.3rem}.kpi{min-height:76px}.kpi-value{font-size:1.42rem}}
        [data-testid="stPlotlyChart"]{
            background:#ffffff!important;
            border:1px solid #dfe4ea!important;
            border-radius:14px!important;
            padding:.35rem .35rem .15rem!important;
            box-shadow:0 3px 12px rgba(31,41,55,.035);
        }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# AUXILIARES
# ============================================================






































# ============================================================
# CONFIGURAÇÕES DO BANCO
# ============================================================











# ============================================================
# TELEMETRIA
# ============================================================










# ============================================================
# ALARMES
# ============================================================




# ============================================================
# GRÁFICOS
# ============================================================







# ============================================================
# ATUALIZAÇÃO DE CONFIGURAÇÃO
# ============================================================













# ============================================================
# RELATÓRIO PDF
# ============================================================



# ============================================================
# NAVEGAÇÃO
# ============================================================

# ============================================================
# CABEÇALHO / NAVEGAÇÃO
# ============================================================

profile = st.session_state.user_profile or {}
current_user_name = str(
    profile.get("nome")
    or profile.get("email")
    or "Usuário"
)
current_user_role = str(
    profile.get("perfil")
    or "Operador"
)

# ============================================================
# CABEÇALHO / NAVEGAÇÃO
# ============================================================

profile = st.session_state.user_profile or {}

current_user_name = str(
    profile.get("nome")
    or profile.get("email")
    or "Usuário"
)

current_user_role = str(
    profile.get("perfil")
    or "Operador"
)

brand_col, home_col, details_col, reports_col, config_col, account_col = st.columns(
    [4.5, 1, 1, 1, 1, 1],
    gap="small",
)

with brand_col:
    brand_html = (
        '<div class="axion-brand-line">'
        '<span class="axion-brand-mark">◈</span>'
        '<span class="axion-brand-name">AXION</span>'
        '<span class="axion-brand-separator">|</span>'
        '<span class="axion-brand-title">Monitoramento Industrial</span>'
        '</div>'
    )

    st.markdown(
        brand_html,
        unsafe_allow_html=True,
    )

with home_col:
    if st.button(
        "⌂  Início",
        key="nav_dashboard",
        help="Dashboard",
        width="stretch",
        type="primary"
        if st.session_state.view == "dashboard"
        else "secondary",
    ):
        st.session_state.view = "dashboard"
        st.rerun()

with details_col:
    if st.button(
        "▤  Detalhes",
        key="nav_details",
        help="Detalhes dos equipamentos",
        width="stretch",
        type="primary"
        if st.session_state.view == "details"
        else "secondary",
    ):
        st.session_state.view = "details"
        st.rerun()

with reports_col:
    if st.button(
        "▥  Relatórios",
        key="nav_reports",
        help="Relatórios de serviço",
        width="stretch",
        type="primary"
        if st.session_state.view == "reports"
        else "secondary",
    ):
        st.session_state.view = "reports"
        st.rerun()

with config_col:
    if allowed_profiles(
        "Administrador",
        "Gerente",
        "Técnico",
    ):
        if st.button(
            "⚙  Configuração",
            key="nav_config",
            help="Configurações",
            width="stretch",
            type="primary"
            if st.session_state.view == "config"
            else "secondary",
        ):
            st.session_state.view = "config"
            st.rerun()

with account_col:
    if st.button(
        "●  Conta",
        key="nav_account",
        help=f"{current_user_name} • {current_user_role}",
        width="stretch",
    ):
        st.session_state.show_account_menu = not st.session_state.get(
            "show_account_menu",
            False,
        )

if st.session_state.get("show_account_menu", False):
    account_user_col, account_users_col, account_logout_col = st.columns(
        [5, 1.2, 1],
        gap="small",
    )

    with account_user_col:
        account_html = (
            '<div class="account-line">'
            f'<b>{current_user_name}</b>'
            f'<span>{current_user_role}</span>'
            '</div>'
        )

        st.markdown(
            account_html,
            unsafe_allow_html=True,
        )

    with account_users_col:
        if allowed_profiles("Administrador"):
            if st.button(
                "Usuários",
                key="account_users",
                width="stretch",
            ):
                st.session_state.view = "users"
                st.session_state.show_account_menu = False
                st.rerun()

    with account_logout_col:
        if st.button(
            "Sair",
            key="account_logout",
            width="stretch",
        ):
            logout()

# ============================================================
# DADOS ATUAIS
# ============================================================

device_rows = build_devices_view()
channel_configs = load_channel_configs()






# ============================================================
# DASHBOARD
# ============================================================


# ============================================================
# DADOS ATUAIS
# ============================================================

device_rows = build_devices_view()
channel_configs = load_channel_configs()
locations = load_locations()


# ============================================================
# PÁGINAS
# ============================================================

if st.session_state.view == "dashboard":
    render_dashboard(
        device_rows,
        channel_configs,
        locations,
    )

elif st.session_state.view == "details":
    render_details(
        device_rows,
        channel_configs,
    )

elif st.session_state.view == "reports":
    render_reports(
        device_rows,
        channel_configs,
    )

elif st.session_state.view == "users":
    render_users()

elif st.session_state.view == "config":
    render_configuration(
        channel_configs,
    )
