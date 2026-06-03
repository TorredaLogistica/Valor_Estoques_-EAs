import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from io import BytesIO

st.set_page_config(page_title="Indicadores de Estoque EAs", layout="wide")

ARQUIVO = "Valor Estoque EAs.xlsx"
SHEET = "Valor Estoque EAs"


def formatar_moeda_br(valor):
    try:
        valor = float(valor)
    except Exception:
        valor = 0.0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero_br(valor, casas=0):
    try:
        valor = float(valor)
    except Exception:
        valor = 0.0
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


def normalizar_texto(df):
    for c in df.columns:
        if c not in ["QUANTIDADE", "VALOR"]:
            df[c] = (
                df[c]
                .astype(str)
                .str.strip()
                .replace({
                    "nan": "Não informado",
                    "None": "Não informado",
                    "": "Não informado",
                    "<NA>": "Não informado",
                })
                .fillna("Não informado")
            )
    return df


@st.cache_data(show_spinner=False)
def carregar_dados(arquivo_excel):
    xls = pd.ExcelFile(arquivo_excel, engine="openpyxl")
    sheet = SHEET if SHEET in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(arquivo_excel, sheet_name=sheet, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    col_tipo_material = pick_column(df.columns, "TMar", "TMat") or "TMat"
    col_centro = pick_column(df.columns, "Cen.") or "Cen."
    col_deposito = pick_column(df.columns, "Dep.") or "Dep."
    col_regiao = pick_column(df.columns, "REGIÃO", "REGIAO") or "REGIÃO"
    col_uf = pick_column(df.columns, "UF") or "UF"
    col_cidade = pick_column(df.columns, "CIDADE") or "CIDADE"
    col_tipo_estoque = pick_column(df.columns, "TIPO ESTOQUE") or "TIPO ESTOQUE"
    col_tipo_despesa = pick_column(df.columns, "TIPO DE DESPESA", "Tipo Despesa") or "Tipo Despesa"
    col_unidade = pick_column(df.columns, "UNIDADE") or "UNIDADE"
    col_qtd = pick_column(df.columns, "Utilização livre") or "Utilização livre"
    col_valor = pick_column(df.columns, "Val.utiliz.livre") or "Val.utiliz.livre"

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

    for c in [col_qtd, col_valor]:
        if c in base.columns:
            base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0)

    rename_map = {}
    if col_tipo_material in base.columns:
        rename_map[col_tipo_material] = "TIPO DE MATERIAL"
    if col_centro in base.columns:
        rename_map[col_centro] = "CENTRO"
    if col_deposito in base.columns:
        rename_map[col_deposito] = "DEPOSITO"
    if col_regiao in base.columns:
        rename_map[col_regiao] = "REGIAO"
    if col_uf in base.columns:
        rename_map[col_uf] = "UF"
    if col_cidade in base.columns:
        rename_map[col_cidade] = "CIDADE"
    if col_tipo_estoque in base.columns:
        rename_map[col_tipo_estoque] = "TIPO ESTOQUE"
    if col_tipo_despesa in base.columns:
        rename_map[col_tipo_despesa] = "TIPO DE DESPESA"
    if col_unidade in base.columns:
        rename_map[col_unidade] = "UNIDADE"
    if col_qtd in base.columns:
        rename_map[col_qtd] = "QUANTIDADE"
    if col_valor in base.columns:
        rename_map[col_valor] = "VALOR"

    base = base.rename(columns=rename_map)
    base = normalizar_texto(base)
    return base


def preparar_df_exibicao(df):
    df_exib = df.copy()
    if "VALOR" in df_exib.columns:
        df_exib["VALOR"] = df_exib["VALOR"].apply(formatar_moeda_br)
    if "QUANTIDADE" in df_exib.columns:
        df_exib["QUANTIDADE"] = df_exib["QUANTIDADE"].apply(formatar_numero_br)
    return df_exib


def gerar_excel_download(df_filtrado, agg=None, visao=None):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_filtrado.to_excel(writer, sheet_name="Base Filtrada", index=False)

        visao_geral = pd.DataFrame({
            "Indicador": ["Valor Total", "Quantidade Total", "Linhas", "Cidades"],
            "Valor": [
                df_filtrado["VALOR"].sum() if "VALOR" in df_filtrado.columns else 0,
                df_filtrado["QUANTIDADE"].sum() if "QUANTIDADE" in df_filtrado.columns else 0,
                len(df_filtrado),
                df_filtrado["CIDADE"].nunique() if "CIDADE" in df_filtrado.columns else 0,
            ]
        })
        visao_geral.to_excel(writer, sheet_name="Visao Geral", index=False)

        if agg is not None and not agg.empty:
            nome_aba = f"Resumo_{visao}"[:31] if visao else "Resumo"
            agg.to_excel(writer, sheet_name=nome_aba, index=False)
    output.seek(0)
    return output


def desenhar_cards(valor_total, quantidade_total, linhas_total, qtd_cidades):
    st.markdown(
        """
        <style>
        .kpi-card {
            background-color: #ffffff;
            border: 1px solid #E6E9EF;
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 1px 3px rgba(16,24,40,0.06);
            min-height: 110px;
        }
        .kpi-label {
            color: #475467;
            font-size: 16px;
            margin-bottom: 10px;
        }
        .kpi-value {
            color: #101828;
            font-size: 26px;
            font-weight: 700;
            line-height: 1.2;
            word-break: break-word;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    cards = [
        ("Valor Total", formatar_moeda_br(valor_total)),
        ("Quantidade Total", formatar_numero_br(quantidade_total)),
        ("Linhas", formatar_numero_br(linhas_total)),
        ("Cidades", formatar_numero_br(qtd_cidades)),
    ]
    for col, (titulo, valor) in zip([c1, c2, c3, c4], cards):
        col.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-label'>{titulo}</div>
                <div class='kpi-value'>{valor}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


st.title("Indicadores de Estoque EAs")
st.caption("Versão ajustada para evitar erros nos filtros, ampliar as visões e padronizar a formatação.")

arquivo_padrao = Path(ARQUIVO)
if not arquivo_padrao.exists():
    st.error(f"Arquivo '{ARQUIVO}' não encontrado na raiz do repositório.")
    st.stop()

base = carregar_dados(arquivo_padrao)

with st.sidebar:
    st.header("Filtros")
    filtros = {}
    colunas_filtro = [
        "TIPO DE MATERIAL",
        "CENTRO",
        "DEPOSITO",
        "REGIAO",
        "UF",
        "CIDADE",
        "TIPO ESTOQUE",
        "TIPO DE DESPESA",
        "UNIDADE",
    ]
    for col in colunas_filtro:
        if col in base.columns:
            opcoes = sorted(base[col].dropna().astype(str).unique().tolist())
            filtros[col] = st.multiselect(col, opcoes)

filtrado = base.copy()
for col, valores in filtros.items():
    if valores:
        filtrado = filtrado[filtrado[col].isin(valores)]

valor_total = filtrado["VALOR"].sum() if "VALOR" in filtrado.columns else 0
quantidade_total = filtrado["QUANTIDADE"].sum() if "QUANTIDADE" in filtrado.columns else 0
linhas_total = len(filtrado)
qtd_cidades = filtrado["CIDADE"].nunique() if "CIDADE" in filtrado.columns else 0

desenhar_cards(valor_total, quantidade_total, linhas_total, qtd_cidades)

visoes = [
    "TIPO DE MATERIAL",
    "REGIAO",
    "UF",
    "CIDADE",
    "TIPO ESTOQUE",
    "TIPO DE DESPESA",
    "UNIDADE",
]
visoes = [v for v in visoes if v in filtrado.columns]

if not visoes:
    st.warning("Não há colunas disponíveis para análise.")
    st.stop()

col_a, col_b = st.columns([2, 1])
with col_a:
    visao = st.selectbox("Visão do indicador", visoes)
with col_b:
    metrica = st.radio("Métrica", ["VALOR", "QUANTIDADE"], horizontal=True)

if filtrado.empty:
    st.warning("Os filtros selecionados não retornaram dados. Ajuste os filtros para visualizar os gráficos e tabelas.")
    agg = pd.DataFrame()
else:
    agg = (
        filtrado.groupby(visao, dropna=False)
        .agg(VALOR=("VALOR", "sum"), QUANTIDADE=("QUANTIDADE", "sum"))
        .reset_index()
        .sort_values(metrica, ascending=False)
    )
    agg = agg[agg[metrica].fillna(0) != 0] if metrica in agg.columns else agg

if not filtrado.empty and not agg.empty:
    max_categorias = min(30, len(agg))
    valor_inicial = min(10, len(agg))

    if len(agg) == 1:
        top_n = 1
        st.caption("Apenas 1 categoria disponível para a seleção atual.")
    else:
        top_n = st.slider(
            "Top N categorias",
            min_value=1,
            max_value=max_categorias,
            value=valor_inicial,
        )

    agg_top = agg.head(top_n).copy()
    agg_top[visao] = agg_top[visao].astype(str)
    agg_top["TEXTO_FORMATADO"] = agg_top[metrica].apply(
        lambda x: formatar_moeda_br(x) if metrica == "VALOR" else formatar_numero_br(x)
    )

    aba1, aba2, aba3 = st.tabs(["Barras", "Pizza", "Tabela"])

    with aba1:
        orientacao = "h" if visao in ["TIPO DE MATERIAL", "CIDADE", "TIPO DE DESPESA", "UNIDADE"] else "v"

        if orientacao == "h":
            fig_bar = px.bar(
                agg_top.sort_values(metrica, ascending=True),
                x=metrica,
                y=visao,
                text="TEXTO_FORMATADO",
                orientation="h",
                title=f"{metrica} por {visao}",
            )
            fig_bar.update_layout(
                xaxis_title=metrica,
                yaxis_title=visao,
                height=max(450, 40 * len(agg_top))
            )
            fig_bar.update_traces(
                textposition="outside",
                hovertemplate=f"{visao}: %{{y}}<br>{metrica}: %{{text}}<extra></extra>",
                cliponaxis=False,
            )
            if metrica == "VALOR":
                fig_bar.update_xaxes(tickprefix="R$ ")
        else:
            fig_bar = px.bar(
                agg_top,
                x=visao,
                y=metrica,
                text="TEXTO_FORMATADO",
                title=f"{metrica} por {visao}",
            )
            fig_bar.update_traces(
                textposition="outside",
                hovertemplate=f"{visao}: %{{x}}<br>{metrica}: %{{text}}<extra></extra>",
                cliponaxis=False,
            )
            fig_bar.update_layout(xaxis_title=visao, yaxis_title=metrica)
            fig_bar.update_xaxes(tickangle=-35)
            if metrica == "VALOR":
                fig_bar.update_yaxes(tickprefix="R$ ")

        st.plotly_chart(fig_bar, use_container_width=True)

    with aba2:
        fig_pie = px.pie(
            agg_top,
            names=visao,
            values=metrica,
            title=f"Distribuição de {metrica} por {visao}",
        )
        if metrica == "VALOR":
            fig_pie.update_traces(
                texttemplate="%{label}<br>%{percent}",
                hovertemplate=f"%{{label}}<br>{metrica}: %{{value:,.2f}}<br>%{{percent}}<extra></extra>"
            )
        else:
            fig_pie.update_traces(
                texttemplate="%{label}<br>%{percent}",
                hovertemplate=f"%{{label}}<br>{metrica}: %{{value:,.0f}}<br>%{{percent}}<extra></extra>"
            )
        st.plotly_chart(fig_pie, use_container_width=True)

    with aba3:
        st.dataframe(preparar_df_exibicao(agg), use_container_width=True, height=420)

elif filtrado.empty:
    st.info("Sem dados para exibir nos gráficos com os filtros atuais.")
else:
    st.info("Sem categorias com valor ou quantidade para a visão selecionada.")

st.subheader("Base filtrada")
st.dataframe(preparar_df_exibicao(filtrado), use_container_width=True, height=450)

excel_bytes = gerar_excel_download(filtrado, agg if 'agg' in locals() else None, visao)
st.download_button(
    "Baixar base filtrada (.xlsx)",
    data=excel_bytes,
    file_name="Base_Filtrada_Estoque_EAs.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
