import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# PARSE XML MLO
# =========================
def parse_mlo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    tasks = []
    id_counter = 0

    def walk(node, parent=None):
        nonlocal id_counter
        caption = node.get("Caption", "").strip()
        start = node.findtext("StartDateTime")
        due = node.findtext("DueDateTime")
        
        # ID univoco
        task_id = node.findtext("IDD")
        if not task_id:
            task_id = f"auto_{id_counter}"
        id_counter += 1

        tasks.append({
            "id": str(task_id),
            "content": caption if caption else "(no name)",
            "parent": str(parent) if parent else None,
            "start": start,
            "end": due
        })

        for child in node.findall("TaskNode"):
            walk(child, task_id)

    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            walk(node)

    df = pd.DataFrame(tasks)
    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["end"], errors="coerce")

    return normalize_dates(df)

# =========================
# NORMALIZE DATES
# =========================
def normalize_dates(df):
    today = datetime.today().date()
    new_starts = []
    new_ends = []

    for _, row in df.iterrows():
        start = row["start"]
        end = row["end"]

        if pd.isna(start) and pd.isna(end):
            start_dt = datetime.combine(today, datetime.min.time())
            end_dt = datetime.combine(today, datetime.max.time())
        elif pd.notna(start) and pd.isna(end):
            start_dt = start
            end_dt = start + timedelta(hours=1)
        elif pd.isna(start) and pd.notna(end):
            start_dt = end - timedelta(hours=1)
            end_dt = end
        elif start == end:
            start_dt = datetime.combine(start.date(), datetime.min.time())
            end_dt = datetime.combine(start.date(), datetime.max.time())
        else:
            start_dt = start
            end_dt = end

        new_starts.append(start_dt)
        new_ends.append(end_dt)

    df["start"] = new_starts
    df["end"] = new_ends
    return df

# =========================
# BUILD TIMELINE HTML
# =========================
def build_html_timeline(df):
    items = []
    links = []

    for _, row in df.iterrows():
        items.append({
            "id": row["id"],
            "content": row["content"],
            "start": row["start"].strftime("%Y-%m-%d %H:%M:%S"),
            "end": row["end"].strftime("%Y-%m-%d %H:%M:%S")
        })
        if row["parent"]:
            links.append({"from": row["parent"], "to": row["id"]})

    items_json = json.dumps(items)
    links_json = json.dumps(links)

    # Nota: Usiamo {{ }} per le parentesi graffe letterali del JS/CSS 
    # perché siamo all'interno di una f-string di Python.
    return f"""
    <div id="visualization" style="position: relative; border: 1px solid #ddd; background: white;">
        <div id="mytimeline"></div>
        <svg id="svg-canvas" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 999;"></svg>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet" />

    <script>
        const container = document.getElementById('mytimeline');
        const svg = document.getElementById('svg-canvas');
        
        const items = new vis.DataSet({items_json});
        const links = {links_json};

        const options = {{
            stack: true,
            zoomKey: 'ctrlKey',
            width: '100%',
            height: '600px',
            editable: false,
            margin: {{ item: 15 }}
        }};

        const timeline = new vis.Timeline(container, items, options);

        function drawArrows() {{
            svg.innerHTML = '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#FF4B4B" /></marker></defs>';
            
            const containerRect = container.getBoundingClientRect();

            links.forEach(link => {{
                const fromEl = container.querySelector(`[data-id="${{link.from}}"]`);
                const toEl = container.querySelector(`[data-id="${{link.to}}"]`);

                if (fromEl && toEl) {{
                    const r1 = fromEl.getBoundingClientRect();
                    const r2 = toEl.getBoundingClientRect();

                    const x1 = r1.left + (r1.width / 2) - containerRect.left;
                    const y1 = r1.bottom - containerRect.top;
                    const x2 = r2.left + (r2.width / 2) - containerRect.left;
                    const y2 = r2.top - containerRect.top;

                    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                    // Disegna una curva a S tra i task
                    const d = `M ${{x1}} ${{y1}} C ${{x1}} ${{y1 + 20}}, ${{x2}} ${{y2 - 20}}, ${{x2}} ${{y2}}`;
                    
                    path.setAttribute("d", d);
                    path.setAttribute("stroke", "#FF4B4B");
                    path.setAttribute("stroke-width", "1.5");
                    path.setAttribute("fill", "none");
                    path.setAttribute("marker-end", "url(#arrowhead)");
                    
                    svg.appendChild(path);
                }}
            }});
        }}

        timeline.on('changed', () => setTimeout(drawArrows, 100));
        timeline.on('rangechanged', drawArrows);
        window.addEventListener('resize', drawArrows);
        setTimeout(drawArrows, 500);
    </script>
    """

# =========================
# UI STREAMLIT
# =========================
st.set_page_config(layout="wide", page_title="MLO Timeline Fix")
st.title("🚀 MLO Timeline (Fix Frecce)")

uploaded_file = st.file_uploader("Carica file XML MyLifeOrganized", type=["xml"])

if uploaded_file:
    df_tasks = parse_mlo(uploaded_file)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        st.metric("Task totali", len(df_tasks))
        if st.checkbox("Mostra Tabella"):
            st.dataframe(df_tasks[["content", "start", "end"]])
    
    with col2:
        html_code = build_html_timeline(df_tasks)
        st.components.v1.html(html_code, height=700, scrolling=True)
else:
    st.info("In attesa del file XML...")
