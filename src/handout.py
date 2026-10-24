"""按对应表给讲义（JY）和视频（SP）编号，实际重命名文件并写入 SQLite 台账。"""

import argparse
import re
import sqlite3
import zipfile
from pathlib import Path

from common import connect, iter_files, read_xlsx, resolve_folder

VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".wmv"}
NUMBERED = re.compile(r"^(JY|SP|SW)([0-9]{4,})-ZL([0-9]{6})-([0-9]{4,})-(.+)$")
MATERIAL_CODE = re.compile(r"ZL([0-9]{6})-([0-9]{4,})")


def find_column(header, keyword):
    # 优先表头完全等于关键字的列，其次是包含关键字的列，必须唯一。
    for candidates in (
        [i for i, h in enumerate(header) if h == keyword],
        [i for i, h in enumerate(header) if keyword in h],
    ):
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise ValueError(f"对应表中有多列表头包含“{keyword}”")
    raise ValueError(f"对应表第一行没有“{keyword}”列")


def load_mapping(path):
    """返回 {讲义名: (资料日期, 资料序号)}，讲义名为对应表中的原文。"""
    rows = read_xlsx(path)
    if not rows:
        raise ValueError("对应表是空的")
    _, header = rows[0]
    material_col = find_column(header, "资料")
    handout_col = find_column(header, "讲义")

    mapping = {}
    for number, values in rows[1:]:
        material = values[material_col] if material_col < len(values) else ""
        handout = values[handout_col] if handout_col < len(values) else ""
        if not material and not handout:
            continue
        if not material or not handout:
            raise ValueError(f"对应表第 {number} 行资料和讲义必须同时填写")
        match = MATERIAL_CODE.search(material)
        if not match:
            raise ValueError(f"对应表第 {number} 行找不到资料编码：{material}")
        code = (int(match.group(1)), int(match.group(2)))
        if mapping.get(handout, code) != code:
            raise ValueError(f"对应表中“{handout}”对应了多份资料")
        mapping[handout] = code
    return mapping


def material_exists(db, date, serial):
    return (
        db.execute(
            "SELECT 1 FROM files WHERE docs_type = 'ZL' AND research_date = ? AND serial_number = ?",
            (date, serial),
        ).fetchone()
        is not None
    )


def rename(folder, map_path):
    root = resolve_folder(folder, "讲义")
    map_path = Path(map_path).expanduser().resolve(strict=True)
    mapping = load_mapping(map_path)
    db = connect()
    renamed = []
    try:
        files = iter_files(root, exclude=[map_path])
        skipped = []
        numbered = 0
        with db:
            for f in files:
                match = NUMBERED.fullmatch(f.name)
                if not match:
                    continue
                kind, serial, date, material_serial, original = match.groups()
                identity = (kind, int(serial), int(date), int(material_serial))
                if int(serial) < 1:
                    raise ValueError(f"已有编号不符合规则：{f}")
                if not material_exists(db, identity[2], identity[3]):
                    raise ValueError(f"已有编号对应的资料不在台账中：{f}")
                # 先登记已有编号，避免遍历顺序使新文件抢占旧编号。
                relative = f.relative_to(root).as_posix()
                row = db.execute(
                    "SELECT kind, serial_number, material_date, material_serial FROM derivatives WHERE relative_path = ?",
                    (relative,),
                ).fetchone()
                if row is not None:
                    if row != identity:
                        raise ValueError(f"文件编号与台账不一致：{relative}")
                    continue
                taken = db.execute(
                    "SELECT relative_path FROM derivatives WHERE kind = ? AND serial_number = ?",
                    (kind, int(serial)),
                ).fetchone()
                if taken is not None:
                    raise ValueError(f"编号重复：{relative} 与 {taken[0]}")
                db.execute(
                    "INSERT INTO derivatives ( kind, serial_number, material_date, material_serial, original_name, current_name, relative_path ) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (*identity, original, f.name, relative),
                )

            for f in files:
                relative = f.relative_to(root).as_posix()
                if NUMBERED.fullmatch(f.name):
                    numbered += 1
                    continue
                if db.execute(
                    "SELECT 1 FROM derivatives WHERE relative_path = ?", (relative,)
                ).fetchone():
                    raise ValueError(f"数据库竟然有这条数据！有问题{relative}")
                code = mapping.get(f.name) or mapping.get(f.stem)
                if code is None:
                    skipped.append((relative, "对应表中没有"))
                    continue
                date, material_serial = code
                if not material_exists(db, date, material_serial):
                    skipped.append(
                        (relative, f"资料 ZL{date:06d}-{material_serial:04d} 不在台账中")
                    )
                    continue
                kind = "SP" if f.suffix.lower() in VIDEO_SUFFIXES else "JY"
                serial = db.execute(
                    "SELECT COALESCE(MAX(serial_number), 0) + 1 FROM derivatives WHERE kind = ?",
                    (kind,),
                ).fetchone()[0]
                name = f"{kind}{serial:04d}-ZL{date:06d}-{material_serial:04d}-{f.name}"
                target = f.with_name(name)
                if target.exists():
                    raise ValueError(f"目标文件已存在：{target}")
                db.execute(
                    "INSERT INTO derivatives ( kind, serial_number, material_date, material_serial, original_name, current_name, relative_path ) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        kind,
                        serial,
                        date,
                        material_serial,
                        f.name,
                        name,
                        target.relative_to(root).as_posix(),
                    ),
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

    for relative, reason in skipped:
        print(f"跳过（{reason}）：{relative}")
    print(
        f"完成！共重命名 {len(renamed)} 个文件，已有编号 {numbered} 个，跳过 {len(skipped)} 个"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="讲义文件夹")
    parser.add_argument(
        "--map", required=True, type=Path, dest="map_path", help="讲义与资料的对应表（xlsx）"
    )
    args = parser.parse_args()
    try:
        rename(args.folder, args.map_path)
    except (ValueError, OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
        parser.exit(1, f"重命名失败：{exc}\n")


if __name__ == "__main__":
    main()
