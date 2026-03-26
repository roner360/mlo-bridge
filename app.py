import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px


def parse_mlo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    tasks = []

    def walk(node, parent=None):
        caption = node.get("Caption", "").strip()

        start = node.findtext("StartDateTime")
        due = node.findtext("DueDateTime")

        task = {
            "name": caption if caption else "(no name)",
            "parent": parent,
            "start": start,
            "due": due
        }

        tasks.append(task)

        for child in node.findall("TaskNode"):
            walk(child, caption)

    task_tree = root.find(".//TaskTree")
    for node in task_tree.findall("TaskNode"):
        walk(node)

    return pd.DataFrame(tasks)


def build_gantt(df):
    today = datetime.today()

    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["due"], errors="coerce")

    # fallback start
    df["start"] = df["start"].fillna(today)

    # fallback end = +1 day
    df["end"] = df["end"].fillna(df["start"] + timedelta(days=1))

    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="name",
        color="parent"
    )

    fig.update_yaxes(autorange="reversed")
    return fig


# UI
st.title("MLO → Gantt (MVP)")

file = st.file_uploader("Upload XML MLO")

if file:
    df = parse_mlo(file)

    st.subheader("Raw data")
    st.dataframe(df)

    st.subheader("Gantt")
    fig = build_gantt(df)
    st.plotly_chart(fig)
