import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px


# =========================
# PARSER MLO
# =========================
def parse_mlo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    tasks = []
    id_counter = 0

    def walk(node, parent=None, level=0):
        nonlocal id_counter

        caption = node.get("Caption", "").strip()

        start = node.findtext("StartDateTime")
        due = node.findtext("DueDateTime")

        # ID reale
        idd = node.findtext("IDD")
        if idd:
            task_id = idd.strip()
        else:
            task_id = f"auto_{id_counter}"
            id_counter += 1

        # indent visivo
        indent_name = ("— " * level) + (caption if caption else "(no name)")

        tasks.append({
            "id": task_id,
            "name": indent_name,
            "parent": parent,
            "start": start,
            "due": due
        })

        for child in node.findall("TaskNode"):
            walk(child, task_id, level + 1)

    task_tree = root.find(".//TaskTree")
    for node in task_tree.findall("TaskNode"):
        walk(node)

    return pd.DataFrame(tasks)

# =========================
# GANTT
# =========================
def build_gantt(df):
    today = datetime.today()

    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["due"], errors="coerce")

    # fallback
    df["start"] = df["start"].fillna(today)
    df["end"] = df["end"].fillna(df["start"] + timedelta(days=1))

    # ORDINAMENTO → fondamentale
    df = df.sort_values(by="start")

    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="name"
    )

    fig.update_yaxes(autorange="reversed")

    # miglior visibilità
    fig.update_layout(
        height=1200,  # importante
        showlegend=False
    )

    return fig


# =========================
# UI STREAMLIT
# =========================
st.set_page_config(layout="wide")
st.title("MLO → Gantt Viewer (MVP)")

uploaded_file = st.file_uploader("Carica file XML MLO", type=["xml"])

if uploaded_file:
    df = parse_mlo(uploaded_file)

    st.subheader("📋 Tasks")
    st.dataframe(df, use_container_width=True)

    st.subheader("📊 Gantt Chart")
    fig = build_gantt(df)
    st.plotly_chart(fig, use_container_width=True)
