import streamlit as st
from supabase import create_client


@st.cache_resource
def get_supabase_config():
    try:
        return (
            st.secrets["supabase_url"],
            st.secrets["supabase_key"],
        )
    except Exception as exc:
        st.error(
            f"Não foi possível carregar a configuração do Supabase: {exc}"
        )
        return None, None

