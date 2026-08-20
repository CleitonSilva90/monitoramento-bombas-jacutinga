import base64
from pathlib import Path

import streamlit as st
from supabase import create_client

from core.session import get_supabase_config

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BACKGROUND = ASSETS / "axion-login-background.png"


def _background_data_uri() -> str:
    """
    Embeds the login background directly in the page.
    This avoids browser/static-file path problems with Streamlit CSS.
    """
    if not BACKGROUND.exists():
        return ""

    encoded = base64.b64encode(BACKGROUND.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_login() -> None:
    background_uri = _background_data_uri()

    if background_uri:
        background_css = (
            "background-image:"
            "linear-gradient(rgba(1,7,18,.18), rgba(1,7,18,.24)),"
            f"url('{background_uri}');"
            "background-size:cover;"
            "background-position:center center;"
            "background-repeat:no-repeat;"
            "background-attachment:fixed;"
        )
    else:
        background_css = (
            "background:"
            "radial-gradient(circle at 50% 42%, rgba(16,112,255,.16), transparent 31%),"
            "linear-gradient(135deg,#020612 0%,#061426 50%,#020918 100%);"
        )

    st.markdown(
        f"""
<style>
/* ==========================================================
   AXION LOGIN V10
   Fundo embutido como data URI + card verdadeiramente central.
   ========================================================== */

[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stSidebar"] {{
    display:none !important;
}}

[data-testid="stAppViewContainer"],
[data-testid="stApp"] {{
    min-height:100vh !important;
    {background_css}
}}

.block-container {{
    max-width:100% !important;
    min-height:100vh !important;
    padding:0 !important;
    margin:0 !important;
}}

/* Escurecimento muito leve para manter o card legível */
[data-testid="stAppViewContainer"]::before {{
    content:"";
    position:fixed;
    inset:0;
    pointer-events:none;
    background:linear-gradient(
        180deg,
        rgba(0,5,16,.08) 0%,
        rgba(0,7,18,.04) 48%,
        rgba(0,5,14,.22) 100%
    );
}}

/* ---------- topo ---------- */
.axion-login-top {{
    position:relative;
    z-index:20;
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding:18px 36px 0;
}}

.axion-brand-top {{
    color:#ffffff;
    font-size:14px;
    font-weight:800;
    letter-spacing:.02em;
    text-shadow:0 1px 12px rgba(0,0,0,.55);
}}

.axion-brand-top span {{
    color:#49baff;
}}

.axion-online {{
    display:inline-flex;
    align-items:center;
    gap:8px;
    color:#ffffff;
    background:rgba(2,10,23,.54);
    border:1px solid rgba(21,142,255,.72);
    border-radius:9px;
    padding:8px 12px;
    font-size:11px;
    font-weight:700;
    box-shadow:0 8px 24px rgba(0,0,0,.20);
    backdrop-filter:blur(7px);
}}

.axion-online-dot {{
    width:8px;
    height:8px;
    border-radius:50%;
    background:#22e76e;
    box-shadow:0 0 12px rgba(34,231,110,.85);
}}

/* ---------- centralização ---------- */
/*
   A coluna do Streamlit gera espaço próprio. Usamos margin-top negativo
   e transform para posicionar o card no centro visual sem criar scroll.
*/
.axion-login-center {{
    position:relative;
    z-index:10;
    width:100%;
    margin-top:0;
    transform:translateY(-58px);
}}

[data-testid="stHorizontalBlock"] {{
    align-items:flex-start !important;
}}

[data-testid="stColumn"] {{
    overflow:visible !important;
}}

/* ---------- card ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker) {{
    width:min(430px, calc(100vw - 32px)) !important;
    margin:0 auto !important;
    padding:26px 30px 22px !important;

    background:
        linear-gradient(
            180deg,
            rgba(5,20,40,.90),
            rgba(1,10,24,.94)
        ) !important;

    border:1px solid rgba(25,145,255,.88) !important;
    border-radius:20px !important;

    box-shadow:
        0 24px 72px rgba(0,0,0,.48),
        0 0 40px rgba(10,120,255,.12),
        inset 0 1px 0 rgba(255,255,255,.04) !important;

    backdrop-filter:blur(10px);
}}

[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stVerticalBlock"] {{
    gap:.22rem !important;
}}

/* ---------- nome AXION ---------- */
.axion-card-name {{
    text-align:center;
    color:#ffffff;
    font-size:34px;
    font-weight:900;
    letter-spacing:.045em;
    line-height:1;
    margin:0 0 7px;
    text-shadow:
        0 0 16px rgba(44,167,255,.16),
        0 1px 3px rgba(0,0,0,.50);
}}

.axion-card-name span {{
    color:#21a4ff;
}}

.axion-card-subtitle {{
    text-align:center;
    color:#d0deec;
    font-size:10px;
    font-weight:700;
    letter-spacing:.11em;
    text-transform:uppercase;
    margin-bottom:15px;
}}

.axion-login-kicker {{
    text-align:center;
    color:#68cbff;
    font-size:8px;
    font-weight:800;
    text-transform:uppercase;
    letter-spacing:.18em;
    margin-bottom:5px;
}}

.axion-login-title {{
    text-align:center;
    color:#ffffff;
    font-size:17px;
    font-weight:800;
    line-height:1.25;
    margin-bottom:12px;
}}

/* ---------- inputs ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stForm"] {{
    border:0 !important;
    padding:0 !important;
    background:transparent !important;
}}

[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stTextInput"] {{
    margin-bottom:7px !important;
}}

[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stTextInput"] label,
[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stTextInput"] label p,
[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stTextInput"] label span {{
    color:#f4f8fc !important;
    font-size:12px !important;
    font-weight:700 !important;
}}

[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stTextInput"] input {{
    min-height:45px !important;
    background:rgba(3,14,28,.90) !important;
    color:#ffffff !important;
    border:1px solid rgba(92,135,172,.85) !important;
    border-radius:10px !important;
    font-size:14px !important;
}}

[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stTextInput"] input:focus {{
    border-color:#1598ff !important;
    box-shadow:0 0 0 2px rgba(21,152,255,.17) !important;
}}

[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    [data-testid="stTextInput"] input::placeholder {{
    color:#9ab0c2 !important;
}}

/* ---------- botão ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    div.stFormSubmitButton > button {{
    width:100% !important;
    min-height:45px !important;
    margin-top:5px !important;
    border-radius:10px !important;
    border:1px solid #1ba1ff !important;
    background:linear-gradient(90deg,#075df2,#159fff) !important;
    color:#ffffff !important;
    font-size:14px !important;
    font-weight:800 !important;
    box-shadow:0 8px 23px rgba(7,126,255,.22) !important;
}}

[data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker)
    div.stFormSubmitButton > button:hover {{
    filter:brightness(1.08);
}}

.axion-security {{
    text-align:center;
    color:#c2cfdb;
    font-size:10px;
    margin-top:8px;
}}

.axion-security span {{
    color:#2daeff;
    font-weight:800;
}}

@media (max-width:760px) {{
    .axion-login-top {{
        padding:14px 14px 0;
    }}

    .axion-brand-top {{
        font-size:12px;
    }}

    .axion-online {{
        padding:7px 9px;
        font-size:10px;
    }}

    .axion-login-center {{
        transform:translateY(-18px);
    }}

    [data-testid="stVerticalBlockBorderWrapper"]:has(.axion-card-marker) {{
        width:calc(100vw - 24px) !important;
        padding:23px 20px 20px !important;
    }}

    .axion-card-name {{
        font-size:31px;
    }}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="axion-login-top">
  <div class="axion-brand-top">
    AXION <span>| Monitoramento Industrial</span>
  </div>
  <div class="axion-online">
    <span class="axion-online-dot"></span>
    Sistema Online
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.02, 1], gap="small")

    with center:
        st.markdown('<div class="axion-login-center">', unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<span class="axion-card-marker"></span>', unsafe_allow_html=True)

            st.markdown(
                """
<div class="axion-card-name">AX<span>ION</span></div>
<div class="axion-card-subtitle">Monitoramento Industrial</div>
<div class="axion-login-kicker">Acesso seguro</div>
<div class="axion-login-title">Entre para acessar o monitoramento</div>
""",
                unsafe_allow_html=True,
            )

            with st.form("login_form"):
                email = st.text_input(
                    "E-mail",
                    placeholder="usuario@empresa.com",
                    key="login_email",
                )
                password = st.text_input(
                    "Senha",
                    type="password",
                    key="login_password",
                )
                submitted = st.form_submit_button("Entrar")

            st.markdown(
                '<div class="axion-security">'
                'Acesso seguro e protegido pelo <span>AXION</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        if not email.strip() or not password:
            st.error("Informe e-mail e senha.")
            return

        try:
            url, key = get_supabase_config()
            client = create_client(url, key)

            response = client.auth.sign_in_with_password(
                {
                    "email": email.strip(),
                    "password": password,
                }
            )

            session = response.session
            if not session:
                raise RuntimeError("O Supabase não retornou uma sessão.")

            st.session_state.auth_session = {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
            }

            st.cache_data.clear()
            st.session_state.user_profile = None
            st.rerun()

        except Exception:
            st.error("Não foi possível entrar. Verifique o e-mail e a senha.")
