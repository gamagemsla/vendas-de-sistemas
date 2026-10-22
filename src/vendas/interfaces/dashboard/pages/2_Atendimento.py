import os

import httpx
import streamlit as st

from vendas.bootstrap.container import container

st.set_page_config(
    page_title="Central de Atendimento e Handoffs - Vendas B2B",
    layout="wide",
)

API_BASE_URL = os.getenv("VENDAS_API_URL", "http://localhost:8000")
HEADERS = {
    "Authorization": "Bearer local-dev",
    "X-User-Role": "admin",
    "X-User-Id": "dashboard-admin",
}

st.markdown("### Central de Atendimento & Handoffs")
st.markdown(
    "Monitore conversas onde a IA escalou o atendimento para um operador humano ou onde o lead solicitou intervenção."
)
st.markdown("---")

# Busca conversas em handoff via application query
handoff_query = container.get_handoff_conversations_query()
conversations = handoff_query.execute()

if not conversations:
    st.info(
        "Nenhum atendimento pendente de handoff humano no momento. Todas as conversas estão sob gestão autônoma da IA."
    )
else:
    # Seleção de conversas pendentes
    conv_options = {
        c["id"]: f"Lead: {c['lead_name']} | Telefone: {c['contact_phone']}" for c in conversations
    }
    selected_conv_id = st.selectbox(
        "Selecione uma conversa para assumir (Takeover):",
        options=list(conv_options.keys()),
        format_func=lambda x: conv_options[x],
    )

    if selected_conv_id:
        # Histórico via application query
        history_query = container.get_conversation_history_query()
        messages = history_query.execute(selected_conv_id)

        # Find selected conversation details
        conv = next((c for c in conversations if c["id"] == selected_conv_id), None)
        if conv:
            st.markdown(f"#### Atendimento ao Lead: **{conv['lead_name']}**")
            st.markdown(
                f"**Telefone / Canal:** {conv['contact_phone']} ({conv['channel'].upper()})"
            )
            st.markdown("---")

            # Exibe o histórico de mensagens da conversa
            st.markdown("##### Histórico de Mensagens")
            for msg in messages:
                sender_label = (
                    "Operador / IA" if msg["direction"] == "outbound" else "Lead (Cliente)"
                )
                st.text(f"[{msg['created_at'][11:19]}] {sender_label}: {msg['content']}")

            st.markdown("---")

            # Formulário de resposta manual do operador humano (Takeover)
            with st.form("operator_takeover_form"):
                st.markdown("##### Enviar Mensagem (Takeover Humano)")
                operator_message = st.text_area("Digite sua resposta para o WhatsApp do cliente:")
                send_button = st.form_submit_button("Enviar Mensagem e Assumir Conversa")

                if send_button and operator_message:
                    # Envia via API (ação de escrita)
                    try:
                        response = httpx.post(
                            f"{API_BASE_URL}/conversations/{selected_conv_id}/takeover",
                            json={"message": operator_message},
                            headers=HEADERS,
                            timeout=10,
                        )
                        response.raise_for_status()
                        st.success("Mensagem enviada para a outbox de entrega com sucesso!")
                        st.rerun()
                    except httpx.HTTPError as exc:
                        st.error(f"Falha ao enviar mensagem: {exc}")
