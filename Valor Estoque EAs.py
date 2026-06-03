import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from io import BytesIO

st.set_page_config(page_title="Indicadores de Estoque EAs", layout="wide")

ARQUIVO_PADRAO = Path("Valor Estoque EAs.xlsx")
NOME_PLANILHA_PREFERENCIAL = "Valor Estoque EAs"


def formatar_moeda_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero_br(valor, casas=0):
    if casas == 0:
        return f"{valor:,.0f}".replace(",", ".")
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pick_column(columns, *names):
    columns = [str(c).strip() for c in columns]
    for n in names:
        for c in columns:
            if c.lower() == n.lower():
                return c
    for n in names:
        for c in columns:
            if n.lower() in c.lower():
                return c
    return None


@st.cache_data(show_spinner=False)
def carregar_dados_excel(arquivo):
    xls = pd.ExcelFile(arquivo, engine="openpyxl")
    if NOME_PLANILHA_PREFERENCIAL in xls.sheet_names:
        sheet = NOME_PLANILHA_PREFERENCIAL
    else:
        sheet = xls.sheet_names[0]

    df = pd.read_excel(arquivo, sheet_name=sheet, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    col_tipo_material = pick_column(df.columns, 'TMar', 'TMat')
    col_centro = pick_column(df.columns, 'Cen.')
    col_deposito = pick_column(df.columns, 'Dep.')
    col_regiao = pick_column(df.columns, 'REGIÃO', 'REGIAO')
    col_uf = pick_column(df.columns, 'UF')
    col_cidade = pick_column(df.columns, 'CIDADE')
    col_tipo_estoque = pick_column(df.columns, 'TIPO ESTOQUE')
    col_tipo_despesa = pick_column(df.columns, 'TIPO DE DESPESA', 'Tipo Despesa')
    col_unidade = pick_column(df.columns, 'UNIDADE')
    col_qtd = pick_column(df.columns, 'Utilização livre')
    col_valor = pick_column(df.columns, 'Val.utiliz.livre')

    selecionadas = [
        c for c in [
            col_tipo_material,
            col_centro,
            col_deposito,
            col_regiao,
            col_uf,
            col_cidade,
            col_tipo_estoque,
            col_tipo_despesa,
            col_unidade,
            col_qtd,
            col_valor,
        ] if c in df.columns
    ]

    base = df[selecionadas].copy()

    if col_qtd in base.columns:
        base[col_qtd] = pd.to_numeric(base[col_qtd], errors='coerce').fillna(0)
    if col_valor in base.columns:
        base[col_valor] = pd.to_numeric(base[col_valor], errors='coerce').fillna(0)

    rename_map = {}
    if col_tipo_material in base.columns:
        rename_map[col_tipo_material] = 'TIPO DE MATERIAL'
    if col_centro in base.columns:
        rename_map[col_centro] = 'CENTRO'
    if col_deposito in base.columns:
        rename_map[col_deposito] = 'DEPOSITO'
    if col_regiao in base.columns:
        rename_map[col_regiao] = 'REGIAO'
    if col_uf in base.columns:
        rename_map[col_uf] = 'UF'
    if col_cidade in base.columns:
        rename_map[col_cidade] = 'CIDADE'
    if col_tipo_estoque in base.columns:
        rename_map[col_tipo_estoque] = 'TIPO ESTOQUE'
    if col_tipo_despesa in base.columns:
        rename_map[col_tipo_despesa] = 'TIPO DE DESPESA'
    if col_unidade in base.columns:
        rename_map[col_unidade] = 'UNIDADE'
    if col_qtd in base.columns:
        rename_map[col_qtd] = 'QUANTIDADE'
    if col_valor in base.columns:
        rename_map[col_valor] = 'VALOR'

    base = base.rename(columns=rename_map)

    for c in base.columns:
        if c not in ['QUANTIDADE', 'VALOR']:
            base[c] = base[c].astype(str).replace({'nan': 'Não informado'}).fillna('Não informado')

    return base, sheet


def gerar_resumo_excel(df_filtrado):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_filtrado.to_excel(writer, sheet_name='Base Filtrada', index=False)

        overview = pd.DataFrame({
            'Indicador': ['Linhas', 'Quantidade Total', 'Valor Total', 'Qtd. Regiões', 'Qtd. UFs', 'Qtd. Cidades'],
            'Valor': [
                len(df_filtrado),
                df_filtrado['QUANTIDADE'].sum() if 'QUANTIDADE' in df_filtrado.columns else 0,
                df_filtrado['VALOR'].sum() if 'VALOR' in df_filtrado.columns else 0,
                df_filtrado['REGIAO'].nunique() if 'REGIAO' in df_filtrado.columns else 0,
                df_filtrado['UF'].nunique() if 'UF' in df_filtrado.columns else 0,
                df_filtrado['CIDADE'].nunique() if 'CIDADE' in df_filtrado.columns else 0,
            ]
        })
        overview.to_excel(writer, sheet_name='Visao Geral', index=False)

        dimensoes = ['TIPO DE MATERIAL', 'REGIAO', 'UF', 'CIDADE', 'TIPO ESTOQUE', 'TIPO DE DESPESA', 'UNIDADE']
        for dim in dimensoes:
            if dim in df_filtrado.columns:
                resumo = (
                    df_filtrado.groupby(dim, dropna=False)
                    .agg(QUANTIDADE=('QUANTIDADE', 'sum'), VALOR=('VALOR', 'sum'))
                    .reset_index()
                    .sort_values('VALOR', ascending=False)
                )
                resumo.to_excel(writer, sheet_name=dim[:31], index=False)
    output.seek(0)
    return output


st.title('Indicadores de Estoque EAs')
st.caption('Versão preparada para GitHub / Streamlit Cloud, com leitura do arquivo no repositório ou upload manual.')

with st.sidebar:
    st.header('Fonte de dados')
    arquivo_upload = st.file_uploader('Envie a planilha Excel', type=['xlsx'])
    usar_arquivo_repositorio = st.checkbox('Usar arquivo padrão do repositório', value=ARQUIVO_PADRAO.exists())

arquivo_para_leitura = None
if arquivo_upload is not None:
    arquivo_para_leitura = arquivo_upload
elif usar_arquivo_repositorio and ARQUIVO_PADRAO.exists():
    arquivo_para_leitura = ARQUIVO_PADRAO

if arquivo_para_leitura is None:
    st.warning('Nenhum arquivo disponível. Faça upload da planilha ou adicione "Valor Estoque EAs.xlsx" na raiz do repositório.')
    st.stop()

base, sheet_usada = carregar_dados_excel(arquivo_para_leitura)

with st.sidebar:
    st.header('Filtros')
    filtros = {}
    for col in ['TIPO DE MATERIAL', 'CENTRO', 'DEPOSITO', 'REGIAO', 'UF', 'CIDADE', 'TIPO ESTOQUE', 'TIPO DE DESPESA', 'UNIDADE']:
        if col in base.columns:
            opcoes = sorted(base[col].dropna().astype(str).unique().tolist())
            filtros[col] = st.multiselect(col, opcoes)

filtrado = base.copy()
for col, valores in filtros.items():
    if valores:
        filtrado = filtrado[filtrado[col].isin(valores)]

valor_total = filtrado['VALOR'].sum() if 'VALOR' in filtrado.columns else 0
quantidade_total = filtrado['QUANTIDADE'].sum() if 'QUANTIDADE' in filtrado.columns else 0
linhas_total = len(filtrado)
qtd_cidades = filtrado['CIDADE'].nunique() if 'CIDADE' in filtrado.columns else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric('Valor Total', formatar_moeda_br(valor_total))
m2.metric('Quantidade Total', formatar_numero_br(quantidade_total))
m3.metric('Linhas', formatar_numero_br(linhas_total))
m4.metric('Cidades', formatar_numero_br(qtd_cidades))

with st.expander('Informações da carga', expanded=False):
    st.write(f'Planilha utilizada: {sheet_usada}')
    st.write(f'Linhas carregadas: {formatar_numero_br(len(base))}')
    st.write(f'Colunas disponíveis: {", ".join(base.columns)}')

visoes = [
    'TIPO DE MATERIAL',
    'REGIAO',
    'UF',
    'CIDADE',
    'TIPO ESTOQUE',
    'TIPO DE DESPESA',
    'UNIDADE'
]
visoes = [v for v in visoes if v in filtrado.columns]

col_a, col_b = st.columns([2, 1])
with col_a:
    visao = st.selectbox('Visão do indicador', visoes)
with col_b:
    metrica = st.radio('Métrica', ['VALOR', 'QUANTIDADE'], horizontal=True)

agg = (
    filtrado.groupby(visao, dropna=False)
    .agg(VALOR=('VALOR', 'sum'), QUANTIDADE=('QUANTIDADE', 'sum'))
    .reset_index()
    .sort_values(metrica, ascending=False)
)

top_n = st.slider('Top N categorias', 5, min(30, max(5, len(agg))), min(10, max(5, len(agg))))
agg_top = agg.head(top_n)

aba1, aba2, aba3 = st.tabs(['Barras', 'Pizza', 'Tabela'])

with aba1:
    fig_bar = px.bar(
        agg_top,
        x=visao,
        y=metrica,
        text=metrica,
        title=f'{metrica} por {visao}'
    )
    fig_bar.update_traces(textposition='outside')
    fig_bar.update_layout(xaxis_title=visao, yaxis_title=metrica)
    st.plotly_chart(fig_bar, use_container_width=True)

with aba2:
    fig_pie = px.pie(
        agg_top,
        names=visao,
        values=metrica,
        title=f'Distribuição de {metrica} por {visao}'
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with aba3:
    st.dataframe(agg, use_container_width=True, height=420)

st.subheader('Base filtrada')
st.dataframe(filtrado, use_container_width=True, height=450)

col_download_1, col_download_2 = st.columns(2)
with col_download_1:
    csv = filtrado.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        'Baixar base filtrada (CSV)',
        data=csv,
        file_name='estoque_eas_filtrado.csv',
        mime='text/csv'
    )

with col_download_2:
    excel_bytes = gerar_resumo_excel(filtrado)
    st.download_button(
        'Baixar resumo filtrado (Excel)',
        data=excel_bytes,
        file_name='Resumo_Estoque_EAs_Filtrado.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )