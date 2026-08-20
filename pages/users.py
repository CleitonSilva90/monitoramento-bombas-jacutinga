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


def render_users():
    supabase = get_supabase()


    if not allowed_profiles("Administrador"):
        st.error("Acesso restrito ao Administrador.")
        st.stop()

    st.markdown(
        "<div class='page-kicker'>Administração</div>"
        "<div class='page-title'>Usuários</div>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Gerencie usuários, perfis, ativação e redefinição de senha."
    )

    if st.session_state.get("users_feedback"):
        feedback = st.session_state.pop(
            "users_feedback"
        )

        feedback_type = str(
            feedback.get("type", "success")
        )

        feedback_message = str(
            feedback.get("message", "")
        )

        if feedback_type == "error":
            st.error(
                feedback_message
            )
        else:
            st.success(
                feedback_message
            )

    with st.expander("➕ Cadastrar usuário", expanded=False):

        with st.form("create_user_form"):

            user_name = st.text_input(
                "Nome",
                placeholder="Ex.: João da Silva",
            )

            user_email = st.text_input(
                "E-mail",
                placeholder="usuario@empresa.com",
            )

            user_password = st.text_input(
                "Senha inicial",
                type="password",
            )

            user_role = st.selectbox(
                "Perfil",
                [
                    "Operador",
                    "Técnico",
                    "Gerente",
                    "Administrador",
                ],
            )

            create_user = st.form_submit_button(
                "Criar usuário",
                type="primary",
            )

        if create_user:

            if not user_name.strip():
                st.error("Informe o nome.")

            elif not user_email.strip():
                st.error("Informe o e-mail.")

            elif len(user_password) < 8:
                st.error(
                    "A senha inicial deve ter pelo menos 8 caracteres."
                )

            else:

                try:

                    response = supabase.functions.invoke(
                        "admin-user-management",
                        {
                            "body": {
                                "action": "create",
                                "nome": user_name.strip(),
                                "email": user_email.strip(),
                                "password": user_password,
                                "perfil": user_role,
                            }
                        },
                    )

                    data = getattr(response, "data", None)

                    if isinstance(data, str):
                        data = json.loads(data)

                    if not isinstance(data, dict) or not data.get("ok"):
                        raise RuntimeError(
                            data.get("error")
                            if isinstance(data, dict)
                            else "Resposta inválida."
                        )

                    st.session_state.users_feedback = {
                        "type": "success",
                        "message": (
                            f"Usuário {user_name.strip()} "
                            "foi criado com sucesso."
                        ),
                    }
                    st.rerun()

                except Exception as exc:

                    st.error("Não foi possível criar o usuário.")
                    st.caption(str(exc))

    try:

        users_response = (
            supabase
            .table("perfis_usuarios")
            .select("id,nome,email,perfil,ativo,created_at")
            .order("nome")
            .execute()
        )

        users = pd.DataFrame(
            users_response.data or []
        )

    except Exception as exc:

        st.error("Não foi possível carregar os usuários.")
        st.caption(str(exc))
        users = pd.DataFrame()

    if users.empty:

        st.info("Nenhum usuário cadastrado.")

    else:

        for _, user in users.iterrows():

            uid = str(user.get("id"))
            name = str(user.get("nome") or "")
            email = str(user.get("email") or "")
            role = str(user.get("perfil") or "Operador")
            active = bool(user.get("ativo", True))

            with st.container(border=True):

                left, right = st.columns([4, 1])

                with left:

                    st.markdown(f"### {name}")

                    st.caption(
                        f"{email} • {role} • "
                        f"{'Ativo' if active else 'Inativo'}"
                    )

                with right:

                    if st.button(
                        "Editar",
                        key=f"edit_{uid}",
                        width="stretch",
                    ):
                        st.session_state.edit_user_id = uid
                        st.rerun()

                    if st.button(
                        "Redefinir senha",
                        key=f"reset_{uid}",
                        width="stretch",
                    ):
                        st.session_state.reset_user_id = uid
                        st.session_state.reset_user_name = name
                        st.rerun()

                if (
                    st.session_state.get("edit_user_id")
                    == uid
                ):

                    with st.form(f"edit_user_{uid}"):

                        edited_role = st.selectbox(
                            "Perfil",
                            [
                                "Operador",
                                "Técnico",
                                "Gerente",
                                "Administrador",
                            ],
                            index=(
                                [
                                    "Operador",
                                    "Técnico",
                                    "Gerente",
                                    "Administrador",
                                ].index(role)
                                if role in [
                                    "Operador",
                                    "Técnico",
                                    "Gerente",
                                    "Administrador",
                                ]
                                else 0
                            ),
                        )

                        edited_active = st.checkbox(
                            "Usuário ativo",
                            value=active,
                        )

                        save_user_edit = st.form_submit_button(
                            "Salvar alterações",
                            type="primary",
                        )

                    if save_user_edit:

                        try:

                            response = supabase.functions.invoke(
                                "admin-user-management",
                                {
                                    "body": {
                                        "action": "update_profile",
                                        "user_id": uid,
                                        "perfil": edited_role,
                                        "ativo": edited_active,
                                    }
                                },
                            )

                            data = getattr(response, "data", None)

                            if isinstance(data, str):
                                data = json.loads(data)

                            if not isinstance(data, dict) or not data.get("ok"):
                                raise RuntimeError(
                                    data.get("error")
                                    if isinstance(data, dict)
                                    else "Resposta inválida."
                                )

                            st.session_state.users_feedback = {
                                "type": "success",
                                "message": (
                                    f"Usuário {name} foi atualizado "
                                    "com sucesso."
                                ),
                            }

                            st.session_state.pop(
                                "edit_user_id",
                                None,
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                "Não foi possível atualizar o usuário."
                            )
                            st.caption(str(exc))

                if (
                    st.session_state.get("reset_user_id")
                    == uid
                ):

                    with st.form(f"reset_password_{uid}"):

                        new_password = st.text_input(
                            "Nova senha",
                            type="password",
                        )

                        new_password_confirm = st.text_input(
                            "Confirmar nova senha",
                            type="password",
                        )

                        reset_submit = st.form_submit_button(
                            "Salvar nova senha",
                            type="primary",
                        )

                    if reset_submit:

                        if len(new_password) < 8:

                            st.error(
                                "A nova senha deve ter pelo menos 8 caracteres."
                            )

                        elif new_password != new_password_confirm:

                            st.error("As senhas não coincidem.")

                        else:

                            try:

                                response = supabase.functions.invoke(
                                    "admin-user-management",
                                    {
                                        "body": {
                                            "action": "reset_password",
                                            "user_id": uid,
                                            "password": new_password,
                                        }
                                    },
                                )

                                data = getattr(response, "data", None)

                                if isinstance(data, str):
                                    data = json.loads(data)

                                if not isinstance(data, dict) or not data.get("ok"):
                                    raise RuntimeError(
                                        data.get("error")
                                        if isinstance(data, dict)
                                        else "Resposta inválida."
                                    )

                                st.session_state.users_feedback = {
                                    "type": "success",
                                    "message": (
                                        f"Senha de {name} "
                                        "redefinida com sucesso."
                                    ),
                                }

                                st.session_state.pop(
                                    "reset_user_id",
                                    None,
                                )

                                st.rerun()

                            except Exception as exc:

                                st.error(
                                    "Não foi possível redefinir a senha."
                                )
                                st.caption(str(exc))

    st.stop()


