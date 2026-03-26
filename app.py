import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# =========================
# 1. PARSER ROBUSTO
# =========================
def parse_mlo_safe(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        st.error(f"Errore XML: {e}")
        return []

    raw_tasks = []
    # Usiamo un contatore semplice per gli ID
    counter = 1

    def walk(node, parent_id=None):
        nonlocal counter
        
        current_id = str(counter)
        counter += 1
        
        caption = node.get("Caption", "").strip() or f"Task {current_id}"
        start_val = node.findtext("StartDateTime")
        due_val = node.findtext("DueDateTime")

        # Conversione date
        s_dt = pd.to_datetime(start_val, errors='coerce')
        e_dt = pd.to_datetime(due_val, errors='coerce')
        
        # Fallback date: se mancano, mettiamo oggi. 
        # Importante: il genitore deve finire dopo i figli.
        if pd.isna(s_dt): s_dt = datetime.now().replace(hour=9, minute=0)
        if pd.isna(e_dt): e_dt = s_dt + timedelta(hours=8)
        if s_dt >= e_dt: e_dt = s_dt + timedelta(hours=1)

        raw_tasks.append({
            "id": current_id,
            "name": caption,
            "start": s_dt,
            "end": e_dt,
            "progress": 0,
            "parent_internal": parent_id, # Usato per costruire le dipendenze
            "dependencies": []
        })

        for child in node.findall("TaskNode"):
            walk(child, current_id)

    # Trova il punto di inizio
    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            walk(node)

    if not raw_tasks:
        return []

    # LOGICA DIPENDENZE: Il Genitore dipende dai Figli
    # Creiamo un dizionario per accesso rapido
    task_dict = {t["id"]: t for t in raw_tasks}
    
    for t in raw_tasks:
        if t["parent_internal"]:
            parent = task_dict.get(t["parent_internal"])
            if parent:
                # Il genitore (parent) ha come dipendenza il figlio (t)
                parent["dependencies"].append(t["id"])
                
                # CORREZIONE DATE: Il genitore deve iniziare dopo che il figlio finisce
                if parent["start"] <= t["end"]:
                    parent["start"] = t["end"] + timedelta(hours=1)
                    if parent["end"] <= parent["start"]:
                        parent["end"] = parent["start"] + timedelta(hours=8)

    # Formattazione finale per Frappe Gantt
    final_tasks = []
    for t in raw_tasks:
        final_tasks.append({
            "id": t["id"],
            "name": t["name"],
            "start": t["start"].strftime("%Y-%m-%d"),
            "end": t["end"].strftime("%Y-%m-%d"),
            "progress": t["progress"],
            "dependencies": ", ".join(t["dependencies"]) # Trasforma lista in stringa "1, 2, 3"
        })

    return final_tasks

# =========================
# 2. HTML & JS
# =========================
def get_gantt_html(tasks):
    tasks_json = json.dumps(tasks)
    return f"""
    <div id="gantt-holder" style="background: white; border: 1px solid #eee; border-radius: 10px;">
        <svg id="gantt-target"></svg>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.css">
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            try {{
                const data = {tasks_json};
                if(data.length > 0) {{
                    const gantt = new Gantt("#gantt-target", data, {{
                        view_mode: 'Day',
                        language: 'it',
                        bar_height: 25,
                        column_width: 40
                    }});
                }}
            }} catch(e) {{
                console.error("Gantt Error:", e);
                document.getElementById('gantt-holder').innerHTML = '<p style="padding:20px; color:red;">Errore JS: ' + e.message + '</p>';
            }}
        }});
    </script>
    """

# =========================
# 3. STREAMLIT INTERFACE
# =========================
st.set_page_config(layout="wide", page_title="MLO Gantt")
st.title("📊 MLO Gantt: Genitore come Successore")

uploaded = st.file_uploader("Trascina qui il file XML di MLO", type="xml")

if uploaded:
    data = parse_mlo_safe(uploaded)
    
    if data:
        st.success(f"Analizzati {len(data)} task correttamente.")
        html = get_gantt_html(data)
        st.components.v1.html(html, height=600, scrolling=True)
        
        with st.expander("Ispeziona JSON inviato al grafico"):
            st.json(data)
    else:
        st.error("Nessun task trovato. Verifica la struttura dell'XML.")
