import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import json

# ... (Le funzioni parse_mlo e normalize_dates rimangono identiche) ...

def build_html_timeline(df):
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
            # Nota: MyLifeOrganized solitamente ha una struttura Parent -> Child. 
            # In una timeline stile Gantt, la freccia di solito va dal genitore al figlio.
            links.append({
                "from": str(row["parent"]),
                "to": str(row["id"])
            })

    # Trasformiamo in JSON per il JS
    items_json = json.dumps(items)
    links_json = json.dumps(links)

    return f"""
    <div id="visualization" style="position: relative; border: 1px solid #ddd;">
        <div id="mytimeline"></div>
        <svg id="svg-canvas" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 10;"></svg>
    </div>

    <style>
        .vis-item {{ border-color: #2b7ce9; background-color: #97c2fc; }}
        #visualization {{ overflow: hidden; }}
    </style>

    <script src="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet" />

    <script>
        const container = document.getElementById('mytimeline');
        const svg = document.getElementById('svg-canvas');
        const items = new vis.DataSet({items_json});
        const links = {links_json};

        const options = {{
            stack: true,
            horizontalScroll: true,
            zoomKey: 'ctrlKey',
            width: '100%',
            height: '600px',
            orientation: 'top'
        }};

        const timeline = new vis.Timeline(container, items, options);

        function drawArrows() {{
            svg.innerHTML = "";
            const containerRect = container.getBoundingClientRect();

            links.forEach(link => {{
                // Selettore specifico per gli item di Vis.js
                const fromEl = container.querySelector(`[data-id="${{link.from}}"]`);
                const toEl = container.querySelector(`[data-id="${{link.to}}"]`);

                if (fromEl && toEl) {{
                    const r1 = fromEl.getBoundingClientRect();
                    const r2 = toEl.getBoundingClientRect();

                    // Calcolo coordinate relative al contenitore dell'iframe
                    const x1 = r1.left + r1.width - containerRect.left;
                    const y1 = r1.top + (r1.height / 2) - containerRect.top;

                    const x2 = r2.left - containerRect.left;
                    const y2 = r2.top + (r2.height / 2) - containerRect.top;

                    // Creazione freccia SVG
                    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                    line.setAttribute("x1", x1);
                    line.setAttribute("y1", y1);
                    line.setAttribute("x2", x2);
                    line.setAttribute("y2", y2);
                    line.setAttribute("stroke", "#FF4B4B");
                    line.setAttribute("stroke-width", "2");
                    line.setAttribute("marker-end", "url(#arrowhead)");
                    
                    svg.appendChild(line);
                }}
            }});
        }}

        // Definiamo la punta della freccia nell'SVG
        svg.innerHTML += `
            <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill="#FF4B4B" />
                </marker>
            </defs>
        `;

        // Eventi per ridisegnare
        timeline.on('changed', () => setTimeout(drawArrows, 50));
        timeline.on('rangechanged', drawArrows);
        window.addEventListener('resize', drawArrows);
        
        // Initial draw
        setTimeout(drawArrows, 500);
    </script>
    """

# ... (Il resto della UI rimane uguale) ...
