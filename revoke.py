from pathlib import Path

# 定义要重命名的文件夹路径
folder = Path("/Users/mind/Documents/Project/乍得仿真培训/调研/001收集资料/生产运行管理实施细则")

# 删除文件名中第一个"-"前面的所有内容（包括"-"）
count = 0
for f in folder.rglob("*"):
    if f.is_file():
        # 跳过隐藏文件（以.开头的文件）
        if f.name.startswith("."):
            continue
        # 查找第一个"-"的位置
        dash_index = f.name.find("-")
        # 如果找到"-"，则删除它及前面的所有内容
        if dash_index != -1:
            新文件名 = f.name[dash_index + 1:]
            f.rename(f.with_name(新文件名))
            print(f"重命名: {f.name} -> {新文件名}")
            count += 1

print(f"\n完成！共撤销重命名 {count} 个文件")