from pathlib import Path
import os

# 定义要重命名的文件夹路径
folder = Path("/Users/mind/Documents/Project/乍得仿真培训/调研/001收集资料")

资料前缀 = "ZL"
新文件名数组 = []
相对路径数组 = []

def main():
    计数器 = 0
    # 使用 rglob 递归遍历所有文件（包括子文件夹中的文件）
    for f in folder.rglob("*"):
        if f.is_file():
            # 跳过隐藏文件（以.开头的文件）
            if f.name.startswith("."):
                continue

            调研时间 = 提取调研时间(f.parent)
            if not 调研时间:
                # print(f"警告：{f.name}无法从路径中提取调研时间: {f.parent}")
                continue

            计数器 += 1
            # 生成4位补零的序号
            序号 = str(计数器).zfill(4)
            新文件名 = f"{资料前缀}{调研时间}-{序号}-{f.name}"
            相对路径 = os.path.relpath(
                f.with_name(新文件名),
                "/Users/mind/Documents/Project/乍得仿真培训/调研/001收集资料",
            )
            # f.rename(f.with_name(新文件名))
            # print(f"重命名: {f.name} -> {新文件名}")
            新文件名数组.append(新文件名)
            相对路径数组.append(相对路径)
    for f in 新文件名数组:
        print(f)
    # print("------------------------------------")
    # for f in 相对路径数组:
    #     print(f)
    print(f"\n完成！共重命名 {计数器} 个文件")


# 辅助函数：从路径中提取调研时间
def 提取调研时间(path: Path) -> str:
    """
    从路径中向上查找，找到第一个以 '-' 分割后第一部分为纯数字的文件夹名称
    返回该数字字符串，如果找不到则返回空字符串
    """
    current = path
    # 设置一个边界，避免无限循环（比如到达根目录或指定的基础目录）
    base_dir = Path("/Users/mind/Documents/Project/乍得仿真培训/调研/001收集资料")

    while current != base_dir and current != current.parent:
        folder_name = current.name
        parts = folder_name.split("-", 1)

        if parts and parts[0].isdigit():
            return parts[0]

        current = current.parent

    return ""  # 如果没找到，返回空字符串


if __name__ == "__main__":
    main()

# 计数器 = 0
# for f in folder.rglob("*"):
#     if f.is_file():
#         计数器 += 1

# print(计数器)
