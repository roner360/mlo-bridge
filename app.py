import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# 1. PARSER XML (LOGICA GUID)
# =========================
def parse_mlo_full(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    tasks = []
    links = [] # {from, to, type}

    # Primo passaggio: Creiamo un dizionario di tutti i task per risolvere i GUID
    def walk(node, parent_id=None):
        caption = node.get("Caption", "").strip() or "Root"
        idd = node.findtext("IDD")
        
        # Se non c'è IDD (come per i figli a, b, c), generiamo un ID basato sul nome
        # In MLO i figli "semplici" spesso non hanno IDD finché non vengono linkati
        current_id = idd if idd else f"task_{caption}_{parent_id}"
        
        start = node.findtext("StartDateTime")
        due = node.findtext("DueDateTime")
        
        s_dt = pd.to_datetime(start, errors='coerce')
        e_dt = pd.to_datetime(due, errors='coerce')
        if pd.isna(s_dt): s_dt = datetime.now()
        if pd.isna(e_dt): e_dt = s_dt + timedelta(hours=2)

        tasks.append({
            "id": current_id,
            "content": caption,
            "start": s_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": e_dt.strftime("%Y-%m-%d %H:%M:%S")
        })

        # --- FRECCE GERARCHIA (Figlio -> Genitore) ---
        if parent_id and parent_id != "Root":
            links.append({"from": current_id, "to": parent_id, "color": "#999"})

        # --- FRECCE DIPENDENZA REALE (<Dependency>) ---
        dep_node = node.find("Dependency")
        if dep_node is not None:
            uid = dep_node.findtext("UID")
            if uid:
                # La dipendenza dice: "Io (current_id) dipendo da UID"
                # Quindi la freccia va da UID a me
                links.append({"from": uid, "to": current_id, "color": "red"})

        for child in node.findall("TaskNode"):
            walk(child, current_id)

    task_tree = root.find(".//TaskTree")
    for node in task_tree.findall("TaskNode"):
        walk(node)

    return tasks, links

# =========================
# 2. COSTRUZIONE HTML + JS
# =========================
def build_gantt_with_arrows(tasks, links):
    tasks_json = json.dumps(tasks)
    links_json = json.dumps(links)

    return f"""
    <div id="visualization" style="position: relative; background: white;">
        <div id="mytimeline" style="background: #fafafa; border: 1px solid #ddd;"></div>
        <svg id="arrow-canvas" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 100;"></svg>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet" />

    <script>
        const container = document.getElementById('mytimeline');
        const svg = document.getElementById('arrow-canvas');
        const items = new vis.DataSet({tasks_json});
        const links = {links_json};

        const options = {{
            stack: true,
            zoomKey: 'ctrlKey',
            height: '600px',
            margin: {{ item: 15 }}
        }};

        const timeline = new vis.Timeline(container, items, options);

        function drawArrows() {{
            svg.innerHTML = `
                <defs>
                    <marker id="arrow-gray" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="#999" />
                    </marker>
                    <marker id="arrow-red" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="red" />
                    </marker>
                </defs>`;
            
            const containerRect = container.getBoundingClientRect();

            links.forEach(link => {{
                const fromEl = container.querySelector(`[data-id="${{link.from}}"]`);
                const toEl = container.querySelector(`[data-id="${{link.to}}"]`);

                if (fromEl && toEl) {{
                    const r1 = fromEl.getBoundingClientRect();
                    const r2 = toEl.getBoundingClientRect();

                    const x1 = r1.left + (r1.width / 2) - containerRect.left;
                    const y1 = (link.color === 'red') ? (r1.bottom - containerRect.top) : (r1.top - containerRect.top);
                    
                    const x2 = r2.left + (r2.width / 2) - containerRect.left;
                    const y2 = (link.color === 'red') ? (r2.top - containerRect.top) : (r2.bottom - containerRect.top);

                    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                    const d = `M ${{x1}} ${{y1}} C ${{x1}} ${{y1 + (y2-y1)/2}}, ${{x2}} ${{y2 - (y2-y1)/2}}, ${{x2}} ${{y2}}`;
                    
                    path.setAttribute("d", d);
                    path.setAttribute("stroke", link.color);
                    path.setAttribute("stroke-width", link.color === 'red' ? "2" : "1");
                    path.setAttribute("fill", "none");
                    path.setAttribute("marker-end", link.color === 'red' ? "url(#arrow-red)" : "url(#arrow-gray)");
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
# 3. STREAMLIT APP
# =========================
st.set_page_config(layout="wide")
st.title("📊 MLO Gantt Avanzato")
st.write("Frecce **Grigie**: Gerarchia (Figlio -> Genitore). Frecce **Rosse**: Dipendenza Reale.")

file = st.file_uploader("Carica test2.xml", type="xml")

if file:
    tasks, links = parse_mlo_full(file)
    
    if tasks:
        html = build_gantt_with_arrows(tasks, links)
        st.components.v1.html(html, height=650)
        
        with st.expander("Ispeziona Dipendenze Trovate"):
            st.write(links)
