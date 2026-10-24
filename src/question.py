"""题库编号（T）：按讲义、视频或三维文件编号，写入 SQLite 台账。尚未实现。"""

import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    parser.exit(1, "题库功能尚未实现\n")


if __name__ == "__main__":
    main()
