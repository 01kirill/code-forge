import csv
import io
from typing import Any

from codeforge.common.contracts import Document


def csv_gradebook(data: Document) -> str:
    def cell_text(cell: Document) -> str:
        labels = {
            "completed": "Завершён",
            "attempted": "Начат",
            "unstarted": "Нет попытки",
        }
        return (
            f"{labels[cell['status']]} / {cell['xp']} XP"
            f" / {cell['task_xp']} XP за задачу"
        )

    def safe(value: Any) -> Any:
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["Студент", *(safe(col["title"]) for col in data["columns"]), "Итог, %"]
    )
    for row in data["rows"]:
        writer.writerow(
            [
                safe(row["name"]),
                *(cell_text(cell) for cell in row["cells"]),
                row["percent"],
            ]
        )
    return "\ufeff" + output.getvalue()
