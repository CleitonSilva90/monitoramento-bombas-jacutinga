import streamlit as st
from pathlib import Path
import base64

AXION_NAVY = "#07121F"
AXION_NAVY_2 = "#10283F"
AXION_BLUE = "#168BFF"
AXION_CYAN = "#16C7F7"
AXION_BG = "#F4F7FA"
AXION_SURFACE = "#FFFFFF"
AXION_TEXT = "#122033"
AXION_MUTED = "#64748B"
AXION_BORDER = "#D9E2EC"

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

def apply_theme():
    st.markdown(f"""
    <style>
    :root {{
        --axion-navy:{AXION_NAVY};
        --axion-navy-2:{AXION_NAVY_2};
        --axion-blue:{AXION_BLUE};
        --axion-cyan:{AXION_CYAN};
        --axion-bg:{AXION_BG};
        --axion-surface:{AXION_SURFACE};
        --axion-text:{AXION_TEXT};
        --axion-muted:{AXION_MUTED};
        --axion-border:{AXION_BORDER};
    }}
    [data-testid="stAppViewContainer"] {{ background:var(--axion-bg); }}
    [data-testid="stHeader"] {{ background:transparent; }}
    .axion-topbar {{
      background:linear-gradient(90deg,var(--axion-navy),var(--axion-navy-2));
      border-bottom:1px solid rgba(255,255,255,.08);
      padding:10px 18px; display:flex; align-items:center; box-sizing:border-box;
    }}
    .axion-brand img {{ height:34px; width:auto; display:block; }}
    .axion-card {{
      background:var(--axion-surface); border:1px solid var(--axion-border);
      border-radius:14px; box-shadow:0 4px 18px rgba(15,23,42,.05);
    }}
    </style>
    """, unsafe_allow_html=True)

def render_brand_header():
    logo = ASSETS / "axion-wordmark.png"
    if not logo.exists():
        return
    encoded = base64.b64encode(logo.read_bytes()).decode("ascii")
    st.markdown(
        f'<div class="axion-topbar"><div class="axion-brand">'
        f'<img src="data:image/png;base64,{encoded}" alt="AXION | Monitoramento Industrial">'
        f'</div></div>',
        unsafe_allow_html=True,
    )
