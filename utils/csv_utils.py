import csv
from pathlib import Path


def export_dict_to_csv(data: list[dict[str, str]], file_path: Path) -> None:
    """导出字典列表到 CSV 文件"""
    if not data:
        return
    with file_path.open('w') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


def load_csv_to_dict(file_path: Path) -> list[dict[str, str]]:
    """从 CSV 文件加载字典列表"""
    with file_path.open('r') as f:
        reader = csv.DictReader(f)
        return list(reader)
