"""Streamlit sidebar filters for the SERCOP opportunities dashboard."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from core.keywords import BUSINESS_LINES


def render_sidebar_filters() -> dict:
    """Render and return dashboard filter settings."""
    st.sidebar.header("Filtros")

    selected_lines = st.sidebar.multiselect(
        "Lineas de negocio",
        options=list(BUSINESS_LINES.keys()),
        default=list(BUSINESS_LINES.keys()),
    )

    today = date.today()
    publication_range = st.sidebar.date_input(
        "Rango de fecha de publicacion",
        value=(today - timedelta(days=60), today),
        format="YYYY-MM-DD",
    )
    if isinstance(publication_range, tuple) and len(publication_range) == 2:
        publication_start, publication_end = publication_range
    else:
        publication_start, publication_end = today - timedelta(days=60), today

    amount_range = st.sidebar.slider(
        "Monto presupuestado",
        min_value=0,
        max_value=500_000,
        value=(0, 250_000),
        step=1_000,
        format="$%d",
    )

    min_score = st.sidebar.slider("Score minimo de relevancia", 0, 100, 40, 5)

    st.sidebar.caption("Solo se muestran procesos en planeacion o licitacion segun Datos Abiertos/OCDS.")

    max_pages = st.sidebar.number_input("Paginas maximas por busqueda", min_value=1, max_value=5, value=1)
    enrich_details = st.sidebar.checkbox("Traer presupuesto referencial", value=True)
    max_detail_records = st.sidebar.number_input(
        "Presupuestos maximos por carga",
        min_value=5,
        max_value=100,
        value=50,
        disabled=not enrich_details,
    )
    refresh = st.sidebar.button("Actualizar datos", use_container_width=True)

    return {
        "selected_lines": selected_lines,
        "publication_start": publication_start,
        "publication_end": publication_end,
        "amount_min": amount_range[0],
        "amount_max": amount_range[1],
        "min_score": min_score,
        "max_pages": int(max_pages),
        "enrich_details": enrich_details,
        "max_detail_records": int(max_detail_records),
        "refresh": refresh,
    }
