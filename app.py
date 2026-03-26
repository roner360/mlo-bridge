import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# 1. PARSE XML MLO (ID GENERATI)
# =========================
def parse_mlo_to_gantt(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        st.error(f"Errore caricamento XML: {e}")
        return []

    tasks = []
    # Usiamo un dizionario per mappare i nodi XML a ID univoci generati al volo
    node_to_id = {}
    id_counter = 0

    # Funzione ricorsiva per mappare prima tutti i nodi e creare ID certi
    def map_nodes(node):
        nonlocal id_counter
        id_counter += 1
        # Cerchiamo l'IDD di MLO, se manca usiamo il contatore
        idd = node.findtext("IDD")
        node_to_id[node] = idd if idd else f"T{id_counter}"
        for child in node.findall("TaskNode"):
            map_nodes(child)

    # Funzione per estrarre i dati
    def walk(node, parent_id=None):
        caption = node.get("Caption", "").strip() or "Task Senza Nome"
        current_id = node_to_id[node]
        
        start_val = node.findtext("StartDateTime")
        due_val = node.findtext("DueDateTime")

        s_dt = pd.to_datetime(start_val, errors='coerce')
        e_dt = pd.to_datetime(due_val, errors='coerce')
        
        # Fallback date (Frappe Gantt richiede date valide)
        if pd.isna(s_dt): s_dt = datetime.now()
        if pd.isna(e_dt): e_dt = s_dt + timedelta(hours=24)
        if s_dt >= e_dt: e_dt = s_dt + timedelta(hours=1)

        task_data = {
            "id": current_id,
            "name": caption,
            "start": s_dt.strftime("%Y-%m-%d"),
            "end": e_dt.strftime("%Y-%m-%d"),
            "progress": 0,
            "dependencies": "", # Gestite dopo
            "temp_parent": parent_id
        }
        tasks.append(task_data)

        for child in node.findall("TaskNode"):
            walk(child, current_id)

    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            map_nodes(node)
            walk(node)

    # LOGICA RICHIESTA: Il Genitore è il SUCCESSORE dei figli (Frecce verso l'alto)
    # Quindi: Genitore dipende da -> Figlio1, Figlio2...
    id_list = [t["id"] for t in tasks]
    for t in tasks:
        # Cerchiamo tutti i compiti che hanno questo task come genitore
        children_ids = [c["id"] for c in tasks if c["temp_parent"] == t["id"]]
        if children_ids:
            # Il genitore dipende dai suoi figli
            t["dependencies"] = ", ".join(children_ids)

    return tasks

# =========================
# 2. RENDERER (FIX JS CRASH)
# =========================
def render_gantt(tasks):
    tasks_json = json.dumps(tasks)
    
    return f"""
    <div id="gantt-container" style="background: white; border: 1px solid #ddd; border-radius: 5px;">
        <svg id="gantt-canvas"></svg>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.css">

    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            try {{
                const taskData = {tasks_json};
                
                if (taskData.length === 0) {{
                    document.getElementById('gantt-container').innerHTML = "Nessun task trovato.";
                    return;
                }}

                const gantt = new Gantt("#gantt-canvas", taskData, {{
                    view_mode: 'Day',
                    language: 'it',
                    bar_height: 30,
                    padding: 18,
                    column_width: 30,
                    custom_popup_html: function(task) {{
                        return `
                            <div style="padding: 10px; width: 160px;">
                                <p style="font-weight: bold; margin:0;">${{task.name}}</p>
                                <p style="font-size: 11px; color: #666;">ID: ${{task.id}}</p>
                            </div>
                        `;
                    }}
                }});
            }} catch (e) {{
                console.error(e);
                document.getElementById('gantt-container').innerHTML = "Errore nel rendering: " + e.message;
            }}
        }});
    </script>
    """

# =========================
# 3. STREAMLIT APP
# =========================
st.set_page_config(layout="wide")
st.title("MLO Gantt Dependency Viewer")

uploaded_file = st.file_uploader("Carica XML MyLifeOrganized", type=["xml"])

if uploaded_file:
    with st.spinner("Analisi gerarchia MLO..."):
        tasks = parse_mlo_to_gantt(uploaded_file)
        
        if tasks:
            st.info(f"Visualizzazione di {len(tasks)} task. Le frecce indicano che il genitore segue il completamento dei figli.")
            html_content = render_gantt(tasks)
            st.components.v1.html(html_content, height=600, scrolling=True)
            
            with st.expander("Debug: Struttura Dati"):
                st.write(pd.DataFrame(tasks))
        else:
            st.warning("Nessun task trovato nell'XML.")
