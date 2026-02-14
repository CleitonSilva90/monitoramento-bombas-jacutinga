import streamlit as st
import pandas as pd
from supabase import create_client
import math
from datetime import datetime

# 1. TENTATIVA DE CAPTURA IMEDIATA (API MODE)
# O st.query_params deve ser lido antes de qualquer st.title ou comando visual
params = st.query_params.to_dict()

if "id" in params:
    # Se houver um ID, o Streamlit entende que é o ESP32 e para tudo aqui
    try:
        # Configuração do Banco (Substitua se os seus dados mudarem)
        URL = "https://iemojjmgzyrxddochnlq.supabase.co"
        KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"
        supabase = create_client(URL, KEY)

        id_b = params["id"]
        m = float(params.get("mancal", 0))
        o = float(params.get("oleo", 0))
        p = float(params.get("pressao", 0))
        vx = float(params.get("vx", 0))
        vy = float(params.get("vy", 0))
        vz = float(params.get("vz", 0))
        v_rms = math.sqrt((vx**2 + vy**2 + vz**2) / 3)

        # Grava no Supabase (Usando os nomes de tabela que criamos no Passo 1 anterior)
        supabase.table("status_atual").upsert({
            "id_bomba": id_b, "mancal": m, "oleo": o, "rms": v_rms, "pressao": p, "ultima_batida": "now()"
        }).execute()

        supabase.table("historico").insert({
            "id_bomba": id_b, "mancal": m, "oleo": o, "rms": v_rms, "pressao": p
        }).execute()

        # Resposta curta para o ESP32 não ler o HTML inteiro
        st.write("DADO_SALVO")
        st.stop() # Mata o processo aqui para não carregar o resto do site
    except Exception as e:
        st.write(f"ERRO_API: {e}")
        st.stop()

# --- 2. INTERFACE DO USUÁRIO (SÓ CARREGA SE NÃO FOR API) ---
st.set_page_config(page_title="Dashboard Jacutinga", layout="wide")
st.title("🏭 Monitoramento em Tempo Real")

try:
    URL = "https://iemojjmgzyrxddochnlq.supabase.co"
    KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbW9qam1nenlyeGRkb2NobmxxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA1MzU2NTYsImV4cCI6MjA4NjExMTY1Nn0.Adeu9DBblWBUQfwlJS9XrcKWixNRqRizFEZ0TOkx7eY"
    supabase = create_client(URL, KEY)
    
    dados = supabase.table("status_atual").select("*").execute()
    
    if dados.data:
        df = pd.DataFrame(dados.data)
        st.subheader("Status dos Ativos")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aguardando dados do campo...")
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}")
