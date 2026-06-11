"""Streamlit app for Ecuador public-procurement opportunity intelligence."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from api.sercop_client import SercopAPIError, releases_to_dataframe, search_releases
from core.keywords import balanced_search_terms
from core.scorer import score_dataframe
from ui.cards import render_process_detail, render_summary_metrics
from ui.filters import render_sidebar_filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
LOGGER = logging.getLogger(__name__)


def current_search_years() -> tuple[int, ...]:
    """Return years to search by default."""
    today = date.today()
    return (today.year,)


def normalize_dates(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize date columns for filtering and display."""
    for column in ["fecha_publicacion", "fecha_cierre"]:
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def apply_filters(frame: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply sidebar filters to the scored opportunities table."""
    if frame.empty:
        return frame

    filtered = frame.copy()
    filtered = filtered[filtered["linea_negocio"].isin(filters["selected_lines"])]
    filtered = filtered[filtered["score"] >= filters["min_score"]]
    filtered = filtered[filtered["monto"].fillna(0).between(filters["amount_min"], filters["amount_max"])]

    publication_dates = pd.to_datetime(filtered["fecha_publicacion"], errors="coerce")
    today = date.today()
    publication_start = pd.Timestamp(filters.get("publication_start", today - timedelta(days=60)))
    publication_end = pd.Timestamp(filters.get("publication_end", today)) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    in_publication_range = publication_dates.between(publication_start, publication_end)
    filtered = filtered[publication_dates.isna() | in_publication_range]

    if "fase" in filtered:
        allowed_phases = {"planeacion", "licitacion"}
        filtered = filtered[filtered["fase"].fillna("").str.lower().isin(allowed_phases)]

    reviewed = st.session_state.setdefault("reviewed_ocids", set())
    filtered["revisado"] = filtered["ocid"].isin(reviewed)
    return filtered.sort_values(["score", "monto"], ascending=[False, False])


@st.cache_data(ttl=30 * 60, show_spinner="Consultando datos abiertos del SERCOP...")
def load_opportunities(max_pages: int, enrich_details: bool, max_detail_records: int) -> pd.DataFrame:
    """Load, normalize and score SERCOP opportunities."""
    frame = releases_to_dataframe(
        search_releases(
            years=current_search_years(),
            search_terms=tuple(balanced_search_terms(max_per_line=4)),
            max_pages=max_pages,
            enrich_details=enrich_details,
            max_detail_records=max_detail_records,
        )
    )
    frame = normalize_dates(frame)
    return score_dataframe(frame)


def render_table(frame: pd.DataFrame) -> str | None:
    """Render the main opportunities table and return the selected OCID."""
    display_columns = [
        "revisado",
        "entidad",
        "objeto",
        "monto",
        "score",
        "linea_negocio",
        "fecha_publicacion",
        "fase",
        "codigo_proceso",
        "ocid",
    ]
    table = frame[display_columns].copy()
    table["fecha_publicacion"] = pd.to_datetime(table["fecha_publicacion"], errors="coerce").dt.strftime("%Y-%m-%d")
    table["fecha_publicacion"] = table["fecha_publicacion"].fillna("N/D")
    event = st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        column_config={
            "revisado": st.column_config.CheckboxColumn("Revisado"),
            "monto": st.column_config.NumberColumn("Presupuesto referencial", format="$%.0f"),
            "fecha_publicacion": st.column_config.TextColumn("Fecha publicacion"),
            "fase": st.column_config.TextColumn("Fase OCDS"),
            "codigo_proceso": st.column_config.TextColumn("Codigo proceso"),
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
            "ocid": None,
        },
    )
    selection = getattr(event, "selection", None)
    selected_rows = selection.rows if selection else []
    if selected_rows:
        return str(table.iloc[selected_rows[0]]["ocid"])
    return None


def render_charts(frame: pd.DataFrame) -> None:
    """Render distribution and score-vs-budget charts."""
    col1, col2 = st.columns(2)
    with col1:
        distribution = frame.groupby("linea_negocio", as_index=False).size()
        fig = px.bar(distribution, x="linea_negocio", y="size", labels={"size": "Procesos", "linea_negocio": ""})
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=360)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.scatter(
            frame,
            x="monto",
            y="score",
            color="linea_negocio",
            hover_data=["entidad", "tipo_proceso"],
            labels={"monto": "Monto presupuestado", "score": "Score"},
        )
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=360)
        st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    """Run the Streamlit dashboard."""
    st.set_page_config(page_title="SERCOP Oportunidades", layout="wide")
    st.title("Inteligencia de oportunidades SERCOP")

    if "reviewed_ocids" not in st.session_state:
        st.session_state.reviewed_ocids = set()

    filters = render_sidebar_filters()
    if filters["refresh"]:
        st.cache_data.clear()
        st.rerun()

    if filters["enrich_details"]:
        st.info("El presupuesto referencial se toma del detalle OCDS. Si aparece 429, reduce los presupuestos maximos o espera unos minutos.")

    st.caption(
        "Los estados provienen de Datos Abiertos SERCOP/OCDS y pueden estar desfasados frente al SOCE. "
        "Verifica el codigo del proceso en SOCE antes de tomar una decision comercial."
    )

    try:
        opportunities = load_opportunities(
            filters["max_pages"],
            filters["enrich_details"],
            filters["max_detail_records"],
        )
    except SercopAPIError as exc:
        st.error(str(exc))
        LOGGER.exception("Unable to load SERCOP opportunities")
        return

    filtered = apply_filters(opportunities, filters)
    render_summary_metrics(filtered)

    if filtered.empty:
        st.info("No hay procesos que cumplan los filtros actuales.")
        return

    selected_ocid = render_table(filtered)

    csv = filtered.drop(columns=["score_desglose", "keywords_detectadas"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("Exportar tabla filtrada a CSV", csv, "sercop_oportunidades.csv", "text/csv")

    if selected_ocid:
        with st.expander("Detalle del proceso seleccionado", expanded=True):
            row = filtered.loc[filtered["ocid"] == selected_ocid].iloc[0].to_dict()
            render_process_detail(row)

    render_charts(filtered)


if __name__ == "__main__":
    main()
