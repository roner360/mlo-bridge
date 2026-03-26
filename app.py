import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# 1. PARSE XML MLO (PIÙ ROBUSTO)
# =========================
def parse_mlo_robust(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        st.error(f"Errore nel leggere il file XML: {e}")
        return []

    tasks = []
    
    # MLO mette i task dentro TaskTree -> TaskNode
    # Cerchiamo ricorsivamente tutti i TaskNode
    def walk(node, parent_id=None):
        caption = node.get("Caption", "").strip()
        
        # Estraiamo le date dai tag figli del TaskNode
        start_node = node.find("StartDateTime")
        due_node = node.find("DueDateTime")
        idd_node = node.find("IDD")

        start_val = start_node.text if start_node is not None else None
        due_val = due_node.text if due_node is not None else None
        task_id = idd_node.text if idd_node is not None else f"id_{len(tasks)}"

        # Pulizia date per Pandas
        s_dt = pd.to_datetime(start_val, errors='coerce')
        e_dt = pd.to_datetime(due_val, errors='coerce')
        
        # Fallback se le date mancano (Frappe Gantt le esige)
        if pd.isna(s_dt): s_dt = datetime.now()
        if pd.isna(e_dt): e_dt = s_dt + timedelta(days=1)
        if s_dt >= e_dt: e_dt = s_dt + timedelta(hours=2)

        tasks.append({
            "id": str(task_id),
            "name": caption if caption else "(Senza Titolo)",
            "start": s_dt.strftime("%Y-%m-%d"),
            "end": e_dt.strftime("%Y-%m-%d"),
            "progress": 0,
            "dependencies": str(parent_id) if parent_id else "", # Qui la freccia va da genitore a figlio (standard Gantt)
            "is_parent": False
        })

        # Proseguiamo sui figli
        for child in node.findall("TaskNode"):
            walk(child, task_id)

    # Avvio ricerca
    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            walk(node)
    
    return tasks

# =========================
# 2. HTML GANTT
# =========================
def render_gantt(tasks_list):
    tasks_json = json.dumps(tasks_list)
    
    return f"""
    <div id="gantt-container" style="border:1px solid #ccc; background: white;">
        <svg id="gantt"></svg>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.css">

    <script>
        try {{
            const tasks = {tasks_json};
            if (tasks.length > 0) {{
                const gantt = new Gantt("#gantt", tasks, {{
                    view_mode: 'Day',
                    language: 'it',
                    column_width: 30
                }});
            }} else {{
                document.getElementById('gantt-container').innerHTML = "Nessun dato da visualizzare.";
            }}
        }} catch (err) {{
            document.getElementById('gantt-container').innerHTML = "Errore JS: " + err.message;
        }}
    </script>
    """

# =========================
# 3. UI
# =========================
st.set_page_config(layout="wide")
st.title("Debug MLO Timeline")

uploaded_file = st.file_uploader("Carica XML", type=["xml"])

if uploaded_file:
    data = parse_mlo_robust(uploaded_file)
    
    if not data:
        st.warning("⚠️ L'XML è stato letto ma non sono stati trovati task. Controlla che il file non sia vuoto.")
    else:
        st.success(f"✅ Trovati {len(data)} task!")
        
        # Visualizzazione Gantt
        st.subheader("Gantt View")
        html_code = render_gantt(data)
        st.components.v1.html(html_code, height=500)

        # Tabella di controllo per capire se i dati ci sono
        st.subheader("Tabella Dati Estratti (Debug)")
        st.table(pd.DataFrame(data).head(10))
