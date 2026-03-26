import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import plotly.express as px
from datetime import timedelta


# =========================
# PARSE MLO XML
# =========================
def parse_mlo(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    records = []
    auto_id = 0

    def walk(node, parent_id=None, level=0, sibling_index=0):
        nonlocal auto_id

        caption = (node.get("Caption") or "").strip()
        start_raw = (node.findtext("StartDateTime") or "").strip()
        due_raw = (node.findtext("DueDateTime") or "").strip()
        idd = (node.findtext("IDD") or "").strip()

        task_id = idd if idd else f"auto_{auto_id}"
        auto_id += 1

        children = node.findall("TaskNode")

        deps = []
        for dep in node.findall("Dependency"):
            uid = (dep.findtext("UID") or "").strip()
            if uid:
                deps.append(uid)

        records.append({
            "id": task_id,
            "parent_id": parent_id,
            "level": level,
            "sibling_index": sibling_index,
            "caption": caption if caption else "(no name)",
            "start_raw": start_raw,
            "due_raw": due_raw,
            "dependencies": deps,
            "child_count": len(children),
        })

        for i, child in enumerate(children):
            walk(child, parent_id=task_id, level=level + 1, sibling_index=i)

    task_tree = root.find(".//TaskTree")
    if task_tree is None:
        raise ValueError("Nel file XML non trovo <TaskTree>.")

    for i, node in enumerate(task_tree.findall("TaskNode")):
        walk(node, parent_id=None, level=0, sibling_index=i)

    df = pd.DataFrame(records)

    # Parse date
    df["start"] = pd.to_datetime(df["start_raw"], errors="coerce")
    df["end"] = pd.to_datetime(df["due_raw"], errors="coerce")

    # Se c'è solo start -> durata 1 giorno
    mask_only_start = df["start"].notna() & df["end"].isna()
    df.loc[mask_only_start, "end"] = df.loc[mask_only_start, "start"] + pd.Timedelta(days=1)

    # Se c'è solo due -> usa due come start e +1 giorno come end
    mask_only_due = df["start"].isna() & df["end"].notna()
    df.loc[mask_only_due, "start"] = df.loc[mask_only_due, "end"]
    df.loc[mask_only_due, "end"] = df.loc[mask_only_due, "start"] + pd.Timedelta(days=1)

    return df


# =========================
# PROPAGA DATE AI PARENT
# =========================
def compute_parent_dates(df):
    """
    Se un parent non ha date, le ricava dai figli:
    - start = min(start figli)
    - end   = max(end figli)
    """
    df = df.copy()

    children_map = df.groupby("parent_id")["id"].apply(list).to_dict()
    row_map = {row["id"]: idx for idx, row in df.iterrows()}

    def fill_dates(task_id):
        idx = row_map[task_id]
        row = df.loc[idx]

        start = row["start"]
        end = row["end"]

        child_ids = children_map.get(task_id, [])
        child_starts = []
        child_ends = []

        for cid in child_ids:
            c_start, c_end = fill_dates(cid)
            if pd.notna(c_start):
                child_starts.append(c_start)
            if pd.notna(c_end):
                child_ends.append(c_end)

        if pd.isna(start) and child_starts:
            start = min(child_starts)

        if pd.isna(end) and child_ends:
            end = max(child_ends)

        df.at[idx, "start"] = start
        df.at[idx, "end"] = end
        return start, end

    root_ids = df.loc[df["parent_id"].isna(), "id"].tolist()
    for rid in root_ids:
        fill_dates(rid)

    return df


# =========================
# LABEL GERARCHICHE UNICHE
# =========================
def add_display_labels(df):
    df = df.copy()

    # percorso completo per avere label uniche
    parent_lookup = df.set_index("id")["parent_id"].to_dict()
    caption_lookup = df.set_index("id")["caption"].to_dict()
    level_lookup = df.set_index("id")["level"].to_dict()

    def build_path(task_id):
        parts = []
        current = task_id
        while current is not None:
            parts.append(caption_lookup.get(current, "(no name)"))
            current = parent_lookup.get(current)
        return " / ".join(reversed(parts))

    df["path"] = df["id"].apply(build_path)
    df["display_name"] = df.apply(
        lambda r: f'{"— " * int(r["level"])}{r["caption"]}  [{r["id"]}]',
        axis=1
    )
    return df


# =========================
# PREPARA DATI GANTT
# =========================
def prepare_gantt_dataframe(df, show_groups=True):
    df = compute_parent_dates(df)
    df = add_display_labels(df)

    # Tieni solo task con date valide
    df = df[df["start"].notna() & df["end"].notna()].copy()

    # Correggi eventuali end < start
    bad = df["end"] < df["start"]
    df.loc[bad, "end"] = df.loc[bad, "start"] + pd.Timedelta(days=1)

    # Se non vuoi mostrare i contenitori, tieni solo leaf
    if not show_groups:
        df = df[df["child_count"] == 0].copy()

    # Ordine: prima start, poi livello, poi path
    df = df.sort_values(["start", "level", "path"], ascending=[True, True, True]).copy()

    # Tipo task
    df["task_type"] = df["child_count"].apply(lambda n: "Group/Project" if n > 0 else "Task")

    return df


# =========================
# COSTRUISCI GANTT
# =========================
def build_gantt(df):
    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="display_name",
        color="task_type",
        hover_data={
            "caption": True,
            "path": True,
            "start": True,
            "end": True,
            "id": True,
            "parent_id": True,
            "child_count": True,
            "display_name": False,
            "task_type": True,
        },
    )

    fig.update_yaxes(autorange="reversed")

    fig.update_layout(
        height=max(700, int(len(df) * 28)),
        xaxis_title="Timeline",
        yaxis_title="Tasks",
        legend_title="Type",
        bargap=0.25,
    )

    return fig


# =========================
# UI
# =========================
st.set_page_config(layout="wide")
st.title("MLO → Gantt Viewer")

st.write(
    "Carica un file XML di MyLifeOrganized. "
    "Il grafico mostra solo task con date valide o ricostruibili dai figli."
)

uploaded_file = st.file_uploader("Carica file XML MLO", type=["xml"])

if uploaded_file is not None:
    try:
        raw_df = parse_mlo(uploaded_file)

        col1, col2 = st.columns(2)
        with col1:
            show_groups = st.checkbox("Mostra anche i task contenitori/progetti", value=True)
        with col2:
            show_table = st.checkbox("Mostra tabella dati", value=True)

        gantt_df = prepare_gantt_dataframe(raw_df, show_groups=show_groups)

        st.write(f"Task totali nel file: **{len(raw_df)}**")
        st.write(f"Task mostrati nel Gantt: **{len(gantt_df)}**")

        if len(gantt_df) == 0:
            st.warning(
                "Non ho trovato task con date sufficienti per costruire il Gantt."
            )
        else:
            fig = build_gantt(gantt_df)
            st.plotly_chart(fig, use_container_width=True)

            if show_table:
                st.subheader("Dati usati nel Gantt")
                st.dataframe(
                    gantt_df[
                        [
                            "display_name",
                            "caption",
                            "id",
                            "parent_id",
                            "start",
                            "end",
                            "child_count",
                            "task_type",
                            "path",
                        ]
                    ],
                    use_container_width=True,
                )

    except Exception as e:
        st.error(f"Errore: {e}")
