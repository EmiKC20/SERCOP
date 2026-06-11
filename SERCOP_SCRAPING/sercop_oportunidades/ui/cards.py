"""Reusable Streamlit presentation components."""

from __future__ import annotations

from html import escape
import json
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def render_summary_metrics(frame: pd.DataFrame) -> None:
    """Render top-level dashboard metrics."""
    total = len(frame)
    total_value = float(frame["monto"].fillna(0).sum()) if "monto" in frame else 0.0
    high_relevance = int((frame["score"] >= 70).sum()) if "score" in frame else 0
    latest_publication = None

    if "fecha_publicacion" in frame and not frame.empty:
        publication_dates = pd.to_datetime(frame["fecha_publicacion"], errors="coerce").dropna()
        if not publication_dates.empty:
            latest_publication = publication_dates.max().strftime("%Y-%m-%d")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Procesos", f"{total:,}")
    col2.metric("Presupuesto total", f"${total_value:,.0f}")
    col3.metric("Publicacion reciente", latest_publication or "N/D")
    col4.metric("Alta relevancia", f"{high_relevance:,}")


def render_copyable_process_code(process_code: str) -> None:
    """Render a process code with a browser-side copy button."""
    safe_code = escape(process_code)
    safe_code_attr = escape(process_code, quote=True)
    components.html(
        f"""
        <div style="display:flex;align-items:center;gap:8px;font-family:Arial,sans-serif;font-size:13px;color:#51545a;">
            <span>Codigo proceso: <strong>{safe_code}</strong></span>
            <button
                type="button"
                data-code="{safe_code_attr}"
                onclick="copyProcessCode(this)"
                style="border:1px solid #d7dce2;background:#fff;border-radius:6px;padding:4px 10px;cursor:pointer;color:#2f3337;"
            >Copiar</button>
        </div>
        <script>
        function copyProcessCode(button) {{
            navigator.clipboard.writeText(button.dataset.code);
            button.textContent = 'Copiado';
            setTimeout(function () {{
                button.textContent = 'Copiar';
            }}, 1200);
        }}
        </script>
        """,
        height=36,
    )


def render_process_detail(row: dict[str, Any]) -> None:
    """Render the expanded detail panel for a selected process."""
    ocid = row.get("ocid", "")
    st.subheader(row.get("objeto") or row.get("titulo") or ocid)
    st.caption(f"{row.get('entidad', 'Sin entidad')} - {row.get('tipo_proceso', 'Sin tipo')}")

    publication_date = pd.to_datetime(row.get("fecha_publicacion"), errors="coerce")
    col1, col2, col3 = st.columns(3)
    col1.metric("Score", f"{float(row.get('score') or 0):.0f}/100")
    col2.metric("Presupuesto ref.", f"${float(row.get('monto') or 0):,.0f}")
    col3.metric("Fecha publicacion", "N/D" if pd.isna(publication_date) else publication_date.strftime("%Y-%m-%d"))

    process_code = row.get("codigo_proceso") or "N/D"
    state_source = row.get("fuente_estado") or "Datos abiertos SERCOP/OCDS"
    render_copyable_process_code(process_code)
    st.caption(
        f"Fase OCDS: {row.get('fase') or 'N/D'} | Estado OCDS: {row.get('estado') or 'N/D'} | "
        f"Fuente: {state_source}"
    )

    st.write(row.get("descripcion") or "Sin descripcion completa disponible.")

    breakdown = row.get("score_desglose") or {}
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except json.JSONDecodeError:
            breakdown = {}
    st.json(breakdown, expanded=False)

    keywords = row.get("keywords_detectadas") or []
    if isinstance(keywords, list) and keywords:
        st.caption("Keywords detectadas: " + ", ".join(keywords[:12]))

    link = row.get("url")
    if link:
        st.link_button("Abrir ficha OCDS", link, use_container_width=True)

    soce_link = row.get("url_soce")
    if soce_link:
        st.link_button("Verificar estado en SOCE", soce_link, use_container_width=True)

    reviewed = st.session_state.setdefault("reviewed_ocids", set())
    button_label = "Quitar marca de revisado" if ocid in reviewed else "Marcar como revisado"
    if st.button(button_label, key=f"review-{ocid}", use_container_width=True):
        if ocid in reviewed:
            reviewed.remove(ocid)
        else:
            reviewed.add(ocid)
        st.rerun()
