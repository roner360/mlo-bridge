import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# 1. PARSE XML MLO
# =========================
def parse_mlo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    tasks = []
    id_counter = 0

    def walk(node, parent_id=None):
        nonlocal id_counter
        caption = node.get("Caption", "").strip()
        start = node.findtext("StartDateTime")
        due = node.findtext("DueDateTime")
        
        # ID univoco da MLO (IDD) o generato
        task_id = node.findtext("IDD")
        if not task_id:
            task_id = f"auto_{id_counter}"
        id_counter += 1

        tasks.append({
            "id": str(task_id),
            "content": caption if caption else "(senza nome)",
            "parent": str(parent_id) if parent_id else None,
            "start": start,
            "end": due
        })

        # Ricorsione sui figli
        for child in node.findall("TaskNode"):
            walk(child, task_id)

    # Inizia la scansione dal TaskTree
    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            walk(node)

    df = pd.DataFrame(tasks)
    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["end"], errors="coerce")

    return normalize_dates(df)

# =========================
# 2. NORMALIZE DATES
# =========================
def normalize_dates(df):
    today = datetime.today().date()
    new_starts, new_ends = [], []

    for _, row in df.iterrows():
        start, end = row["start"], row["end"]

        if pd.isna(start) and pd.isna(end):
            s, e = datetime.combine(today, datetime.min.time()), datetime.combine(today, datetime.max.time())
        elif pd.notna(start) and pd.isna(end):
            s, e = start, start + timedelta(hours=2)
        elif pd.isna(start) and pd.notna(end):
            s, e = end - timedelta(hours=2), end
        elif start == end:
            s, e = datetime.combine(start.date(), datetime.min.time()), datetime.combine(start.date(), datetime.max.time())
        else:
            s, e = start, end

        new_starts.append(s)
        new_ends.append(e)

    df["start"], df["end"] = new_starts, new_ends
    return df

# =========================
# 3. BUILD GANTT-STYLE HTML
# =========================
def build_html_timeline(df):
    items = []
    links = []

    for _, row in df.iterrows():
        items.append({
            "id": row["id"],
            "content": row["content"],
            "start": row["start"].strftime("%Y-%m-%d %H:%M:%S"),
            "end": row["end"].strftime("%Y-%m-%d %H:%M:%S"),
            "className": "parent-task" if row["id"] in df["parent"].values else "child-task"
        })
        # Logica richiesta: Freccia da FIGLIO a GENITORE
        if row["parent"]:
            links.append({"from": row["id"], "to": row["parent"]})

    items_json = json.dumps(items)
    links_json = json.dumps(links)

    # Usiamo le doppie parentesi graffe {{ }} per non far arrabbiare Python
    return f"""
    <div id="visualization" style="position: relative; border: 1px solid #ddd; background: #fafafa; border-radius: 8px;">
        <div id="mytimeline"></div>
        <svg id="svg-canvas" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 99;"></svg>
    </div>

    <style>
        .vis-item {{ border-radius: 4px; font-size: 12px; }}
        .parent-task {{ background-color: #e1f5fe; border-color: #03a9f4; font-weight: bold; }}
        .child-task {{ background-color: #ffffff; border-color: #90caf9; }}
        .vis-foreground .vis-group {{ border-bottom: 1px solid #eee; }}
    </style>

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
            margin: {{ item: 20, axis: 20 }}
        }};

        const timeline = new vis.Timeline(container, items, options);

        function drawArrows() {{
            // Pulizia SVG e definizione freccia
            svg.innerHTML = `
                <defs>
                    <marker id="arrowhead" markerWidth="8" markerHeight="5" refX="8" refY="2.5" orient="auto">
                        <polygon points="0 0, 8 2.5, 0 5" fill="#444" />
                    </marker>
                </defs>`;
            
            const containerRect = container.getBoundingClientRect();

            links.forEach(link => {{
                const fromEl = container.querySelector(`[data-id="${{link.from}}"]`);
                const toEl = container.querySelector(`[data-id="${{link.to}}"]`);

                if (fromEl && toEl) {{
                    const r1 = fromEl.getBoundingClientRect();
                    const r2 = toEl.getBoundingClientRect();

                    // Punto di uscita (centro-sopra del figlio)
                    const x1 = r1.left + (r1.width / 2) - containerRect.left;
                    const y1 = r1.top - containerRect.top;

                    // Punto di entrata (centro-sotto del genitore)
                    const x2 = r2.left + (r2.width / 2) - containerRect.left;
                    const y2 = r2.bottom - containerRect.top;

                    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                    // Disegna una curva morbida "S-shape"
                    const d = `M ${{x1}} ${{y1}} C ${{x1}} ${{y1 - 20}}, ${{x2}} ${{y2 + 20}}, ${{x2}} ${{y2}}`;
                    
                    path.setAttribute("d", d);
                    path.setAttribute("stroke", "#666");
                    path.setAttribute("stroke-width", "1");
                    path.setAttribute("fill", "none");
                    path.setAttribute("marker-end", "url(#arrowhead)");
                    svg.appendChild(path);
                }}
            }});
        }}

        // Ridisegna quando la timeline cambia o si sposta
        timeline.on('changed', () => setTimeout(drawArrows, 150));
        timeline.on('rangechanged', drawArrows);
        window.addEventListener('resize', drawArrows);
        setTimeout(drawArrows, 600);
    </script>
    """

# =========================
# 4. STREAMLIT UI
# =========================
st.set_page_config(layout="wide", page_title="MLO Gantt View")
st.title("📊 MLO → Gantt (Child-to-Parent)")

file = st.file_uploader("Carica l'export XML di MLO", type=["xml"])

if file:
    with st.spinner("Elaborazione gerarchia..."):
        df = parse_mlo(file)
        
        tab1, tab2 = st.tabs(["Timeline Gantt", "Dati Tabellari"])
        
        with tab1:
            st.markdown("**Tip:** Usa `Ctrl + Rotella` per zoomare. Le frecce indicano che il compito superiore dipende dal completamento dei figli.")
            html_content = build_html_timeline(df)
            st.components.v1.html(html_content, height=650, scrolling=False)
            
        with tab2:
            st.dataframe(df, use_container_width=True)
else:
    st.info("👋 Carica un file XML esportato da MyLifeOrganized per vedere le dipendenze.")
