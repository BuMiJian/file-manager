"""按调研日期给收集资料编号（ZL），实际重命名文件并写入 SQLite 台账。"""

import argparse
import re
import sqlite3
from pathlib import Path

from common import connect, iter_files, resolve_folder, valid_date

# 定义要重命名的文件夹路径
DEFAULT_FOLDER = Path("/Users/mind/Documents/Project/乍得仿真培训/调研/001收集资料")
DOCS_TYPE = "ZL"
NUMBERED = re.compile(r"^ZL([0-9]{6})-([0-9]{4,})-(.+)$")


# 提取调研时间
def research_date(parent, root):
    while parent != root:
        value = parent.name.split("-", 1)[0]
        if valid_date(value):
            return value
        parent = parent.parent
    return ""


# 重命名
def rename(folder):
    root = resolve_folder(folder, "资料")  # 获取绝对路径
    db = connect()  # 连接数据库
    renamed = []
    try:
        files = iter_files(root)
        skipped = []
        numbered = 0
        with db:
            for f in files:
                # 剔除已编号的文件，匹配到开都ZL
                match = NUMBERED.fullmatch(f.name)
                if not match:
                    continue
                # 匹配到日期，序号，原始文件名
                date, serial, original = match.groups()
                if not valid_date(date) or int(serial) < 1:
                    raise ValueError(f"已有编号不符合规则：{f}")
                # 先登记已有编号，避免遍历顺序使新文件抢占旧编号。
                relative = f.relative_to(root).as_posix()
                row = db.execute(
                    "SELECT docs_type, research_date, serial_number FROM files WHERE relative_path = ?",
                    (relative,),
                ).fetchone()
                identity = (DOCS_TYPE, int(date), int(serial))
                if row is not None:
                    if row != identity:
                        raise ValueError(f"文件编号与台账不一致：{relative}")
                    continue
                db.execute(
                    "INSERT INTO files ( docs_type, research_date, serial_number, original_name, current_name, relative_path ) VALUES (?, ?, ?, ?, ?, ?)",
                    (DOCS_TYPE, date, int(serial), original, f.name, relative),
                )

            for f in files:
                # 跳过已编号的文件
                relative = f.relative_to(root).as_posix()
                if NUMBERED.fullmatch(f.name):
                    numbered += 1
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
                    (DOCS_TYPE, date),
                ).fetchone()[0]
                # 生成新文件名
                name = f"{DOCS_TYPE}{date}-{serial:04d}-{f.name}"
                target = f.with_name(name)
                if target.exists():
                    raise ValueError(f"目标文件已存在：{target}")
                target_relative = target.relative_to(root).as_posix()
                db.execute(
                    "INSERT INTO files ( docs_type, research_date, serial_number, original_name, current_name, relative_path ) VALUES (?, ?, ?, ?, ?, ?)",
                    (DOCS_TYPE, date, serial, f.name, name, target_relative),
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
    # 第一个参数定义接收名，--type 写的时候传入type的值 有dest是使用dest的值，第一个参数值实效
    # default 默认值 type 类型 nargs 参数个数?为位置参数 choice 可选值 dest 参数名
    parser.add_argument("folder", nargs="?", type=Path, default=DEFAULT_FOLDER)
    args = parser.parse_args()  # 解析参数，args.folder就是folder的值
    try:
        rename(args.folder)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"重命名失败：{exc}\n")


if __name__ == "__main__":
    main()
