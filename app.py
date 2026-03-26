import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
from streamlit_vis_timeline import st_timeline


def parse_mlo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    tasks = []
    id_counter = 0

    def walk(node, parent=None):
        nonlocal id_counter

        caption = node.get("Caption", "").strip()

        start = node.findtext("StartDateTime")
        due = node.findtext("DueDateTime")

        # ID fallback
        task_id = node.findtext("IDD") or f"auto_{id_counter}"
        id_counter += 1

        tasks.append({
            "id": task_id,
            "content": caption if caption else "(no name)",
            "parent": parent,
            "start": start,
            "end": due
        })

        for child in node.findall("TaskNode"):
            walk(child, task_id)

    task_tree = root.find(".//TaskTree")
    for node in task_tree.findall("TaskNode"):
        walk(node)

    df = pd.DataFrame(tasks)

    # parse date
    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["end"], errors="coerce")

    today = datetime.today()

    df["start"] = df["start"].fillna(today)
    df["end"] = df["end"].fillna(df["start"] + timedelta(days=1))

    return df


def to_timeline_format(df):
    items = []

    for _, row in df.iterrows():
        items.append({
            "id": row["id"],
            "content": row["content"],
            "start": row["start"].isoformat(),
            "end": row["end"].isoformat(),
            "group": row["parent"] if row["parent"] else "root"
        })

    return items


# UI
st.title("MLO → Timeline (Coda Style)")

file = st.file_uploader("Upload XML")

if file:
    df = parse_mlo(file)

    items = to_timeline_format(df)

    st_timeline(items, height="600px")
