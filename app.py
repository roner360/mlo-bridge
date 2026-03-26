import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# 1. PARSER XML (LOGICA DURATA & DIPENDENZE)
# =========================
def parse_mlo_final(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    tasks = []
    links = [] 

    # Mappa per risolvere i GUID di MLO
    def walk(node, parent_id=None):
        caption = node.get("Caption", "").strip() or "Task"
        idd = node.findtext("IDD")
        
        # Generazione ID se manca IDD (per i figli a, b, c)
        current_id = idd if idd else f"task_{caption}_{parent_id}"
        
        start_str = node.findtext("StartDateTime")
        due_str = node.findtext("DueDateTime")
        
        s_dt = pd.to_datetime(start_str, errors='coerce')
        e_dt = pd.to_datetime(due_str, errors='coerce')

        # --- VINCOLO DURATA MINIMA 23h 59m ---
        if pd.isna(s_dt): 
            s_dt = datetime.now().replace(hour=0, minute=0, second=0)
        
        min_duration = timedelta(hours=23, minutes=59)
        
        if pd.isna(e_dt) or (e_dt - s_dt) < min_duration:
            e_dt = s_dt + min_duration

        tasks.append({
            "id": current_id,
            "content": caption,
            "start": s_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": e_dt.strftime("%Y-%m-%d %H:%M:%S")
        })

        # --- FRECCE GRIGIE: Gerarchia (Figlio -> Genitore) ---
        if parent_id and parent_id != "Root":
            links.append({"from": current_id, "to": parent_id, "color": "#A0A0A0", "dash": "5,5"})

        # --- FRECCE ROSSE: Dipendenza Reale (<Dependency><UID>) ---
        dep_node = node.find("Dependency")
        if dep_node is not None:
            uid = dep_node.findtext("UID")
            if uid:
                # La freccia va dal "Predecessore" (UID) al "Successore" (current_id)
                links.append({"from": uid, "to": current_id, "color": "#FF4B4B", "dash": "0"})

        for child in node.findall("TaskNode"):
            walk(child, current_id)

    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            walk(node, "Root")

    return tasks, links

# =========================
# 2. HTML + JS (CURVE BEZIER)
# =========================
def build_gantt_ui(tasks, links):
    tasks_json = json.dumps(tasks)
    links_json = json.dumps(links)

    return f"""
    <div id="wrapper" style="position: relative; background: #ffffff;">
        <div id="timeline_main"></div>
        <svg id="svg_overlay" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 10;"></svg>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet" />

    <script>
        const container = document.getElementById('timeline_main');
        const svg = document.getElementById('svg_overlay');
        const items = new vis.DataSet({tasks_json});
        const linkData = {links_json};

        const options = {{
            stack: true,
            zoomKey: 'ctrlKey',
            horizontalScroll: true,
            height: '600px',
            margin: {{ item: 25, axis: 10 }},
            orientation: 'top'
        }};

        const timeline = new vis.Timeline(container, items, options);

        function drawArrows() {{
            svg.innerHTML = `
                <defs>
                    <marker id="head-gray" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="#A0A0A0" />
                    </marker>
                    <marker id="head-red" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="#FF4B4B" />
                    </marker>
                </defs>`;
            
            const contRect = container.getBoundingClientRect();

            linkData.forEach(link => {{
                const elFrom = container.querySelector(`[data-id="${{link.from}}"]`);
                const elTo = container.querySelector(`[data-id="${{link.to}}"]`);

                if (elFrom && elTo) {{
                    const rF = elFrom.getBoundingClientRect();
                    const rT = elTo.getBoundingClientRect();

                    // Calcolo punti (Uscita destra -> Entrata sinistra per dipendenze)
                    // O Centro-Sotto -> Centro-Sopra per gerarchia
                    const x1 = rF.left + (rF.width / 2) - contRect.left;
                    const y1 = rF.top + (rF.height / 2) - contRect.top;
                    const x2 = rT.left + (rT.width / 2) - contRect.left;
                    const y2 = rT.top + (rT.height / 2) - contRect.top;

                    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                    // Curva a "S" (Bezier cubica)
                    const offset = (y2 - y1) / 2;
                    const d = `M ${{x1}} ${{y1}} C ${{x1}} ${{y1 + offset}}, ${{x2}} ${{y2 - offset}}, ${{x2}} ${{y2}}`;
                    
                    path.setAttribute("d", d);
                    path.setAttribute("stroke", link.color);
                    path.setAttribute("stroke-width", link.color === '#FF4B4B' ? "2.5" : "1.5");
                    path.setAttribute("stroke-dasharray", link.dash);
                    path.setAttribute("fill", "none");
                    path.setAttribute("marker-end", link.color === '#FF4B4B' ? "url(#head-red)" : "url(#head-gray)");
                    svg.appendChild(path);
                }}
            }});
        }}

        timeline.on('changed', () => setTimeout(drawArrows, 50));
        timeline.on('rangechanged', drawArrows);
        window.addEventListener('resize', drawArrows);
        setTimeout(drawArrows, 500);
    </script>
    """

# =========================
# 3. APP
# =========================
st.set_page_config(layout="wide")
st.title("📊 MLO Gantt: Deep Hierarchy & Dependencies")

uploaded = st.file_uploader("Carica il tuo file XML (es. test2.xml)", type="xml")

if uploaded:
    tasks, links = parse_mlo_final(uploaded)
    
    if tasks:
        st.write(f"Barre caricate: **{len(tasks)}**. Durata minima garantita: **23h 59m**.")
        ui_html = build_gantt_ui(tasks, links)
        st.components.v1.html(ui_html, height=650)
        
        c1, c2 = st.columns(2)
        with c1:
            st.info("🔴 Linea Rossa: Dipendenza UID (test -> a)")
        with c2:
            st.info("⚪ Linea Grigia: Gerarchia (f -> c -> b -> a)")
