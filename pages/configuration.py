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


def render_configuration(channel_configs):
    supabase = get_supabase()


    if not allowed_profiles(
        "Administrador",
        "Gerente",
        "Técnico",
    ):
        st.error(
            "Você não tem permissão para acessar esta área."
        )
        st.stop()



    st.markdown("## Configuração")

    devices = load_devices()

    st.markdown("### Locais")

    with st.expander("➕ Cadastrar novo local", expanded=False):
        with st.form("new_location_form"):
            location_name = st.text_input(
                "Nome do local",
                placeholder="Ex.: Estação Norte",
            )

            location_order = st.number_input(
                "Ordem de exibição",
                min_value=1,
                value=1,
                step=1,
            )

            create_location_button = st.form_submit_button(
                "Cadastrar local",
                type="primary",
            )

        if create_location_button:
            ok_location, location_error = create_location(
                location_name,
                int(location_order),
            )

            if ok_location:
                st.success(
                    f"Local '{location_name.strip()}' cadastrado."
                )
                st.rerun()
            else:
                st.error("Não foi possível cadastrar o local.")
                st.code(
                    location_error or "Erro desconhecido"
                )

    st.markdown("### Equipamentos")

    with st.expander("➕ Cadastrar novo equipamento", expanded=False):
        st.caption(
            "Primeiro conecte o AXION ao AXION Configurator e confirme o Device ID. "
            "Depois informe aqui exatamente esse identificador. O site criará o "
            "equipamento e as entradas AI001–AI008 automaticamente."
        )

        with st.form("new_device_form"):
            new_device_id = st.text_input(
                "Device ID do AXION",
                placeholder="Ex.: AXION-000002",
                help=(
                    "Use exatamente o Device ID exibido pelo AXION Configurator."
                ),
            )

            new_device_name = st.text_input(
                "Nome exibido",
                placeholder="Ex.: Bomba 02",
            )

            location_options = load_locations()
            location_choices = location_options + ["➕ Criar novo local"]

            new_device_location_choice = st.selectbox(
                "Local",
                location_choices,
            )

            if new_device_location_choice == "➕ Criar novo local":
                new_device_location = st.text_input(
                    "Nome do novo local",
                    placeholder="Ex.: Estação Norte",
                    help=(
                        "Cadastre o novo local. Ele ficará disponível "
                        "para os próximos equipamentos."
                    ),
                ).strip()
            else:
                new_device_location = new_device_location_choice

            new_device_description = st.text_input(
                "Descrição",
                placeholder="Ex.: Captação principal",
            )

            new_device_order = st.number_input(
                "Ordem",
                min_value=1,
                value=1,
                step=1,
            )

            new_device_active = st.checkbox(
                "Equipamento ativo",
                value=True,
            )

            create_device = st.form_submit_button(
                "Cadastrar equipamento",
                type="primary",
            )

        if create_device:
            device_id_value = new_device_id.strip()
            device_name_value = (
                new_device_name.strip()
                or device_id_value
            )

            if not device_id_value:
                st.error("Informe o Device ID.")

            elif supabase is None:
                st.error("Supabase indisponível.")

            else:
                try:
                    # --------------------------------------------
                    # 1. Verifica se o equipamento já existe.
                    # --------------------------------------------
                    existing = (
                        supabase
                        .table("dispositivos")
                        .select("device_id")
                        .eq("device_id", device_id_value)
                        .limit(1)
                        .execute()
                    )

                    if existing.data:
                        st.error(
                            f"O equipamento {device_id_value} já está cadastrado."
                        )
                    else:
                        # ----------------------------------------
                        # 2. Cria o local, quando necessário.
                        # ----------------------------------------
                        if new_device_location_choice == "➕ Criar novo local":
                            if not new_device_location:
                                st.error("Informe o nome do novo local.")
                                st.stop()

                            existing_location = (
                                supabase
                                .table("locais")
                                .select("id")
                                .eq("nome", new_device_location)
                                .limit(1)
                                .execute()
                            )

                            if existing_location.data:
                                st.error(
                                    f"O local '{new_device_location}' já está cadastrado."
                                )
                                st.stop()

                            ok_location, location_error = create_location(
                                new_device_location
                            )

                            if not ok_location:
                                st.error("Não foi possível criar o local.")
                                st.code(
                                    location_error or "Erro desconhecido"
                                )
                                st.stop()

                        # ----------------------------------------
                        # 3. Cria o dispositivo.
                        # ----------------------------------------
                        device_payload = {
                            "device_id": device_id_value,
                            "nome_exibicao": device_name_value,
                            "local": new_device_location,
                            "descricao": (
                                new_device_description.strip()
                                or None
                            ),
                            "ativo": new_device_active,
                            "ordem": int(new_device_order),
                            "adc_full_scale_v": 4.096,
                        }

                        device_response = (
                            supabase
                            .table("dispositivos")
                            .insert(device_payload)
                            .select("device_id")
                            .execute()
                        )

                        if not device_response.data:
                            raise RuntimeError(
                                "O Supabase não confirmou o cadastro do equipamento."
                            )

                        # ----------------------------------------
                        # 3. Cria automaticamente AI001...AI008.
                        # Começam desativadas e genéricas.
                        # ----------------------------------------
                        channel_rows = []

                        for canal_num in range(1, 9):
                            channel_rows.append({
                                "device_id": device_id_value,
                                "canal": canal_num,
                                "nome_exibicao": (
                                    f"AI{canal_num:03d}"
                                ),
                                "role": "generic",
                                "modo": "linear_voltage",
                                "unidade": "",
                                "source_min": 0.0,
                                "source_max": 3.0,
                                "eng_min": 0.0,
                                "eng_max": 100.0,
                                "shunt_ohms": 150.0,
                                "decimais": 2,
                                "ativo": False,
                                "exibir_gauge": True,
                                "alarme_min": None,
                                "alarme_max": None,
                                "tipo_entrada": "0–3 V",
                                "shunt_150r": False,
                            })

                        (
                            supabase
                            .table("configuracao_analogica")
                            .upsert(
                                channel_rows,
                                on_conflict="device_id,canal",
                            )
                            .execute()
                        )

                        load_devices.clear()
                        load_channel_configs.clear()
                        load_locations.clear()
                        load_telemetry.clear()

                        st.success(
                            f"{device_name_value} cadastrado com sucesso."
                        )

                        st.info(
                            "As AI001–AI008 foram criadas como inativas. "
                            "Configure as entradas desejadas na seção abaixo. "
                            "Depois, use o AXION Configurator para provisionar o "
                            "token e calibrar a vibração."
                        )

                        st.session_state.device_id = device_id_value
                        st.rerun()

                except Exception as exc:
                    st.error(
                        "Não foi possível cadastrar o equipamento."
                    )
                    st.code(
                        str(exc)
                    )


    if devices.empty:
        st.info(
            "Nenhum equipamento cadastrado ainda. "
            "Use 'Cadastrar novo equipamento' acima."
        )
    else:
        device_options = devices["device_id"].astype(str).tolist()

        selected_device = st.selectbox(
            "Equipamento",
            device_options,
        )

        device_row = devices[
            devices["device_id"].astype(str) == selected_device
        ].iloc[0]

        with st.form("device_form"):
            name = st.text_input(
                "Nome exibido",
                value=str(device_row.get("nome_exibicao") or device_row.get("nome") or selected_device),
            )

            location = st.text_input(
                "Local",
                value=str(device_row.get("local") or "Sem local"),
                help="Ex.: Jacutinga ou Intermédiaria",
            )

            description = st.text_input(
                "Descrição",
                value=str(device_row.get("descricao") or ""),
            )

            order = st.number_input(
                "Ordem",
                min_value=0,
                value=int(safe_float(device_row.get("ordem"), 999)),
                step=1,
            )

            active = st.checkbox(
                "Equipamento ativo",
                value=bool(device_row.get("ativo", True)),
            )

            save_device = st.form_submit_button(
                "Salvar equipamento",
                type="primary",
            )

        if save_device:
            ok, error = update_device(
                selected_device,
                {
                    "nome_exibicao": name.strip() or selected_device,
                    "local": location.strip() or "Sem local",
                    "descricao": description.strip() or None,
                    "ordem": int(order),
                    "ativo": active,
                },
            )

            if ok:
                st.success("Equipamento atualizado.")
                st.rerun()
            else:
                st.error(
                    "Não foi possível salvar o equipamento. "
                    "Verifique as políticas RLS da tabela dispositivos."
                )
                st.code(error or "Erro desconhecido")

        st.markdown("---")
        st.markdown("### Entradas analógicas")

        st.caption(
            "Cada entrada pode ser configurada como 0–3 V ou 4–20 mA. "
            "O shunt de 150 Ω é definido automaticamente pelo tipo elétrico."
        )

        UNIT_OPTIONS = [
            "Sem unidade",
            "bar",
            "MCA",
            "°C",
            "V",
            "%",
            "m",
            "mm",
            "mm/s RMS",
            "RPM",
            "A",
            "Hz",
        ]

        for canal_num in range(1, 9):
            canal = f"AI{canal_num:03d}"
            cfg = channel_configs.get(
                (selected_device, canal),
                {}
            )

            nome_atual = str(
                cfg.get("nome_exibicao")
                or cfg.get("nome")
                or canal
            )

            tipo_raw = str(
                cfg.get("tipo_entrada")
                or ""
            ).strip().lower()

            if (
                tipo_raw in {
                    "4-20ma",
                    "4–20ma",
                    "4–20 ma",
                    "4-20 ma",
                }
                or str(cfg.get("modo", "")).lower() == "linear_4_20ma"
            ):
                tipo_atual = "4–20 mA"
            else:
                tipo_atual = "0–3 V"

            unidade_atual = str(
                cfg.get("unidade") or "Sem unidade"
            )

            if unidade_atual not in UNIT_OPTIONS:
                unidade_atual = "Sem unidade"

            escala_min_atual = safe_float(
                cfg.get("eng_min"),
                0
            )

            escala_max_atual = safe_float(
                cfg.get("eng_max"),
                100
            )

            ativo_atual = bool(
                cfg.get("ativo", True)
            )

            exibir_gauge_atual = bool(
                cfg.get("exibir_gauge", True)
            )

            alarme_min_atual = cfg.get("alarme_min")
            alarme_max_atual = cfg.get("alarme_max")

            shunt_ligado = (
                tipo_atual == "4–20 mA"
            )

            with st.expander(
                f"{canal} — {nome_atual}",
                expanded=False,
            ):
                with st.form(
                    f"channel_form_{selected_device}_{canal}"
                ):

                    channel_name = st.text_input(
                        "Nome da função",
                        value=nome_atual,
                        help=(
                            "Digite livremente a função do sensor."
                        ),
                    )

                    tipo_entrada = st.selectbox(
                        "Tipo de entrada",
                        ["0–3 V", "4–20 mA"],
                        index=(
                            1 if tipo_atual == "4–20 mA"
                            else 0
                        ),
                    )

                    # O shunt não é editável.
                    # Ele segue automaticamente o tipo elétrico.
                    st.text_input(
                        "Shunt 150 Ω",
                        value=(
                            "ON — automático"
                            if tipo_entrada == "4–20 mA"
                            else "OFF — automático"
                        ),
                        disabled=True,
                    )

                    unidade = st.selectbox(
                        "Unidade",
                        UNIT_OPTIONS,
                        index=UNIT_OPTIONS.index(
                            unidade_atual
                        ),
                    )

                    escala_min = st.number_input(
                        "Escala mínima",
                        value=float(
                            escala_min_atual
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    escala_max = st.number_input(
                        "Escala máxima",
                        value=float(
                            escala_max_atual
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    ativo = st.checkbox(
                        "Entrada ativa",
                        value=ativo_atual,
                    )

                    exibir_gauge = st.checkbox(
                        "Exibir gauge no dashboard",
                        value=exibir_gauge_atual,
                        help=(
                            "Quando ativado, esta entrada aparece como "
                            "mostrador analógico no Dashboard. Desative "
                            "para manter a leitura disponível sem criar gauge."
                        ),
                    )

                    alarme_min = st.number_input(
                        "Limite mínimo de alarme",
                        value=float(
                            safe_float(
                                alarme_min_atual,
                                0
                            )
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    alarme_max = st.number_input(
                        "Limite máximo de alarme",
                        value=float(
                            safe_float(
                                alarme_max_atual,
                                0
                            )
                        ),
                        step=0.1,
                        format="%.2f",
                    )

                    save_channel = st.form_submit_button(
                        "Salvar entrada",
                        type="primary",
                    )

                if save_channel:

                    if not channel_name.strip():
                        st.error(
                            f"Informe o nome da função de {canal}."
                        )
                        st.stop()

                    tipo_entrada_normalizado = (
                        "4–20 mA"
                        if tipo_entrada == "4–20 mA"
                        else "0–3 V"
                    )

                    shunt_ligado = (
                        tipo_entrada_normalizado == "4–20 mA"
                    )

                    modo_interno = (
                        "linear_4_20ma"
                        if shunt_ligado
                        else "linear_voltage"
                    )

                    # Para 4–20 mA, o domínio elétrico é 4–20 mA.
                    # Para tensão, o domínio elétrico é 0–3 V.
                    if shunt_ligado:
                        source_min = 4.0
                        source_max = 20.0
                    else:
                        source_min = 0.0
                        source_max = 3.0

                    payload = {
                        "nome_exibicao": (
                            channel_name.strip()
                        ),
                        "tipo_entrada": (
                            tipo_entrada_normalizado
                        ),
                        "shunt_150r": shunt_ligado,
                        "modo": modo_interno,
                        "role": "generic",
                        "unidade": (
                            ""
                            if unidade == "Sem unidade"
                            else unidade
                        ),
                        "source_min": source_min,
                        "source_max": source_max,
                        "eng_min": float(
                            escala_min
                        ),
                        "eng_max": float(
                            escala_max
                        ),
                        "shunt_ohms": 150.0,
                        "decimais": 2,
                        "ativo": ativo,
                        "exibir_gauge": exibir_gauge,
                        "alarme_min": float(
                            alarme_min
                        ),
                        "alarme_max": float(
                            alarme_max
                        ),
                    }

                    ok, error = update_channel(
                        selected_device,
                        canal,
                        payload,
                    )

                    if ok:
                        st.success(
                            f"{canal} atualizado."
                        )
                        st.rerun()
                    else:
                        st.error(
                            f"Não foi possível salvar {canal}."
                        )
                        st.code(
                            error or "Erro desconhecido"
                        )

        st.markdown("---")
        st.info(
            "Os limites de alarme das entradas analógicas são configurados "
            "diretamente em cada AI. Ao salvar a entrada, os valores mínimo "
            "e máximo passam a ser usados imediatamente pelo sistema de alarmes."
        )

        st.markdown(
            "<div class='small' style='margin-top:.35rem;'>"
            "A vibração dos eixos X/Y/Z é uma aquisição nativa do AXION e "
            "possui tratamento separado dos limites das entradas analógicas."
            "</div>",
            unsafe_allow_html=True,
        )


    # ============================================================
    # RODAPÉ
    # ============================================================

    st.markdown("---")
    st.markdown(
    f"""
    <div class="muted" style="text-align:center;padding:10px;">
        AXION • Atualização automática a cada {REFRESH_SECONDS}s •
        Dados reais do Supabase
    </div>
    """,
    unsafe_allow_html=True,
    )
