"""按资料类型和日期编号，实际重命名文件并写入 SQLite 台账。"""

import argparse
import re
import sqlite3
from datetime import datetime
from pathlib import Path

# 定义要重命名的文件夹路径
DEFAULT_FOLDER = Path("/Users/mind/Documents/Project/乍得仿真培训/调研/001收集资料")
NUMBERED = re.compile(r"^([A-Z]+)([0-9]{6})-([0-9]{4,})-(.+)$")

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
"""


def valid_date(value):
    # 明确按 2000—2099 年解释六位日期，避免 %y 的世纪分界。
    if not re.fullmatch(r"[0-9]{6}", value):
        return False
    try:
        datetime.strptime("20" + value, "%Y%m%d")
        return True
    except ValueError:
        return False


# 提取调研时间
def research_date(parent, root):
    while parent != root:
        value = parent.name.split("-", 1)[0]
        if valid_date(value):
            return value
        parent = parent.parent
    return ""


def rename(folder, docs_type="ZL"):
    # 校验 CLI 参数
    # 展开～，并解析为绝对路径，如果没有找到则抛出异常
    root = Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("资料路径必须是文件夹")
    if docs_type not in ["ZL", "SP", "JY", "SW"]:
        raise ValueError("资料类型只能是 ZL、SP、JY、SW")
    db = sqlite3.connect("data.db")
    renamed = []
    try:
        db.execute(SCHEMA)
        # 过滤不重命名的文件
        files = sorted(
            (
                p
                for p in root.rglob("*")  # 递归遍历所有文件和文件夹
                if p.is_file() and not p.is_symlink()  # 必须是文件并且排除快捷方式
                # 排除隐藏文件夹
                and not any(part.startswith(".") for part in p.relative_to(root).parts)
                and not p.name.endswith((".db"))  # 排除带有这些后缀的文件
            ),
            key=lambda p: p.relative_to(root).as_posix(),
        )
        skipped = []
        with db:
            for f in files:
                # 剔除已编号的文件
                match = NUMBERED.fullmatch(f.name)
                if not match:
                    continue
                kind, date, serial, original = match.groups()
                if not valid_date(date) or int(serial) < 1:
                    raise ValueError(f"已有编号不符合规则：{f}")
                # 先登记已有编号，避免遍历顺序使新文件抢占旧编号。
                relative = f.relative_to(root).as_posix()
                row = db.execute(
                    "SELECT docs_type, research_date, serial_number FROM files WHERE relative_path = ?",
                    (relative,),
                ).fetchone()
                identity = (kind, int(date), int(serial))
                if row is not None:
                    if row != identity:
                        raise ValueError(f"文件编号与台账不一致：{relative}")
                    continue
                db.execute(
                    "INSERT INTO files ( docs_type, research_date, serial_number, original_name, current_name, relative_path ) VALUES (?, ?, ?, ?, ?, ?)",
                    (kind, date, int(serial), original, f.name, relative),
                )

            for f in files:
                # 跳过已编号的文件
                relative = f.relative_to(root).as_posix()
                if NUMBERED.fullmatch(f.name):
                    skipped.append((relative, "已有编号"))
                    continue
                if db.execute(
                    "SELECT 1 FROM files WHERE relative_path = ?", (relative,)
                ).fetchone():
                    raise ValueError(f"数据库竟然有这条数据！有问题{relative}")
                # 提取调研时间
                date = research_date(f.parent, root)
                if not date:
                    skipped.append((relative, "未找到有效日期"))
                    continue
                # 生成序号
                serial = db.execute(
                    "SELECT COALESCE(MAX(serial_number), 0) + 1 FROM files "
                    "WHERE docs_type = ? AND research_date = ?",
                    (docs_type, date),
                ).fetchone()[0]
                # 生成新文件名
                name = f"{docs_type}{date}-{serial:04d}-{f.name}"
                target = f.with_name(name)
                if target.exists():
                    raise ValueError(f"目标文件已存在：{target}")
                target_relative = target.relative_to(root).as_posix()
                db.execute(
                    "INSERT INTO files ( docs_type, research_date, serial_number, original_name, current_name, relative_path ) VALUES (?, ?, ?, ?, ?, ?)",
                    (docs_type, date, serial, f.name, name, target_relative),
                )
                f.rename(target)
                renamed.append((f, target))
    except BaseException:
        # SQLite 会回滚台账；同时恢复本次已改名的文件。
        for original, target in reversed(renamed):
            target.rename(original)
        raise
    finally:
        db.close()

    print(f"完成！共重命名 {len(renamed)} 个文件，跳过 {len(skipped)} 个文件")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=DEFAULT_FOLDER)
    parser.add_argument(
        "--type", default="ZL", dest="docs_type", choices=["ZL", "SP", "JY", "SW"]
    )
    args = parser.parse_args()
    try:
        rename(args.folder, args.docs_type)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"重命名失败：{exc}\n")


if __name__ == "__main__":
    main()
