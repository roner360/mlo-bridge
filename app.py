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
