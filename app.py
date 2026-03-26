import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta

# =========================
# 1. PARSER XML -> MERMAID
# =========================
def parse_mlo_to_mermaid(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        st.error(f"Errore XML: {e}")
        return ""

    tasks = []
    node_to_id = {}
    counter = 1

    # Primo passaggio: Mappatura ID sicuri
    def map_ids(node):
        nonlocal counter
        task_id = f"task_{counter}"
        node_to_id[node] = task_id
        counter += 1
        for child in node.findall("TaskNode"):
            map_ids(child)

    # Secondo passaggio: Estrazione dati
    def walk(node, parent_id=None):
        caption = node.get("Caption", "").replace(":", "-").strip() or "Senza Titolo"
        current_id = node_to_id[node]
        
        start_val = node.findtext("StartDateTime")
        due_val = node.findtext("DueDateTime")

        s_dt = pd.to_datetime(start_val, errors='coerce')
        e_dt = pd.to_datetime(due_val, errors='coerce')

        # Fallback date per Mermaid (YYYY-MM-DD)
        if pd.isna(s_dt): s_dt = datetime.now()
        if pd.isna(e_dt): e_dt = s_dt + timedelta(days=1)
        
        # Calcoliamo la durata in giorni (Mermaid preferisce la durata)
        duration_days = max(1, (e_dt - s_dt).days)

        # Trova i figli per le dipendenze
        children = node.findall("TaskNode")
        child_ids = [node_to_id[c] for c in children]

        tasks.append({
            "id": current_id,
            "name": caption,
            "start": s_dt.strftime("%Y-%m-%d"),
            "duration": f"{duration_days}d",
            "dependencies": child_ids, # Il genitore dipende dai figli
            "is_parent": len(children) > 0
        })

        for child in children:
            walk(child, current_id)

    task_tree = root.find(".//TaskTree")
    if task_tree is not None:
        for node in task_tree.findall("TaskNode"):
            map_ids(node)
            walk(node)

    # Costruzione della stringa Mermaid
    mermaid_code = "gantt\n"
    mermaid_code += "    title MLO Gantt (Child -> Parent)\n"
    mermaid_code += "    dateFormat  YYYY-MM-DD\n"
    mermaid_code += "    axisFormat  %d/%m\n\n"

    for t in tasks:
        # Se ha dipendenze (figli), usiamo 'after'
        if t["dependencies"]:
            dep_str = "after " + " ".join(t["dependencies"])
            mermaid_code += f"    {t['name']} :{t['id']}, {dep_str}, {t['duration']}\n"
        else:
            # Task semplice senza dipendenze
            mermaid_code += f"    {t['name']} :{t['id']}, {t['start']}, {t['duration']}\n"

    return mermaid_code

# =========================
# 2. HTML RENDERER
# =========================
def render_mermaid(code):
    return f"""
    <div class="mermaid" style="background: white; padding: 20px; border-radius: 10px;">
        {code}
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ 
            startOnLoad: true,
            theme: 'default',
            gantt: {{
                barHeight: 30,
                fontSize: 12,
                useMaxWidth: false
            }}
        }});
    </script>
    """

# =========================
# 3. STREAMLIT UI
# =========================
st.set_page_config(layout="wide")
st.title("🚀 MLO Gantt con Mermaid.js")

uploaded = st.file_uploader("Carica file XML MLO", type="xml")

if uploaded:
    mermaid_string = parse_mlo_to_mermaid(uploaded)
    
    if mermaid_string:
        with st.expander("Vedi Codice Mermaid (Debug)"):
            st.code(mermaid_string)
        
        st.components.v1.html(render_mermaid(mermaid_string), height=800, scrolling=True)
    else:
        st.error("Impossibile generare il grafico. Controlla il file XML.")
