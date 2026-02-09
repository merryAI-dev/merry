"""
UI helpers for consistent page layout.
"""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st


def render_page_header(
    title: str,
    description: Optional[str] = None,
    kicker: Optional[str] = None,
    meta: Optional[str] = None,
) -> None:
    """Render a consistent page hero block."""
    safe_title = html.escape(title)
    safe_desc = html.escape(description) if description else ""
    safe_kicker = html.escape(kicker) if kicker else ""
    safe_meta = html.escape(meta) if meta else ""

    parts = ['<div class="page-hero">']
    if kicker:
        parts.append(f'<div class="page-hero__kicker">{safe_kicker}</div>')
    parts.append(f'<h1 class="page-hero__title">{safe_title}</h1>')
    if description:
        parts.append(f'<p class="page-hero__desc">{safe_desc}</p>')
    if meta:
        parts.append(f'<div class="page-hero__meta">{safe_meta}</div>')
    parts.append("</div>")

    st.markdown("\n".join(parts), unsafe_allow_html=True)
