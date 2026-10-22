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
query_service = container.get_overview_kpis_query()
kpis = query_service.execute()

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
        st.metric(label="CONTATADOS", value=0, delta="-")
    with col4:
        st.metric(label="EM CONVERSA", value=1, delta="IA ativa")
    with col5:
        st.metric(label="REUNIÕES AGENDADAS", value=0, delta="Confirmadas")
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
            "Contatado": 0,
            "Em conversa": 1,
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
    st.info(
        "Aqui você poderá visualizar os leads extraídos pelo Apify e filtrá-los por CNPJ, status ou telefone."
    )

# -------------------------------------------------------------
# ABA 3: FILA DE DISPAROS
# -------------------------------------------------------------
with tab_fila:
    st.markdown("###  Fila de Disparos e Outbox")
    st.info(
        "Monitore os disparos automatizados de cadência, estado da outbox transacional e modo Dry-Run."
    )

# -------------------------------------------------------------
# ABA 4: ATENDIMENTO
# -------------------------------------------------------------
with tab_atendimento:
    st.markdown("###  Central de Atendimento & Handoffs")
    st.info("Gerencie conversas escaladas pela IA para atendimento humano (Takeover).")
