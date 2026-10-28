import streamlit as st

from vendas.bootstrap.container import container

# Configuração da Página
st.set_page_config(
    page_title="Painel Comercial - Vendas B2B",
    page_icon="",
    layout="wide",
)

# Cabeçalho Principal (Estilo Painel Comercial)
st.markdown("### Painel Comercial")
st.markdown("Captação, funil de vendas e atendimento por WhatsApp.")
st.markdown("---")

# Filtros Globais no Topo
filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])
with filter_col1:
    search_query = st.text_input("Buscar empresa", placeholder="Buscar por nome da empresa...")
with filter_col2:
    status_filter = st.multiselect(
        "Status do funil", ["Novo", "Contatado", "Em conversa", "Qualificado", "Perdido"]
    )
with filter_col3:
    grade_filter = st.multiselect(
        "Grau de oportunidade", ["Alta", "Média", "Baixa", "Sem classificação"]
    )

st.markdown("")

# Abas Superiores Correspondentes
tab_visao, tab_leads, tab_fila, tab_atendimento = st.tabs(
    ["Visão geral", "Leads", "Fila de disparos", "Atendimento"]
)

# Busca de Dados Segura via aplicação (Read Model)
overview_query = container.get_overview_kpis_query()
kpis = overview_query.execute()

# Contagens por status para KPIs adicionais
status_counts_query = container.get_count_leads_by_status_query()
status_counts = status_counts_query.execute()

# -------------------------------------------------------------
# ABA 1: VISÃO GERAL
# -------------------------------------------------------------
with tab_visao:
    # Linha de Métricas (KPI Cards no estilo da imagem)
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric(label="LEADS NA BASE", value=kpis.get("total_leads", 0), delta="Base ativa")
    with col2:
        st.metric(label="NOVOS", value=kpis.get("in_cadence", 0), delta="Aguardando")
    with col3:
        st.metric(label="CONTATADOS", value=status_counts.get("CONTACTED", 0), delta="-")
    with col4:
        st.metric(
            label="EM CONVERSA", value=status_counts.get("IN_CONVERSATION", 0), delta="IA ativa"
        )
    with col5:
        st.metric(
            label="REUNIÕES AGENDADAS",
            value=status_counts.get("MEETING_SCHEDULED", 0),
            delta="Confirmadas",
        )
    with col6:
        st.metric(
            label="CONVERSÃO", value=f"{kpis.get('conversion_rate', 0.0)}%", delta="reuniões / base"
        )

    st.markdown("---")

    # Seção Funil e Qualificação
    st.markdown("##### Funil e qualificação")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("**Leads por etapa do funil**")
        st.caption("Quantidade atual em cada status")
        funil_data = {
            "Novo": kpis.get("total_leads", 0),
            "Contatado": status_counts.get("CONTACTED", 0),
            "Em conversa": status_counts.get("IN_CONVERSATION", 0),
            "Perdido": kpis.get("opted_out_leads", 0),
        }
        st.bar_chart(funil_data)

    with chart_col2:
        st.markdown("**Grau de oportunidade**")
        st.caption("Participação de cada grau na base")
        oportunidade_data = {
            "Alta": kpis.get("qualified_leads", 0),
            "Sem classificação": kpis.get("total_leads", 0),
        }
        st.bar_chart(oportunidade_data)

# -------------------------------------------------------------
# ABA 2: LEADS
# -------------------------------------------------------------
with tab_leads:
    st.markdown("###  Gestão e Listagem de Leads")
    # Filtros locais
    lead_search = st.text_input("Buscar lead", placeholder="Nome da empresa ou contato...")
    lead_status = st.multiselect(
        "Status",
        ["NEW", "CONTACTED", "IN_CONVERSATION", "QUALIFIED", "OPTED_OUT", "MEETING_SCHEDULED"],
    )
    lead_grade = st.multiselect("Grau", ["HIGH", "MEDIUM", "LOW", "UNCLASSIFIED"])

    list_query = container.get_list_leads_query()
    leads = list_query.execute(
        search=lead_search or None,
        status=lead_status or None,
        grade=lead_grade or None,
        limit=50,
        offset=0,
    )

    if not leads:
        st.info("Nenhum lead encontrado com os filtros atuais.")
    else:
        for lead in leads:
            with st.expander(f"{lead['company_name']} - {lead['contact_name']}"):
                st.write(f"Telefone: {lead['phone']}")
                st.write(f"E-mail: {lead['email']}")
                st.write(f"Status: {lead['status']}")
                st.write(f"Grau: {lead['grade']}")
                st.write(f"Criado em: {lead['created_at']}")

# -------------------------------------------------------------
# ABA 3: FILA DE DISPAROS
# -------------------------------------------------------------
with tab_fila:
    st.markdown("###  Fila de Disparos e Outbox")
    outbox_status = st.multiselect("Status", ["pending", "sent", "failed", "dead_letter"])
    outbox_channel = st.multiselect("Canal", ["whatsapp", "email"])

    outbox_query = container.get_outbox_queue_query()
    outbox_items = outbox_query.execute(
        status=outbox_status or None,
        channel=outbox_channel or None,
        limit=50,
        offset=0,
    )

    if not outbox_items:
        st.info("Nenhum item na fila de disparos.")
    else:
        for item in outbox_items:
            with st.expander(f"{item['event_type']} - {item['channel']} ({item['status']})"):
                st.write(f"Tentativas: {item['attempts']}/{item['max_attempts']}")
                st.write(f"Agendado para: {item['scheduled_at']}")
                st.write(f"Criado em: {item['created_at']}")

# -------------------------------------------------------------
# ABA 4: ATENDIMENTO
# -------------------------------------------------------------
with tab_atendimento:
    st.markdown("###  Central de Atendimento & Handoffs")
    st.info("Gerencie conversas escaladas pela IA para atendimento humano (Takeover).")
