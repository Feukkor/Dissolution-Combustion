"""Validate experiment files before updating the GUI. No GUI dependencies."""
import csv
import io
import math
from pathlib import Path


class DataLoadError(ValueError):
    pass


RAW_FIELDS = {
    "溶解热": ["room_temperature(K)", "water_volume(mL)",
              "solute_molarmass(g/mol)", "solute_mass(g)", "R1(Omega)",
              "R2(Omega)", "t1(s)", "t2(s)", "current(A)"],
    "燃烧热": ["room_temperature(K)", "water_volume(mL)", "cotton_mass(g)",
              "combustible_mass(g)", "Nickel_before_mass(g)", "Nickel_after_mass(g)"],
}
FIT_FIELDS = ["water_volume(mL)", "water_density(g/mL)", "solute_mass(g)",
              "solute_molarmass(g/mol)", "dissolution_heat(kJ)"]


def read_rows(path):
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise DataLoadError(f"无法读取文件，请检查文件是否存在、是否有读取权限。\n{error}") from error
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise DataLoadError("编码错误：文件是 UTF-16/UTF-32 编码，请另存为 UTF-8 文本或 CSV。")
    if raw.startswith((b"PK\x03\x04", b"\xd0\xcf\x11\xe0", b"%PDF-", b"\x89PNG", b"\xff\xd8", b"GIF8", b"MZ")):
        raise DataLoadError("文件格式错误：这不是支持的 CSV/纯文本文件。Excel、Word、PDF 或图片不能直接导入，请导出为 UTF-8 CSV；仅修改后缀无效。")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DataLoadError(f"编码错误：文件无法按 UTF-8 解码（字节位置 {error.start + 1}）。请将文本另存为 UTF-8；若是 Excel 等文件，请先导出 CSV。") from error
    if any(ord(c) < 32 and c not in "\t\r\n" for c in text):
        raise DataLoadError("文件格式错误：含有二进制控制字符，不是支持的纯文本数据。")
    rows = []
    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        for row in reader:
            if row and any(cell.strip() for cell in row):
                rows.append((reader.line_num, [cell.strip() for cell in row]))
    except csv.Error as error:
        raise DataLoadError(f"第 {reader.line_num} 行 CSV 格式错误：{error}") from error
    if not rows:
        raise DataLoadError("文件为空，没有可加载的数据。")
    return rows


def number(value, line, field):
    try:
        result = float(value)
    except ValueError as error:
        raise DataLoadError(f"第 {line} 行的 {field} 必须是数字，实际为 {value!r}。") from error
    if not math.isfinite(result):
        raise DataLoadError(f"第 {line} 行的 {field} 必须是有限数值，不能为 NaN 或无穷大。")
    return result


def load_raw(path, mode):
    rows = read_rows(path)
    for line, row in rows:
        if len(row) != 2:
            raise DataLoadError(f"{mode}数据格式错误：第 {line} 行应有 2 列，实际有 {len(row)} 列。请用英文逗号分隔，并检查是否混入计算结果。")
    parameters = {}
    headers = (["time(s)", "Delta_T(K)"], ["time(s)", "(Delta_T(K))"])
    if rows[0][1] not in headers:
        fields = RAW_FIELDS[mode]
        if len(rows) <= len(fields):
            raise DataLoadError(f"{mode}文件应包含 {len(fields)} 行参数、时间—温差表头及测量数据。")
        for line, row in rows[:len(fields)]:
            key, value = row
            if key not in fields or key in parameters:
                raise DataLoadError(f"第 {line} 行参数 {key!r} 不符合{mode}模块要求（未知或重复参数）。请检查是否选择了正确的处理模块。")
            parameters[key] = number(value, line, key)
        rows = rows[len(fields):]
    if rows[0][1] not in headers:
        raise DataLoadError(f"第 {rows[0][0]} 行表头错误，应为 time(s),Delta_T(K)。")
    data = [[number(value, line, field) for value, field in zip(row, headers[0])]
            for line, row in rows[1:]]
    # Platform endpoint selection needs six points for dissolution, four for combustion.
    minimum = 6 if mode == "溶解热" else 4
    if len(data) < minimum:
        raise DataLoadError(f"{mode}至少需要 {minimum} 个测量点，当前只有 {len(data)} 个。")
    seen = set()
    for (line, _), (timestamp, _) in zip(rows[1:], data):
        if timestamp in seen:
            raise DataLoadError(f"第 {line} 行时间 {timestamp} 重复，无法进行曲线插值。")
        seen.add(timestamp)
    return parameters, sorted(data)


def load_fit(path):
    rows = read_rows(path)
    titles = rows[0][1]
    if len(set(titles)) != len(titles):
        raise DataLoadError("溶解热拟合表头含重复列名。")
    missing = [field for field in FIT_FIELDS if field not in titles]
    if missing:
        raise DataLoadError("溶解热拟合文件缺少必要列：" + "、".join(missing) + "。请导入单轮处理生成的 dissolution.csv，而非原始温差数据。")
    data = []
    for line, row in rows[1:]:
        if len(row) != len(titles):
            raise DataLoadError(f"第 {line} 行应有 {len(titles)} 列，实际有 {len(row)} 列。")
        values = [number(row[titles.index(field)], line, field) for field in FIT_FIELDS]
        if any(value <= 0 for value in values[:4]):
            raise DataLoadError(f"第 {line} 行的水体积、密度、溶质质量和摩尔质量必须大于零。")
        data.append(values)
    if len(data) < 3:
        raise DataLoadError(f"溶解热拟合至少需要 3 轮数据，当前只有 {len(data)} 轮。")
    total = 0
    for (line, _), values in zip(rows[1:], data):
        total += values[4]
        if total == 0:
            raise DataLoadError(f"截至第 {line} 行的累计溶解热为零，无法进行倒数拟合。")
    return data
