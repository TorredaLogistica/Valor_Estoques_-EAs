import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from io import BytesIO

st.set_page_config(page_title="Valores dos Estoques dos EAs", layout="wide")

ARQUIVO = "Valor Estoque EAs_Consolidado.parquet"
MESES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


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


def formatar_valor_grafico(valor, metrica):
    try:
        valor = float(valor)
    except Exception:
        valor = 0.0

    if metrica == "VALOR":
        absoluto = abs(valor)
        if absoluto >= 1_000_000_000:
            return f"R$ {valor / 1_000_000_000:.1f} bi".replace(".", ",")
        if absoluto >= 1_000_000:
            return f"R$ {valor / 1_000_000:.1f} mi".replace(".", ",")
        if absoluto >= 1_000:
            return f"R$ {valor / 1_000:.1f} mil".replace(".", ",")
        return formatar_moeda_br(valor)

    absoluto = abs(valor)
    if absoluto >= 1_000_000:
        return f"{valor / 1_000_000:.1f} mi".replace(".", ",")
    if absoluto >= 1_000:
        return f"{valor / 1_000:.1f} mil".replace(".", ",")
    return formatar_numero_br(valor)


def preparar_rotulos_linha(df, metrica):
    dados = df.copy()
    dados["ROTULO_GRAFICO"] = dados[metrica].apply(lambda valor: formatar_valor_grafico(valor, metrica))
    dados["ROTULO_COMPLETO"] = dados[metrica].apply(
        lambda valor: formatar_moeda_br(valor) if metrica == "VALOR" else formatar_numero_br(valor)
    )
    dados["POSICAO_ROTULO"] = ["top center" if indice % 2 == 0 else "bottom center" for indice in range(len(dados))]
    return dados


def pick_column(columns, *names):
    columns = [str(c).strip() for c in columns]
    for nome in names:
        for coluna in columns:
            if coluna.lower() == nome.lower():
                return coluna
    for nome in names:
        for coluna in columns:
            if nome.lower() in coluna.lower():
                return coluna
    return None


def converter_mes(valor):
    if pd.isna(valor):
        return pd.NA
    texto = str(valor).strip().lower()
    mapa = {
        "jan": 1, "janeiro": 1, "fev": 2, "fevereiro": 2, "mar": 3, "março": 3,
        "abr": 4, "abril": 4, "mai": 5, "maio": 5, "jun": 6, "junho": 6,
        "jul": 7, "julho": 7, "ago": 8, "agosto": 8, "set": 9, "setembro": 9,
        "out": 10, "outubro": 10, "nov": 11, "novembro": 11, "dez": 12, "dezembro": 12,
    }
    if texto in mapa:
        return mapa[texto]
    try:
        numero = int(float(texto))
        return numero if 1 <= numero <= 12 else pd.NA
    except Exception:
        return pd.NA


def identificar_periodo(df):
    """Cria DATA_REFERENCIA e MES_ANO usando data completa, mês/ano ou período textual."""
    col_data = pick_column(
        df.columns,
        "DATA REFERÊNCIA", "DATA REFERENCIA", "DATA", "DT REFERÊNCIA", "DT REFERENCIA",
        "DATA ESTOQUE", "DATA BASE", "COMPETÊNCIA", "COMPETENCIA",
    )
    col_periodo = pick_column(df.columns, "MÊS/ANO", "MES/ANO", "MÊS ANO", "MES ANO", "PERÍODO", "PERIODO")
    col_mes = pick_column(df.columns, "MÊS", "MES")
    col_ano = pick_column(df.columns, "ANO")

    data_ref = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

    if col_data:
        data_ref = pd.to_datetime(df[col_data], errors="coerce", dayfirst=True)

    if data_ref.isna().all() and col_periodo:
        texto = df[col_periodo].astype(str).str.strip()
        data_ref = pd.to_datetime(texto, errors="coerce", dayfirst=True)
        faltantes = data_ref.isna()
        if faltantes.any():
            extraido = texto.str.extract(r"(?P<mes>\d{1,2})\D+(?P<ano>\d{4})")
            data_extraida = pd.to_datetime(
                dict(
                    year=pd.to_numeric(extraido["ano"], errors="coerce"),
                    month=pd.to_numeric(extraido["mes"], errors="coerce"),
                    day=1,
                ),
                errors="coerce",
            )
            data_ref = data_ref.fillna(data_extraida)

    if data_ref.isna().all() and col_mes and col_ano:
        mes = df[col_mes].apply(converter_mes)
        ano = pd.to_numeric(df[col_ano], errors="coerce")
        data_ref = pd.to_datetime(dict(year=ano, month=mes, day=1), errors="coerce")

    if data_ref.notna().any():
        df["DATA_REFERENCIA"] = data_ref.dt.to_period("M").dt.to_timestamp()
        df["MES_ANO"] = df["DATA_REFERENCIA"].apply(
            lambda x: f"{MESES_PT[x.month]}/{x.year}" if pd.notna(x) else "Não informado"
        )
    else:
        df["DATA_REFERENCIA"] = pd.NaT
        df["MES_ANO"] = "Não informado"
    return df


def normalizar_texto(df):
    ignorar = {"QUANTIDADE", "VALOR", "DATA_REFERENCIA"}
    for coluna in df.columns:
        if coluna not in ignorar:
            df[coluna] = (
                df[coluna].astype(str).str.strip()
                .replace({"nan": "Não informado", "None": "Não informado", "": "Não informado", "<NA>": "Não informado"})
                .fillna("Não informado")
            )
    return df


@st.cache_data(show_spinner=False)
def carregar_dados(arquivo_parquet):
    df = pd.read_parquet(arquivo_parquet, engine="pyarrow")
    df.columns = [str(c).strip() for c in df.columns]
    df = identificar_periodo(df)

    candidatos = {
        "TIPO DE MATERIAL": pick_column(df.columns, "TMar", "TMat", "TIPO DE MATERIAL"),
        "CENTRO": pick_column(df.columns, "Cen.", "CENTRO"),
        "DEPOSITO": pick_column(df.columns, "Dep.", "DEPOSITO", "DEPÓSITO"),
        "REGIAO": pick_column(df.columns, "REGIÃO", "REGIAO"),
        "UF": pick_column(df.columns, "UF"),
        "CIDADE": pick_column(df.columns, "CIDADE"),
        "TIPO ESTOQUE": pick_column(df.columns, "TIPO ESTOQUE"),
        "TIPO DE DESPESA": pick_column(df.columns, "TIPO DE DESPESA", "Tipo Despesa"),
        "UNIDADE": pick_column(df.columns, "UNIDADE"),
        "QUANTIDADE": pick_column(df.columns, "Utilização livre", "QUANTIDADE"),
        "VALOR": pick_column(df.columns, "Val.utiliz.livre", "VALOR"),
    }

    selecionadas = [c for c in candidatos.values() if c and c in df.columns]
    selecionadas += ["DATA_REFERENCIA", "MES_ANO"]
    selecionadas = list(dict.fromkeys(selecionadas))
    base = df[selecionadas].copy()

    rename_map = {origem: destino for destino, origem in candidatos.items() if origem in base.columns}
    base = base.rename(columns=rename_map)
    for coluna in ["QUANTIDADE", "VALOR"]:
        if coluna not in base.columns:
            base[coluna] = 0.0
        base[coluna] = pd.to_numeric(base[coluna], errors="coerce").fillna(0)
    return normalizar_texto(base)

def preparar_df_exibicao(df):
    df_exib = df.copy()
    if "DATA_REFERENCIA" in df_exib.columns:
        df_exib = df_exib.drop(columns=["DATA_REFERENCIA"])
    if "VALOR" in df_exib.columns:
        df_exib["VALOR"] = df_exib["VALOR"].apply(formatar_moeda_br)
    if "QUANTIDADE" in df_exib.columns:
        df_exib["QUANTIDADE"] = df_exib["QUANTIDADE"].apply(formatar_numero_br)
    return df_exib


def gerar_excel_download(df_filtrado, agg=None, evolucao=None):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        preparar_df_exibicao(df_filtrado).to_excel(writer, sheet_name="Base Filtrada", index=False)
        if agg is not None and not agg.empty:
            agg.to_excel(writer, sheet_name="Resumo Atual", index=False)
        if evolucao is not None and not evolucao.empty:
            evolucao.to_excel(writer, sheet_name="Evolucao Mensal", index=False)
    output.seek(0)
    return output


def desenhar_cards(df):
    valor_total = df["VALOR"].sum()
    quantidade_total = df["QUANTIDADE"].sum()
    qtd_depositos = df["DEPOSITO"].nunique() if "DEPOSITO" in df.columns else 0
    qtd_cidades = df["CIDADE"].nunique() if "CIDADE" in df.columns else 0
    st.markdown("""
        <style>
        .kpi-card {background:#fff;border:1px solid #E6E9EF;border-radius:12px;padding:14px 16px;
                   box-shadow:0 1px 3px rgba(16,24,40,.06);min-height:110px}
        .kpi-label {color:#475467;font-size:16px;margin-bottom:10px}
        .kpi-value {color:#101828;font-size:26px;font-weight:700;line-height:1.2;word-break:break-word}
        </style>
    """, unsafe_allow_html=True)
    cards = [
        ("Valor Total", formatar_moeda_br(valor_total)),
        ("Quantidade Total", formatar_numero_br(quantidade_total)),
        ("Depósitos", formatar_numero_br(qtd_depositos)),
        ("Cidades", formatar_numero_br(qtd_cidades)),
    ]
    for coluna, (titulo, valor) in zip(st.columns(4), cards):
        coluna.markdown(f"<div class='kpi-card'><div class='kpi-label'>{titulo}</div><div class='kpi-value'>{valor}</div></div>", unsafe_allow_html=True)


def montar_grafico_barras(agg, visao, metrica):
    horizontal = visao in ["TIPO DE MATERIAL", "CIDADE", "TIPO DE DESPESA", "UNIDADE"]
    base_plot = agg.sort_values(metrica, ascending=horizontal).copy()
    base_plot["TEXTO_FORMATADO"] = base_plot[metrica].apply(
        lambda x: formatar_moeda_br(x) if metrica == "VALOR" else formatar_numero_br(x)
    )
    if horizontal:
        fig = px.bar(base_plot, x=metrica, y=visao, orientation="h", text="TEXTO_FORMATADO", title=f"{metrica} por {visao}")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(height=max(450, 40 * len(base_plot)), margin=dict(l=20, r=150, t=60, b=20))
    else:
        fig = px.bar(base_plot, x=visao, y=metrica, text="TEXTO_FORMATADO", title=f"{metrica} por {visao}")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(tickangle=-35)
        fig.update_layout(margin=dict(l=20, r=80, t=60, b=60))
    if metrica == "VALOR":
        fig.update_xaxes(tickprefix="R$ ") if horizontal else fig.update_yaxes(tickprefix="R$ ")
    return fig


def aplicar_filtros(base, filtros):
    resultado = base.copy()
    for coluna, valores in filtros.items():
        if valores:
            resultado = resultado[resultado[coluna].isin(valores)]
    return resultado


def montar_evolucao(df, metrica, meses):
    if df["DATA_REFERENCIA"].notna().sum() == 0:
        return pd.DataFrame()
    data_maxima = df["DATA_REFERENCIA"].max()
    inicio = data_maxima - pd.DateOffset(months=meses - 1)
    recorte = df[df["DATA_REFERENCIA"].between(inicio, data_maxima)].copy()
    evolucao = recorte.groupby(["DATA_REFERENCIA", "MES_ANO"], as_index=False)[["VALOR", "QUANTIDADE"]].sum()
    return evolucao.sort_values("DATA_REFERENCIA")


st.title("Valores dos Estoques dos EAs")
st.caption("Análise do estoque por período, visão atual e evolução mensal.")

arquivo_padrao = Path(ARQUIVO)
if not arquivo_padrao.exists():
    st.error(f"Arquivo Parquet '{ARQUIVO}' não encontrado na raiz do repositório.")
    st.stop()

base = carregar_dados(arquivo_padrao)
possui_periodo = base["DATA_REFERENCIA"].notna().any()

with st.sidebar:
    st.header("Filtros")
    if possui_periodo:
        periodos = (
            base[["DATA_REFERENCIA", "MES_ANO"]].dropna(subset=["DATA_REFERENCIA"])
            .drop_duplicates().sort_values("DATA_REFERENCIA", ascending=False)
        )
        opcoes_periodo = periodos["MES_ANO"].tolist()
        periodo_referencia = st.selectbox("Mês/Ano de referência", opcoes_periodo, index=0, key="mes_ano_referencia")
    else:
        periodo_referencia = None
        st.warning("Não foi localizada uma coluna de data, mês/ano ou competência na planilha.")

    filtros = {}
    for coluna in ["TIPO DE MATERIAL", "CENTRO", "DEPOSITO", "REGIAO", "UF", "CIDADE", "TIPO ESTOQUE", "TIPO DE DESPESA", "UNIDADE"]:
        if coluna in base.columns:
            opcoes = sorted(base[coluna].dropna().astype(str).unique().tolist())
            filtros[coluna] = st.multiselect(coluna, opcoes, key=f"filtro_{coluna}")

base_com_filtros = aplicar_filtros(base, filtros)
filtrado = base_com_filtros.copy()
if periodo_referencia:
    filtrado = filtrado[filtrado["MES_ANO"] == periodo_referencia]

aba_atual, aba_evolucao = st.tabs(["Visão Atual", "Evolução Mensal"])

with aba_atual:
    if periodo_referencia:
        st.caption(f"Referência selecionada: {periodo_referencia}")
    desenhar_cards(filtrado)

    visoes = [v for v in ["TIPO DE MATERIAL", "REGIAO", "UF", "CIDADE", "TIPO ESTOQUE", "TIPO DE DESPESA", "UNIDADE"] if v in filtrado.columns]
    col_a, col_b = st.columns([2, 1])
    with col_a:
        visao = st.selectbox("Visão do indicador", visoes, key="visao_atual")
    with col_b:
        metrica = st.radio("Métrica", ["VALOR", "QUANTIDADE"], horizontal=True, key="metrica_atual")

    if filtrado.empty:
        st.warning("Os filtros selecionados não retornaram dados.")
        agg = pd.DataFrame()
    else:
        agg = filtrado.groupby(visao, dropna=False)[["VALOR", "QUANTIDADE"]].sum().reset_index().sort_values(metrica, ascending=False)
        agg = agg[agg[metrica] != 0]

    if not agg.empty:
        top_n = st.slider("Top N categorias", 1, min(30, len(agg)), min(10, len(agg)), key="top_n_categorias") if len(agg) > 1 else 1
        agg_top = agg.head(top_n).copy()
        # Exibe somente um gráfico de barras na Visão Atual.
        fig_barras = montar_grafico_barras(agg_top, visao, metrica)
        st.plotly_chart(
            fig_barras,
            use_container_width=True,
            key="visao_atual_grafico_barras_unico",
        )
        with st.expander("Ver tabela detalhada"):
            st.dataframe(preparar_df_exibicao(agg), use_container_width=True, height=420)

    st.subheader("Base filtrada")
    st.dataframe(preparar_df_exibicao(filtrado), use_container_width=True, height=450)

with aba_evolucao:
    st.subheader("Evolução mensal do estoque")
    if not possui_periodo:
        st.info("Para exibir a evolução mensal, inclua na planilha uma coluna de Data, Mês/Ano, Competência ou as colunas Mês e Ano.")
        evolucao_total = pd.DataFrame()
    else:
        col_1, col_2 = st.columns([1, 1])
        with col_1:
            janela = st.selectbox("Período da evolução", [12, 6, 3], index=0, format_func=lambda x: f"Últimos {x} meses", key="periodo_evolucao")
        with col_2:
            metrica_evolucao = st.radio("Métrica da evolução", ["VALOR", "QUANTIDADE"], horizontal=True, key="metrica_evolucao")

        evolucao_total = montar_evolucao(base_com_filtros, metrica_evolucao, janela)
        if evolucao_total.empty:
            st.warning("Não há dados mensais para os filtros selecionados.")
        else:
            evolucao_total_plot = preparar_rotulos_linha(evolucao_total, metrica_evolucao)
            fig_total = px.line(
                evolucao_total_plot,
                x="MES_ANO",
                y=metrica_evolucao,
                markers=True,
                text="ROTULO_GRAFICO",
                custom_data=["ROTULO_COMPLETO"],
                title=f"Evolução mensal do total do estoque - {metrica_evolucao}",
            )
            fig_total.update_traces(
                line=dict(width=3),
                marker=dict(size=8),
                textposition=evolucao_total_plot["POSICAO_ROTULO"].tolist(),
                textfont=dict(size=12),
                hovertemplate="%{x}<br>%{customdata[0]}<extra></extra>",
                cliponaxis=False,
            )
            fig_total.update_layout(
                xaxis_title="Mês/Ano",
                yaxis_title=metrica_evolucao,
                hovermode="x unified",
                margin=dict(l=20, r=30, t=80, b=60),
            )
            if metrica_evolucao == "VALOR":
                fig_total.update_yaxes(tickprefix="R$ ")
            st.plotly_chart(
                fig_total,
                use_container_width=True,
                key="evolucao_mensal_grafico_total",
            )

            st.subheader("Evolução por tipo de material")
            materiais = sorted(base_com_filtros["TIPO DE MATERIAL"].dropna().astype(str).unique().tolist())
            material_selecionado = st.selectbox("Selecione o tipo de material", materiais, key="material_evolucao")
            base_material = base_com_filtros[base_com_filtros["TIPO DE MATERIAL"] == material_selecionado]
            evolucao_material = montar_evolucao(base_material, metrica_evolucao, janela)
            if evolucao_material.empty:
                st.info("Não há dados mensais para o material selecionado.")
            else:
                evolucao_material_plot = preparar_rotulos_linha(evolucao_material, metrica_evolucao)
                fig_material = px.line(
                    evolucao_material_plot,
                    x="MES_ANO",
                    y=metrica_evolucao,
                    markers=True,
                    text="ROTULO_GRAFICO",
                    custom_data=["ROTULO_COMPLETO"],
                    title=f"Evolução mensal - {material_selecionado}",
                )
                fig_material.update_traces(
                    line=dict(width=3),
                    marker=dict(size=8),
                    textposition=evolucao_material_plot["POSICAO_ROTULO"].tolist(),
                    textfont=dict(size=12),
                    hovertemplate="%{x}<br>%{customdata[0]}<extra></extra>",
                    cliponaxis=False,
                )
                fig_material.update_layout(
                    xaxis_title="Mês/Ano",
                    yaxis_title=metrica_evolucao,
                    hovermode="x unified",
                    margin=dict(l=20, r=30, t=80, b=60),
                )
                if metrica_evolucao == "VALOR":
                    fig_material.update_yaxes(tickprefix="R$ ")
                st.plotly_chart(
                    fig_material,
                    use_container_width=True,
                    key="evolucao_mensal_grafico_material",
                )

excel_bytes = gerar_excel_download(
    filtrado,
    agg if "agg" in locals() else None,
    evolucao_total if "evolucao_total" in locals() else None,
)
st.download_button(
    "Baixar base filtrada (.xlsx)", data=excel_bytes,
    file_name="Base_Filtrada_Estoque_EAs.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
