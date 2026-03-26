import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# ==========================================
# 1. PARSER E CALCOLO RICORSIVO (BACKWARD)
# ==========================================
def process_mlo_recalculator(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    nodes_data = {}
    
    # Primo passaggio: Estrazione dati e calcolo durate
    def extract(node, parent_id=None):
        caption = node.get("Caption", "").strip() or "Task"
        idd = node.findtext("IDD")
        current_id = idd if idd else f"task_{caption}_{parent_id}"
        
        start_str = node.findtext("StartDateTime")
        due_str = node.findtext("DueDateTime")
        
        s_dt = pd.to_datetime(start_str, errors='coerce')
        e_dt = pd.to_datetime(due_str, errors='coerce')
        
        if pd.isna(s_dt): s_dt = datetime.now()
        if pd.isna(e_dt): e_dt = s_dt + timedelta(hours=23, minutes=59)
        
        # Durata reale MLO (minimo 24h come richiesto)
        duration = max(e_dt - s_dt, timedelta(hours=23, minutes=59))
        
        # Cerchiamo dipendenze UID
        dep_uid = None
        dep_node = node.find("Dependency")
        if dep_node is not None:
            dep_uid = dep_node.findtext("UID")

        nodes_data[current_id] = {
            "id": current_id,
            "name": caption,
            "mlo_start": s_dt,
            "mlo_due": e_dt,
            "duration": duration,
            "parent": parent_id,
            "predecessor_of_uid": dep_uid, # Chi io aspetto
            "calc_start": e_dt - duration,
            "calc_due": e_dt,
            "children": []
        }
        
        if parent_id and parent_id in nodes_data:
            nodes_data[parent_id]["children"].append(current_id)

        for child in node.findall("TaskNode"):
            extract(child, current_id)

    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            extract(node, "Root")

    # --- MOTORE RICORSIVO BACKWARD PASS ---
    # L'idea: Il "Due" di un predecessore = "Start" del successore
    def recalculate():
        changed = True
        while changed:
            changed = False
            for tid, node in nodes_data.items():
                
                # Regola 1: Se sono figlio, la mia fine deve essere <= inizio del genitore
                if node["parent"] and node["parent"] in nodes_data:
                    p = nodes_data[node["parent"]]
                    if node["calc_due"] > p["calc_start"]:
                        node["calc_due"] = p["calc_start"]
                        node["calc_start"] = node["calc_due"] - node["duration"]
                        changed = True
                
                # Regola 2: Se ho una dipendenza UID (io sono il successore di UID)
                # Il predecessore deve finire prima che io inizi
                for other_id, other_node in nodes_data.items():
                    if other_node["predecessor_of_uid"] == node["id"]:
                        # node è il successore, other_node è il predecessore
                        if other_node["calc_due"] > node["calc_start"]:
                            other_node["calc_due"] = node["calc_start"]
                            other_node["calc_start"] = other_node["calc_due"] - other_node["duration"]
                            changed = True

    recalculate()
    
    # Preparazione per la UI
    tasks_list = []
    links_list = []
    for tid, n in nodes_data.items():
        tasks_list.append({
            "id": n["id"],
            "content": n["name"],
            "start": n["calc_start"].strftime("%Y-%m-%d %H:%M:%S"),
            "end": n["calc_due"].strftime("%Y-%m-%d %H:%M:%S"),
            "mlo_due": n["mlo_due"].strftime("%Y-%m-%d"),
            "calc_due": n["calc_due"].strftime("%Y-%m-%d")
        })
        # Frecce Blu: Gerarchia
        if n["parent"] and n["parent"] != "Root":
            links_list.append({"from": n["id"], "to": n["parent"], "color": "#0000FF"})
        # Frecce Rosse: Dipendenza UID
        if n["predecessor_of_uid"]:
            links_list.append({"from": n["predecessor_of_uid"], "to": n["id"], "color": "#FF0000"})
            
    return tasks_list, links_list

# ==========================================
# 2. UI E COMPONENTE TIMELINE
# ==========================================
def build_html(tasks, links):
    t_json = json.dumps(tasks)
    l_json = json.dumps(links)
    return f"""
    <div id="cont" style="position: relative; background: #fff; border: 1px solid #eee;">
        <div id="t_line"></div>
        <svg id="arrows" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:10;"></svg>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet" />
    <script>
        const container = document.getElementById('t_line');
        const svg = document.getElementById('arrows');
        const items = new vis.DataSet({t_json});
        const links = {l_json};
        const timeline = new vis.Timeline(container, items, {{ 
            stack: true, height: '500px', zoomKey: 'ctrlKey' 
        }});

        function draw() {{
            svg.innerHTML = '<defs><marker id="m_red" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="red" /></marker><marker id="m_blue" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="blue" /></marker></defs>';
            const cRect = container.getBoundingClientRect();
            links.forEach(l => {{
                const f = container.querySelector(`[data-id="${{l.from}}"]`);
                const t = container.querySelector(`[data-id="${{l.to}}"]`);
                if(f && t) {{
                    const rF = f.getBoundingClientRect(); const rT = t.getBoundingClientRect();
                    const x1 = rF.left + rF.width/2 - cRect.left;
                    const y1 = rF.top + rF.height/2 - cRect.top;
                    const x2 = rT.left + rT.width/2 - cRect.left;
                    const y2 = rT.top + rT.height/2 - cRect.top;
                    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
                    const curve = (y2-y1)/2;
                    p.setAttribute("d", `M ${{x1}} ${{y1}} C ${{x1}} ${{y1+curve}}, ${{x2}} ${{y2-curve}}, ${{x2}} ${{y2}}`);
                    p.setAttribute("stroke", l.color); p.setAttribute("fill", "none"); p.setAttribute("stroke-width", "2");
                    p.setAttribute("marker-end", l.color === '#FF0000' ? "url(#m_red)" : "url(#m_blue)");
                    svg.appendChild(p);
                }}
            }});
        }}
        timeline.on('changed', () => setTimeout(draw, 100));
        timeline.on('rangechanged', draw);
        setTimeout(draw, 500);
    </script>
    """

st.set_page_config(layout="wide")
st.title("🔄 MLO Backward Date Recalculator")

uploaded = st.file_uploader("Carica XML MLO", type="xml")

if uploaded:
    tasks, links = process_mlo_recalculator(uploaded)
    
    # 1. Timeline
    st.components.v1.html(build_html(tasks, links), height=550)
    
    # 2. Tabella di Ricalcolo
    st.subheader("📋 Tabella Scadenze Ricalcolate")
    df = pd.DataFrame(tasks)[["content", "mlo_due", "calc_due"]]
    df.columns = ["Task", "Scadenza Originale (MLO)", "Nuova Scadenza (Calcolata a ritroso)"]
    
    # Evidenzia i cambiamenti
    def highlight_diff(row):
        return ['background-color: #ffcccc' if row[1] != row[2] else '' for _ in row]
    
    st.dataframe(df.style.apply(highlight_diff, axis=1), use_container_width=True)
    
    st.info("💡 Se la cella è rossa, significa che la scadenza è stata anticipata per permettere ai successori di finire in tempo.")
