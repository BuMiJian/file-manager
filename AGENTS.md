# AGENTS.md

给 AI 编码助手的项目说明。

## 项目概况

Python 命令行工具：按编码规则给收集资料、讲义、视频编号重命名，并在 SQLite 台账 `data.db` 中登记。编码规则详见 `README.md`。

所有 Python 源码在 `src/` 下，从项目根目录运行；`data.db` 在项目根目录。

- `src/material.py`：收集资料（ZL），`python3 src/material.py [目录]`
- `src/handout.py`：讲义（JY）和视频（SP），`python3 src/handout.py <目录> --map 对应表.xlsx`
- `src/question.py`：题库（T），尚未实现
- `src/common.py`：台账路径、建表语句、日期校验、xlsx 读取，三个脚本共用
- 只用标准库，不要引入第三方依赖（包括 openpyxl，xlsx 用 `common.read_xlsx` 读）
- 格式化使用 Black

## 关键约束

- **会修改真实文件。** `material.py` 的 `DEFAULT_FOLDER` 指向用户真实的资料目录，不要在真实目录上运行脚本做测试。测试时在工作区内的临时目录造数据，并设置环境变量 `FILE_MANAGER_DB` 指向临时台账，测试完删除临时目录。
- **不要修改或删除 `data.db`**，它是真实台账。
- 台账表：
  - `files`：收集资料，主键 `(docs_type, research_date, serial_number)`，`docs_type` 固定为 `ZL`
  - `derivatives`：讲义、视频、三维，主键 `(kind, serial_number)`，通过外键指向 `files`
- 编码中“第一部分”必须唯一：ZL 在同一日期内唯一，JY/SP/SW 在同类型内全局唯一。
- 六位日期统一按 2000–2099 年解释（`valid_date`），不要改用 `%y`。
- 重命名与数据库写入必须保持原子性：出错时数据库回滚，且已重命名的文件要逆序还原。修改 `rename()` 时不要破坏这一点。
- 改动命名规则时，要同时考虑已登记的文件和台账数据的兼容性。

## 现状与待办

- `src/revoke.py` 是早期脚本，与当前命名规则不匹配，也不更新台账。**未经用户同意不要修改。**
- 三维文件（SW）和题库（T）尚未实现。
- `web/` 下的文件都是空的占位文件，计划用 ECharts 做“调研日期 → 资料 → 讲义/视频 → 题”的树图。

## 协作约定

- 用简体中文交流，代码注释也用中文。
- 提交信息格式：`类型: 中文描述`，例如 `feat: ...`、`chore: ...`、`fix: ...`。
