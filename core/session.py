import streamlit as st
from supabase import create_client
from .config import get_supabase_config


def get_authenticated_supabase():
    session = st.session_state.get("auth_session")

    if not session:
        return None

    url, key = get_supabase_config()

    if not url or not key:
        return None

    try:
        client = create_client(url, key)
        client.auth.set_session(
            session["access_token"],
            session["refresh_token"],
        )
        return client
    except Exception:
        return None


def get_current_user_profile():
    client = get_authenticated_supabase()

    if client is None:
        return None

    try:
        refresh_result = client.auth.refresh_session()

        if refresh_result and refresh_result.session:
            st.session_state.auth_session = {
                "access_token": refresh_result.session.access_token,
                "refresh_token": refresh_result.session.refresh_token,
            }

            client = get_authenticated_supabase()

        user = client.auth.get_user().user

        response = (
            client
            .table("perfis_usuarios")
            .select("id,nome,email,perfil,ativo")
            .eq("id", user.id)
            .limit(1)
            .execute()
        )

        rows = response.data or []
        return rows[0] if rows else None

    except Exception:
        return None


def allowed_profiles(*profiles):
    profile = st.session_state.get("user_profile")

    if not profile or not bool(profile.get("ativo", True)):
        return False

    current = str(
        profile.get("perfil", "")
    ).strip().lower()

    return current in {
        str(item).strip().lower()
        for item in profiles
    }


def logout():
    try:
        client = get_authenticated_supabase()
        if client is not None:
            client.auth.sign_out()
    except Exception:
        pass

    st.session_state.auth_session = None
    st.session_state.user_profile = None
    st.cache_data.clear()
    st.session_state.view = "dashboard"
    st.rerun()

