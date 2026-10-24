"""资料、讲义、题库脚本共用的台账、校验和 Excel 读取。"""

import os
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

# 台账固定在项目目录，不随运行时的工作目录变化；测试时可用环境变量指向临时库。
DB_PATH = Path(
    os.environ.get(  # 获取环境变量，没有则使用默认值
        # 如果存在FILE_MANAGER_DB环境变量，则使用该环境变量，否则使用默认值
        # __file__ 是 common.py
        "FILE_MANAGER_DB",
        Path(__file__).resolve().parent.parent / "data.db",
    )
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    docs_type TEXT NOT NULL,
    research_date INTEGER NOT NULL,
    serial_number INTEGER NOT NULL CHECK (serial_number >= 1),
    original_name TEXT NOT NULL,
    current_name TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    PRIMARY KEY (docs_type, research_date, serial_number)
);

CREATE TABLE IF NOT EXISTS derivatives (
    kind TEXT NOT NULL CHECK (kind IN ('JY', 'SP', 'SW')),
    serial_number INTEGER NOT NULL CHECK (serial_number >= 1),
    material_type TEXT NOT NULL DEFAULT 'ZL' CHECK (material_type = 'ZL'),
    material_date INTEGER NOT NULL,
    material_serial INTEGER NOT NULL,
    original_name TEXT NOT NULL,
    current_name TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    PRIMARY KEY (kind, serial_number),
    FOREIGN KEY (material_type, material_date, material_serial)
        REFERENCES files (docs_type, research_date, serial_number)
);
"""


def connect():
    db = sqlite3.connect(DB_PATH)  # 连接数据库
    db.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    db.executescript(SCHEMA)
    return db


def valid_date(value):
    # 明确按 2000—2099 年解释六位日期，避免 %y 的世纪分界。
    if not re.fullmatch(r"[0-9]{6}", value):
        return False
    try:
        datetime.strptime("20" + value, "%Y%m%d")
        return True
    except ValueError:
        return False


# 解析为绝对路径
def resolve_folder(folder, label):
    # expanduser把~变为绝对路径，resolve解析为绝对路径，strict=True路径不存在时抛出异常
    root = Path(folder).expanduser().resolve(strict=True)
    # 判断是否是文件夹，不是文件夹则抛出异常
    if not root.is_dir():
        raise ValueError(f"{label}路径必须是文件夹")
    return root


def iter_files(root, exclude=()):
    """按相对路径排序，返回需要处理的文件，跳过隐藏路径、快捷方式、数据库和 Office 临时文件。"""
    exclude = {Path(p).resolve() for p in exclude}
    return sorted(
        (
            p
            for p in root.rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and not any(part.startswith(".") for part in p.relative_to(root).parts)
            and not p.name.startswith("~$")
            and p.suffix.lower() != ".db"
            and p.resolve() not in exclude
        ),
        key=lambda p: p.relative_to(root).as_posix(),
    )


_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _column_index(ref):
    index = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        index = index * 26 + ord(ch) - ord("A") + 1
    return index - 1


def _text(node):
    # 只取正文，跳过拼音注音（rPh）里的文字
    parts = [t.text or "" for t in node.findall(f"{_NS}t")]
    parts += [t.text or "" for t in node.findall(f"{_NS}r/{_NS}t")]
    return "".join(parts)


def read_xlsx(path):
    """读取 xlsx 第一个工作表，返回 (Excel 行号, 该行字符串列表)，空单元格为 ""。"""
    with zipfile.ZipFile(path) as z: # z是zipfile.ZipFile对象
        names = set(z.namelist()) # set,不重复的集合
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml")) # 读出文本解析为XML
            shared = [_text(si) for si in root.findall(f"{_NS}si")]

        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        first = workbook.find(f"{_NS}sheets")[0]
        target = targets[first.get(_REL)]
        if target.startswith("/"):
            sheet_path = target.lstrip("/")
        else:
            sheet_path = str(PurePosixPath("xl") / target)
        sheet = ET.fromstring(z.read(sheet_path))

    rows = []
    for row in sheet.iter(f"{_NS}row"):
        values = {}
        for cell in row.findall(f"{_NS}c"):
            kind = cell.get("t")
            value = cell.find(f"{_NS}v")
            if kind == "inlineStr":
                inline = cell.find(f"{_NS}is")
                text = _text(inline) if inline is not None else ""
            elif value is None:
                text = ""
            elif kind == "s":
                text = shared[int(value.text)]
            else:
                text = value.text or ""
            values[_column_index(cell.get("r"))] = text.strip()
        width = max(values) + 1 if values else 0
        rows.append((int(row.get("r")), [values.get(i, "") for i in range(width)]))
    return rows
