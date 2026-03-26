import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json


# =========================
# PARSE XML MLO
# =========================
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

    # parsing date
    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"] = pd.to_datetime(df["end"], errors="coerce")

    # normalizzazione
    df = normalize_dates(df)

    return df


# =========================
# NORMALIZE DATES (FIX GANTT)
# =========================
def normalize_dates(df):
    today = datetime.today().date()

    new_starts = []
    new_ends = []

    for _, row in df.iterrows():
        start = row["start"]
        end = row["end"]

        # entrambi vuoti → today full-day
        if pd.isna(start) and pd.isna(end):
            start_dt = datetime.combine(today, datetime.min.time())
            end_dt = datetime.combine(today, datetime.max.time())

        # solo start → minimo 1 ora
        elif pd.notna(start) and pd.isna(end):
            start_dt = start
            end_dt = start + timedelta(hours=1)

        # solo due → minimo 1 ora
        elif pd.isna(start) and pd.notna(end):
            start_dt = end
            end_dt = end + timedelta(hours=1)

        # start == end → full day
        elif start == end:
            start_dt = datetime.combine(start.date(), datetime.min.time())
            end_dt = datetime.combine(start.date(), datetime.max.time())

        else:
            start_dt = start
            end_dt = end

        new_starts.append(start_dt)
        new_ends.append(end_dt)

    df["start"] = new_starts
    df["end"] = new_ends

    return df


# =========================
# BUILD TIMELINE HTML
# =========================
def build_html_timeline(df):
    import json

    items = []
    links = []

    for _, row in df.iterrows():
        items.append({
            "id": str(row["id"]),
            "content": str(row["content"]),
            "start": row["start"].strftime("%Y-%m-%d %H:%M:%S"),
            "end": row["end"].strftime("%Y-%m-%d %H:%M:%S")
        })

        if row["parent"]:
            links.append({
                "from": str(row["id"]),
                "to": str(row["parent"])
            })

    return f"""
    <div id="wrapper" style="position:relative;">
        <div id="timeline" style="height:600px;"></div>
        <svg id="arrows" style="position:absolute; top:0; left:0; width:100%; height:600px; pointer-events:none;"></svg>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet" />

    <script>
        const items = new vis.DataSet({json.dumps(items)});
        const links = {json.dumps(links)};

        const container = document.getElementById("timeline");
        const wrapper = document.getElementById("wrapper");
        const svg = document.getElementById("arrows");

        const timeline = new vis.Timeline(container, items, {{
            stack: true,
            zoomable: true,
            moveable: true
        }});

        function getItemEl(id) {{
            return container.querySelector(`.vis-item[data-id="${{id}}"]`);
        }}

        function drawArrows() {{
            svg.innerHTML = "";

            const wrapperRect = wrapper.getBoundingClientRect();

            links.forEach(link => {{
                const fromEl = getItemEl(link.from);
                const toEl = getItemEl(link.to);

                if (!fromEl || !toEl) return;

                const fromRect = fromEl.getBoundingClientRect();
                const toRect = toEl.getBoundingClientRect();

                const x1 = fromRect.right - wrapperRect.left;
                const y1 = fromRect.top + fromRect.height / 2 - wrapperRect.top;

                const x2 = toRect.left - wrapperRect.left;
                const y2 = toRect.top + toRect.height / 2 - wrapperRect.top;

                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", x1);
                line.setAttribute("y1", y1);
                line.setAttribute("x2", x2);
                line.setAttribute("y2", y2);
                line.setAttribute("stroke", "red");
                line.setAttribute("stroke-width", "2");

                svg.appendChild(line);
            }});
        }}

        timeline.on("changed", drawArrows);
        timeline.on("rangechanged", drawArrows);

        setTimeout(drawArrows, 800);
    </script>
    """

# =========================
# UI
# =========================
st.set_page_config(layout="wide")
st.title("MLO → Timeline (Coda Style)")

file = st.file_uploader("Carica file XML MLO", type=["xml"])

if file:
    df = parse_mlo(file)

    st.write("Anteprima dati")
    st.dataframe(df.head(), use_container_width=True)

    html = build_html_timeline(df)

    st.components.v1.html(html, height=650, scrolling=True)
