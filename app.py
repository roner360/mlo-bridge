import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# 1. PARSE XML MLO
# =========================
def parse_mlo_for_gantt(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    tasks = []
    
    # Mappa per trovare i figli di ogni genitore
    parent_to_children = {}

    def walk(node, parent_id=None):
        caption = node.get("Caption", "").strip() or "(senza nome)"
        start = node.findtext("StartDateTime")
        due = node.findtext("DueDateTime")
        task_id = node.findtext("IDD") or f"id_{hash(caption)}"

        # Gestione date (Frappe Gantt vuole YYYY-MM-DD)
        # Se mancano, usiamo oggi
        s_dt = pd.to_datetime(start, errors='coerce')
        e_dt = pd.to_datetime(due, errors='coerce')
        
        if pd.isna(s_dt): s_dt = datetime.now()
        if pd.isna(e_dt): e_dt = s_dt + timedelta(days=1)
        # Frappe Gantt crasha se start == end, aggiungiamo un piccolo offset
        if s_dt == e_dt: e_dt = s_dt + timedelta(hours=1)

        tasks.append({
            "id": str(task_id),
            "name": caption,
            "start": s_dt.strftime("%Y-%m-%d"),
            "end": e_dt.strftime("%Y-%m-%d"),
            "progress": 50, # Default
            "dependencies": "", # Riempiremo dopo
            "is_parent": False
        })

        if parent_id:
            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = []
            parent_to_children[parent_id].append(str(task_id))

        for child in node.findall("TaskNode"):
            walk(child, task_id)

    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            walk(node)

    # Logica RICHIESTA: Il Genitore è il successore (dipende dai figli)
    for t in tasks:
        tid = t["id"]
        if tid in parent_to_children:
            t["dependencies"] = ", ".join(parent_to_children[tid])
            t["is_parent"] = True

    return tasks

# =========================
# 2. BUILD FRAPPE GANTT HTML
# =========================
def render_frappe_gantt(tasks):
    tasks_json = json.dumps(tasks)
    
    return f"""
    <div id="gantt-container" style="overflow: auto; background: white; border-radius: 8px;">
        <svg id="gantt"></svg>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.css">

    <style>
        .gantt .bar-progress {{ fill: #a3a3ff; }}
        .gantt .bar {{ fill: #5e64ff; }}
        .gantt .bar-wrapper.parent-task .bar {{ fill: #ffbb00; }}
        .details-container {{ font-family: sans-serif; }}
    </style>

    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            const tasks = {tasks_json};
            
            const gantt = new Gantt("#gantt", tasks, {{
                header_height: 50,
                column_width: 30,
                step: 24,
                view_modes: ['Day', 'Week', 'Month'],
                view_mode: 'Day',
                language: 'it',
                custom_popup_html: function(task) {{
                    return `
                        <div class="details-container" style="padding:10px; width:200px;">
                            <h5>${{task.name}}</h5>
                            <p>Inizio: ${{task.start}}</p>
                            <p>Fine: ${{task.end}}</p>
                        </div>
                    `;
                }}
            }});

            // Aggiungiamo una classe CSS ai genitori per colorarli diversamente
            tasks.forEach(t => {{
                if(t.is_parent) {{
                   const el = document.querySelector(`[data-id="${{t.id}}"]`);
                   if(el) el.classList.add('parent-task');
                }}
            }});
        }});
    </script>
    """

# =========================
# 3. STREAMLIT UI
# =========================
st.set_page_config(layout="wide", page_title="MLO Frappe Gantt")

st.title("🏗️ MLO Gantt Module (Frappe Engine)")
st.write("Le frecce sono generate nativamente: dai figli verso il genitore.")

file = st.file_uploader("Carica XML MLO", type=["xml"])

if file:
    tasks = parse_mlo_for_gantt(file)
    
    if tasks:
        html_code = render_frappe_gantt(tasks)
        # Importante: height deve essere sufficiente a contenere il grafico
        st.components.v1.html(html_code, height=600, scrolling=True)
        
        with st.expander("Vedi dati JSON"):
            st.json(tasks)
    else:
        st.error("Nessun task trovato nell'XML.")
else:
    st.info("Carica un file per iniziare.")
