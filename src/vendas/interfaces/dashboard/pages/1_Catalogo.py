import os

import httpx
import streamlit as st

st.set_page_config(
    page_title="Gestão de Catálogo - Vendas B2B",
    layout="wide",
)

API_BASE_URL = os.getenv("VENDAS_API_URL", "http://localhost:8000")
HEADERS = {
    "Authorization": "Bearer local-dev",
    "X-User-Role": "admin",
    "X-User-Id": "dashboard-admin",
}

st.markdown("### Gestão de Catálogo e Base de Conhecimento da IA")
st.markdown("Cadastre serviços, preços e FAQ que a IA consulta no momento da conversa.")
st.markdown("---")

with st.expander("Cadastrar Novo Serviço / Produto", expanded=False):
    service_name = st.text_input("Nome do Serviço / Produto")
    description = st.text_area("Descrição detalhada / FAQ (Instruções para a IA)")
    category = st.text_input("Categoria")
    requires_approval = st.checkbox("Exige aprovação humana obrigatória para fechar?")
    discount_ok = st.checkbox("Permite concessão de desconto?")
    submitted = st.form_submit_button("Salvar no Catálogo")
    if submitted and service_name:
        payload = {
            "name": service_name,
            "description": description,
            "category": category or None,
            "requires_human_approval": requires_approval,
            "discount_allowed": discount_ok,
        }
        try:
            response = httpx.post(
                f"{API_BASE_URL}/catalog/services", json=payload, headers=HEADERS, timeout=10
            )
            response.raise_for_status()
            st.success(f"Serviço '{service_name}' cadastrado com sucesso!")
            st.rerun()
        except httpx.HTTPError as exc:
            st.error(f"Falha ao criar serviço: {exc}")

st.markdown("### Pré-visualização da Knowledge Base")
question = st.text_input(
    "Pergunta / contexto da IA", placeholder="Ex.: quero saber o valor do plano premium"
)
if question:
    try:
        response = httpx.post(
            f"{API_BASE_URL}/catalog/preview",
            json={"question": question},
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        st.json(response.json())
    except httpx.HTTPError as exc:
        st.warning(f"Preview indisponível: {exc}")

st.markdown("---")

try:
    response = httpx.get(f"{API_BASE_URL}/catalog/services", headers=HEADERS, timeout=10)
    response.raise_for_status()
    items = response.json()
except httpx.HTTPError:
    items = []

if not items:
    st.info("Nenhum item cadastrado no catálogo até o momento.")
else:
    for item in items:
        st.markdown(f"### {item.get('name', 'Serviço')}")
        st.caption(item.get("description") or "Sem descrição detalhada.")
        st.write(
            f"Categoria: {item.get('category') or 'Geral'} | "
            f"Regras: IA={'autônoma' if not item.get('requires_human_approval') else 'humana'} | "
            f"Desconto={'permitido' if item.get('discount_allowed') else 'bloqueado'}"
        )
        st.markdown("---")
