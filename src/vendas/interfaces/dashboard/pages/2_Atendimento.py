import streamlit as st

from vendas.bootstrap.container import container

ConversationModel = container.ConversationModel
LeadModel = container.LeadModel
st.set_page_config(
    page_title="Central de Atendimento e Handoffs - Vendas B2B",
    layout="wide",
)

st.markdown("### Central de Atendimento & Handoffs")
st.markdown(
    "Monitore conversas onde a IA escalou o atendimento para um operador humano ou onde o lead solicitou intervenção."
)
st.markdown("---")

session = container.session_factory()

# Busca conversas que estão em estado de HANDOFF
conversations = session.query(ConversationModel).filter(ConversationModel.state == "HANDOFF").all()

if not conversations:
    st.info(
        "Nenhum atendimento pendente de handoff humano no momento. Todas as conversas estão sob gestão autônoma da IA."
    )
else:
    # Seleção de conversas pendentes
    conv_options = {
        str(c.id): f"Lead ID: {c.lead_id} | Telefone: {c.contact_phone}" for c in conversations
    }
    selected_conv_id = st.selectbox(
        "Selecione uma conversa para assumir (Takeover):",
        options=list(conv_options.keys()),
        format_func=lambda x: conv_options[x],
    )

    if selected_conv_id:
        conv = session.query(ConversationModel).filter_by(id=selected_conv_id).first()
        if conv:
            lead = session.query(LeadModel).filter_by(id=conv.lead_id).first()

            st.markdown(f"#### Atendimento ao Lead: **{lead.name if lead else 'Desconhecido'}**")
            st.markdown(f"**Telefone / Canal:** {conv.contact_phone} ({conv.channel.upper()})")
            st.markdown("---")

            # Exibe o histórico de mensagens da conversa
            st.markdown("##### Histórico de Mensagens")
            for msg in conv.messages:
                sender_label = (
                    "Operador / IA" if msg.direction.value == "outbound" else "Lead (Cliente)"
                )
                st.text(f"[{msg.created_at.strftime('%H:%M:%S')}] {sender_label}: {msg.content}")

            st.markdown("---")

            # Formulário de resposta manual do operador humano (Takeover)
            with st.form("operator_takeover_form"):
                st.markdown("##### Enviar Mensagem (Takeover Humano)")
                operator_message = st.text_area("Digite sua resposta para o WhatsApp do cliente:")
                send_button = st.form_submit_button("Enviar Mensagem e Assumir Conversa")

                if send_button and operator_message:
                    # Enfileira o envio manual na outbox transacional
                    with container.uow as uow:
                        uow.outbox.add(
                            event_type="OPERATOR_TAKEOVER_MESSAGE",
                            payload={
                                "phone": conv.contact_phone,
                                "content": operator_message,
                            },
                            idempotency_key=f"operator-takeover-{conv.id}",
                        )
                        # Atualiza o estado da conversa para fechada/assumida se desejar
                        conv.state = container.ConversationState.OPEN
                        session.commit()

                    st.success("Mensagem enviada para a outbox de entrega com sucesso!")
                    st.rerun()

session.close()
