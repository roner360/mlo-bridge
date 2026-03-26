import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json


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

    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["end"], errors="coerce")

    today = datetime.today()

    df["start"] = df["start"].fillna(today)
    df["end"] = df["end"].fillna(df["start"] + timedelta(days=1))

    return df


def build_html_timeline(df):
    import json

    items = []

    for _, row in df.iterrows():
        items.append({
            "id": str(row["id"]),
            "content": str(row["content"]),
            "start": row["start"].isoformat(),
            "end": row["end"].isoformat()
        })

    items_json = json.dumps(items)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <script src="https://unpkg.com/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
        <link href="https://unpkg.com/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet" />
    </head>

    <body>
        <div id="timeline"></div>

        <script>
            const items = new vis.DataSet({items_json});

            const container = document.getElementById('timeline');

            const options = {{
                stack: true,
                zoomable: true,
                moveable: true,
                orientation: 'top'
            }};

            new vis.Timeline(container, items, options);
        </script>

        <style>
            body {{
                margin: 0;
                padding: 0;
                background: white;
            }}

            #timeline {{
                height: 600px;
                border: 1px solid #ccc;
            }}
        </style>
    </body>
    </html>
    """

    return html

# UI
st.title("MLO → Timeline (Coda Style REAL)")

file = st.file_uploader("Upload XML")

if file:
    df = parse_mlo(file)

    html = build_html_timeline(df)

    st.components.v1.html(html, height=650)
