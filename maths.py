# Author: 赵泽华
# 第三方库
import numpy as np
from scipy import optimize
try:
    from scipy.integrate import simps
except ImportError:
    # scipy >= 1.14 改名 simpson，兼容新旧版本
    from scipy.integrate import simpson as simps
from scipy.interpolate import BSpline, splrep

# 线性回归
# 使用scipy
def linear_regression(csv, Start: int, End: int) -> (float, float, float, float, float):
    """
    使用scipy进行线性回归，返回斜率、截距、斜率标准差、截距标准差、R平方
    """
    def equation(x, k, b):
        return k * x + b
    End += 1    # 植树问题，输入的起止点为闭区间
    N = End - Start # 散点总数
    x = csv[Start:End, 0] # 获取散点横坐标，左闭右开
    y = csv[Start:End, 1] # 获取散点纵坐标，左闭右开
    popt, pcov = optimize.curve_fit(equation, x, y)    # popt为最优拟合参数，pcov为拟合参数的协方差矩阵
    perr = np.sqrt(np.diag(pcov))   # perr为拟合参数的标准差
    k, b = popt
    stddev_k, stddev_b = perr
    # 计算拟合曲线的R平方
    residuals = y - equation(x, *popt)
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_square = 1 - (ss_res / ss_tot)
    return k, b, stddev_k, stddev_b, r_square

'''
# 线性回归
# 由数学定义计算
def linear_regression(csv, Start: int, End: int):
    End += 1    # 植树问题，输入的起止点为闭区间
    N = End - Start # 散点总数
    x = csv[Start : End, 0] # 获取散点横坐标，左闭右开
    y = csv[Start : End, 1] # 获取散点纵坐标，左闭右开
    k = (np.sum(x * y) - np.sum(x) * np.sum(y) / N) / (np.sum(np.power(x, 2)) - (np.sum(x)) ** 2 / N)   # 回归直线的斜率
    b = (np.sum(y) - k * np.sum(x)) / N # 回归直线的截距
    Sxx = np.sum(np.power(x, 2)) - np.sum(x) ** 2 / N # x的总离差平方和
    Syy = np.sum(np.power(y, 2)) - np.sum(y) ** 2 / N   # y的总离差平方和
    sr = np.sqrt((Syy - k ** 2 * Sxx) / (N - 2))  # 回归标准差
    stddev_k = np.sqrt(sr ** 2 / Sxx) # 斜率标准差
    stddev_b = sr * np.sqrt(1 / (N - np.sum(x) ** 2 / np.sum(np.power(x, 2))))    # 截距标准差
    r_square = np.sum(np.power((x * k + b - np.mean(y)), 2)) / Syy  # r^2
    return k, b, stddev_k, stddev_b, r_square
'''

# B-样条平滑曲线
def B_Spline(x, y, dx): # 平滑步长dx
    """
    创建B-样条平滑曲线，返回平滑函数
    """
    # 计算B-样条的节点和系数
    t, c, k = splrep(x, y)
    # 创建平滑函数
    smooth = BSpline(t, c, k)
    return smooth   # 返回平滑函数

# 雷诺校正点
def Reynolds(csv, Start1: int, End1: int, Start2: int, End2: int, dx: float) -> (float, float, float):  # 积分步长dx
    """
    计算雷诺校正点，返回雷诺校正点横坐标、积分面积1、积分面积2
    """
    # 依据起止点进行线性回归
    k1, b1 = linear_regression(csv, Start1, End1)[0:2]
    k2, b2 = linear_regression(csv, Start2, End2)[0:2]
    # 平滑曲线拟合
    x_csv = csv[End1:(Start2 + 1), 0] # 读取横坐标，类型为array
    y_csv = csv[End1:(Start2 + 1), 1] # 读取纵坐标，类型为array
    smooth = B_Spline(x_csv, y_csv, dx) # 创建平滑函数
    x_smooth = np.arange(x_csv.min(), x_csv.max(), dx)  # 生成平滑曲线横坐标
    """
    由2020级怎苏昂同学提供
    1/2 * k * x0^2 + b * x0 - total_integral = 0
    in which:
        k = k2 - k1
        b = b2 - b1
        total_integral = \\int_{End1}^{Start2}(k2 * x + b2 - smooth(x)) dx + 1/2 * k * x_csv.min()^2 + b * x_csv.min()
    """
    def integral_function(x, k2, b2, smooth):
        return k2 * x + b2 - smooth(x)
    k = k2 - k1
    b = b2 - b1
    integral = simps(integral_function(x_smooth, k2, b2, smooth), x_smooth)
    total_integral = integral + 1/2 * k * x_csv.min() ** 2 + b * x_csv.min()
    x0_1, x0_2 = np.roots([1/2 * k, b, -total_integral])
    x0, S1, S2 = 0.0, 0.0, 0.0
    if x0_1 >= x_csv.min() and x0_1 <= x_csv.max():
        x0 = x0_1
    else:
        x0 = x0_2
    if x0 != 0.0:
        # 计算S1和S2
        S1 = simps(integral_function(x_smooth[x_smooth <= x0], k1, b1, smooth), x_smooth[x_smooth <= x0])
        S2 = simps(integral_function(x_smooth[x_smooth >= x0], k2, b2, smooth), x_smooth[x_smooth >= x0])
    return x0, abs(S1), abs(S2)

"""
# 已弃用

# 定积分
def integration(x, y, k, b, dx):
    dS = abs((y - k * x - b) * dx - k * dx * dx * 0.5)  # 定积分，得到绝对面积
    return dS   # 返回积分结果

def Reynolds(csv, Start1: int, End1: int, Start2: int, End2: int, dx: float):  # 积分步长dx
    # 依据起止点进行线性回归
    k1, b1 = linear_regression(csv, Start1, End1)[0 : 2]
    k2, b2 = linear_regression(csv, Start2, End2)[0 : 2]
    # 平滑曲线拟合
    x_csv = csv[End1 : (Start2 + 1), 0] # 读取横坐标，类型为array
    y_csv = csv[End1 : (Start2 + 1), 1] # 读取纵坐标，类型为array
    smooth = B_Spline(x_csv, y_csv, dx) # 创建平滑函数
    x_smooth = np.arange(x_csv.min(), x_csv.max(), dx)  # 生成平滑曲线横坐标
    y_smooth = smooth(x_smooth) # 根据平滑函数生成平滑曲线纵坐标
    len_smooth = x_smooth.size  # 获取平滑曲线总散点数
    # 计算定积分
    S = [[], []]    # 两条回归直线与平滑曲线的定积分，分别以dx为步长，储存在前后两个list中
    for i in range(len_smooth):
        S[0].append(integration(x_smooth[i], y_smooth[i], k1, b1, dx))  # 以dx为步长计算第一条回归直线的定积分，存储在S[0]中
        S[1].append(integration(x_smooth[i], y_smooth[i], k2, b2, dx))  # 以dx为步长计算第二条回归直线的定积分，存储在S[1]中
    # 搜索使得两侧积分面积相等的点
    S1, S2 = 0, sum(S[1])   # 初始化两侧积分面积
    equal_point = 0
    for i in range(len_smooth):
        S1 += S[0][i]
        S2 -= S[1][i]
        if S1 >= S2:
            equal_point = i
            break
    x0 = x_smooth[equal_point]  # 获取雷诺校正点横坐标
    return x0, S1, S2
"""

# 溶解热计算
def calculate_dissolution(parameters: dict):
    '''
    从图形界面获取参数
    parameters = [file_name_extension, Start1, End1, Start2, End2, Start3, End3, T1_left, T1_right, T2_left, T2_right, temperature, water_volume, water_density, water_capacity, solute_mass, solute_molarmass, R1, R2, t1, t2, current, dissolution_heat]
    '''
    # 获取参数
    try:
        T1_left = float(parameters["T1_left"])
        T1_right = float(parameters["T1_right"])
        T2_left = float(parameters["T2_left"])
        T2_right = float(parameters["T2_right"])
        R1 = float(parameters["R1(Omega)"])
        R2 = float(parameters["R2(Omega)"])
        t1 = float(parameters["t1(s)"])
        t2 = float(parameters["t2(s)"])
        current = float(parameters["current(A)"])
    except ValueError:
        pass
    # 计算溶解热
    R = (R1 + R2) / 2
    t = t2 - t1
    Q = current ** 2 * R * t
    dissolution_heat = Q * (T1_left - T1_right) / (T2_right - T2_left) / 1000   # 单位：kJ
    parameters["dissolution_heat(kJ)"] = f"{dissolution_heat:.4f}"
    return parameters

# 溶解热回归
def dissolution_heat_regression(dissolution_csv):
    '''
    从图形界面获取参数
    dissolution_csv = [[water_volume, water_density, solute_mass, solute_molarmass, dissolution_heat], ...]

    需要计算的是水的物质的量n1、溶质的逐级物质的量sum_n2、物质的量浓度n、逐级溶解热sum_Q、积分溶解热Qs
    公式：
    n1 = ρV / 18.015
    n = n1 / sum_n2
    Qs = sum_Q / sum_n2
    '''
    # 积分溶解热
    def equation(n, Qs0, a):
        return (Qs0 * a * n) / (1 + a * n)
    n = []
    Qs = []
    sum_n2 = 0
    sum_Q = 0
    water_volume = float(dissolution_csv[0][0])
    water_density = float(dissolution_csv[0][1])
    water_molarmass = 18.015
    n1 = water_density * water_volume / water_molarmass
    for i in range(len(dissolution_csv)):
        solute_mass = float(dissolution_csv[i][2])
        solute_molarmass = float(dissolution_csv[i][3])
        sum_n2 += solute_mass / solute_molarmass
        Q = float(dissolution_csv[i][4])
        sum_Q += Q
        n.append(n1 / sum_n2)
        Qs.append(sum_Q / sum_n2)
    # 使用线性拟合确定初值
    n_p0 = np.array(np.copy(n))
    Qs_p0 = np.array(np.copy(Qs))
    n_p0 = 1 / n_p0
    Qs_p0 = 1 / Qs_p0
    Start, End = 0, len(n) - 1
    csv = np.stack((n_p0, Qs_p0), axis=1)
    k, b, stddev_k, stddev_b, r_square_p0 = linear_regression(csv, Start, End)
    p0 = [1 / b, b / k]
    # 使用scipy非线性拟合确定最优拟合参数
    popt, pcov = optimize.curve_fit(equation, n, Qs, p0=p0)    # popt为最优拟合参数，pcov为拟合参数的协方差矩阵
    perr = np.sqrt(np.diag(pcov))   # perr为拟合参数的标准差
    Qs0, a = popt
    stddev_Qs0, stddev_a = perr
    # 将n和Qs转换为numpy的array
    n = np.array(n)
    Qs = np.array(Qs)
    # 计算拟合曲线的R平方
    residuals = Qs - equation(n, *popt)
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((Qs - np.mean(Qs)) ** 2)
    r_square = 1 - (ss_res / ss_tot)
    '''
    # 以下为scipy非线性拟合
    p0 = [30, 0.25]
    if np.abs(solute_molarmass - 74.5) < 1: # 认为是KCl
        p0 = [20, 0.4]
    elif np.abs(solute_molarmass - 101.1) < 1:   # 认为是KNO3
        p0 = [40, 0.1]
    popt, pcov = optimize.curve_fit(equation, n, Qs, p0 = p0)    # popt为最优拟合参数，pcov为拟合参数的协方差矩阵
    perr = np.sqrt(np.diag(pcov))   # perr为拟合参数的标准差
    Qs0, a = popt
    stddev_Qs0, stddev_a = perr
    # 将n和Qs转换为numpy的array
    n = np.array(n)
    Qs = np.array(Qs)
    # 计算拟合曲线的R平方
    residuals = Qs - equation(n, *popt)
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((Qs - np.mean(Qs)) ** 2)
    r_square = 1 - (ss_res / ss_tot)
    '''
    '''
    # 以下为线性拟合
    n = np.array(n)
    Qs = np.array(Qs)
    n = 1 / n
    Qs = 1 / Qs
    Start, End = 0, len(n) - 1
    # 将n和Qs合并为二维array，第一列为n，第二列为Qs
    csv = np.stack((n, Qs), axis = 1)
    k, b, stddev_k, stddev_b, r_square = linear_regression(csv, Start, End)
    Qs0 = 1 / b
    a = b / k
    stddev_Qs0 = stddev_b / b ** 2
    stddev_a = np.sqrt((stddev_b / k) ** 2 + (b * stddev_k / (k ** 2)) ** 2)
    '''
    return Qs, n, Qs0, a, stddev_Qs0, stddev_a, r_square

# 积分/微分溶解/冲淡热计算
def dissolution_heat_test(Qs0, a, n_test=[200, 150, 100, 80, 50]):
    n_test = np.array(n_test)
    # 积分溶解热
    Qs_int_dissolution = (Qs0 * a * n_test) / (1 + a * n_test)
    # 积分冲淡热(取绝对值)
    Qs_int_dilution = np.diff(Qs_int_dissolution) * 1000
    # 微分溶解热
    Qs_diff_dissolution = Qs0 * (a * n_test / (1 + a * n_test)) ** 2
    # 微分冲淡热
    Qs_diff_dilution = Qs0 * a * 1000 / (1 + a * n_test) ** 2
    # 数据格式处理
    Qs_int_dissolution = np.round(Qs_int_dissolution, 2)
    Qs_int_dilution = np.round(np.abs(Qs_int_dilution), 2)
    Qs_diff_dissolution = np.round(Qs_diff_dissolution, 2)
    Qs_diff_dilution = np.round(Qs_diff_dilution, 2)
    Qs_int_dilution = np.concatenate((["NA"], Qs_int_dilution), axis=0)
    '''
    n_test = np.concatenate((["n0"], n_test), axis = 0)
    Qs_int_dissolution = np.concatenate((["int_dissolution(kJ/mol)"], Qs_int_dissolution), axis = 0)
    Qs_int_dilution = np.concatenate((["int_dilution(J/mol)", "NA"], Qs_int_dilution), axis = 0)
    Qs_diff_dissolution = np.concatenate((["diff_dissolution(kJ/mol)"], Qs_diff_dissolution), axis = 0)
    Qs_diff_dilution = np.concatenate((["diff_dilution(J/mol)"], Qs_diff_dilution), axis = 0)
    '''
    # 拼接为表格并格式化
    title = ["n0", "Qs(kJ/mol)", "Qd(J/mol)", "Qs'_n2(kJ/mol)", "Qs'_n0(J/mol)"]
    data = np.stack((n_test, Qs_int_dissolution, Qs_int_dilution, Qs_diff_dissolution, Qs_diff_dilution), axis=1)
    data = np.vstack((title, data))

    return data

# 燃烧热计算
def calculate_combustion(parameters: dict, code: str):
    '''
    从图形界面获取参数
    parameters = [file_name_extension, Start1, End1, Start2, End2, T_left, T_right, temperature, water_volume, water_density, water_capacity, combustible_mass, cotton_mass, Nickel_before_mass, Nickel_after_mass, benzoic_enthalpy, cotton_heat, Nickel_heat, constant, combustion_heat]
    '''
    # 获取参数
    try:
        T_left = float(parameters["T_left(K)"])
        T_right = float(parameters["T_right(K)"])
        temperature = float(parameters["room_temperature(K)"])
        water_volume = float(parameters["water_volume(mL)"])
        water_density = float(parameters["water_density(g/mL)"])
        water_capacity = float(parameters["water_capacity(J/gK)"])
        combustible_mass = float(parameters["combustible_mass(g)"])
        cotton_mass = float(parameters["cotton_mass(g)"])
        Nickel_before_mass = float(parameters["Nickel_before_mass(g)"])
        Nickel_after_mass = float(parameters["Nickel_after_mass(g)"])
        benzoic_enthalpy = float(parameters["benzoic_enthalpy(kJ/mol)"])
        cotton_heat = float(parameters["cotton_heat(J/g)"])
        Nickel_heat = float(parameters["Nickel_heat(J/g)"])
    except ValueError:
        pass
    # 计算燃烧热
    water_total_capacity = water_volume * water_density * water_capacity    # 单位J/K
    Q_cotton = cotton_mass * cotton_heat    # 单位J
    Q_Nickel = (Nickel_before_mass - Nickel_after_mass) * Nickel_heat    # 单位J
    if code == "constant":  # 计算量热计常数
        benzoic_heat = (benzoic_enthalpy * 1000 + 0.5 * 8.3144621 * temperature) / 122.123  # 将苯甲酸的恒压燃烧热(kJ/mol)转换为恒容燃烧热(J/g)
        Q_benzoic = (combustible_mass - cotton_mass) * benzoic_heat    # 单位J
        Q = Q_cotton + Q_Nickel + Q_benzoic
        constant = -Q / (T_right - T_left) - water_total_capacity
        parameters["constant(J/K)"] = f"{constant:.1f}"
    # 两种测量模式
    # 若修改为三种，需要修改self.Frame3_Combustion, self.combustion_mode, self.remake_file, maths.calculate_combustion
    elif code == "combustible":
        constant = float(parameters["constant(J/K)"])
        Q_x = -Q_Nickel - Q_cotton - (constant + water_total_capacity) * (T_right - T_left)    # 单位J
        combustion_heat = Q_x / (combustible_mass - cotton_mass)    # 单位J/g
        parameters["combustion_heat(J/g)"] = f"{combustion_heat:.1f}"
        '''
    # 三种测量模式
    # 若修改为两种，需要修改self.Frame3_Combustion, self.combustion_mode, self.remake_file, maths.calculate_combustion
    elif code == "combustible":
        constant = float(parameters[18])
        Q_x = -Q_Nickel - Q_cotton - (constant + water_total_capacity) * (T_right - T_left)    # 单位J
        combustion_heat = Q_x / (combustible_mass - cotton_mass)    # 单位J/g
        parameters[-1] = f"{combustion_heat:.1f}"
        '''
    elif code == "liquid":
        constant = float(parameters["constant(J/K)"])
        Q_x = -Q_Nickel - Q_cotton - (constant + water_total_capacity) * (T_right - T_left)    # 单位J
        combustion_heat = Q_x / combustible_mass    # 单位J/g
        parameters["combustion_heat(J/g)"] = f"{combustion_heat:.1f}"

# 寻找初始起止点（线性扩展法，替代原滑动窗口标准差状态机）
def _sigma_resid(csv, start, end):
    """对 csv[start:end+1] 做最小二乘线性拟合，返回残差标准差 σ_res（噪声水平）。"""
    x = csv[start:end + 1, 0]
    y = csv[start:end + 1, 1]
    if len(x) < 3:
        return 0.0
    k, b = np.polyfit(x, y, 1)
    res = y - (k * x + b)
    return res.std(ddof=2)

def find_start_end_point_linear_ext(csv, sigma_mult=3.5, margin_pts=5, min_len_s=20.0):
    """燃烧热推荐选点：线性扩展法。

    原理：雷诺校正要求前后两个拟合区间都"线性良好"。从曲线两端（前期平台 /
    后期稳态）向主升温段方向逐点扩展，用拟合残差标准差 σ_res 是否超过
    σ0 的 sigma_mult 倍（σ0 为前期噪声水平）判断"线性性"何时被破坏，
    边界处各内缩 margin_pts 点，保证选点既不进入主升温段（第二阶段）、
    又尽量保留足够多的点。

    返回 [0, End1, Start2, len-1]。
    """
    if csv is None:
        return [0, 0, 0, 0]
    n = len(csv)
    if n < 50:
        return [0, 0, n - 1, n - 1]
    step = np.median(np.diff(csv[:, 0]))
    min_len = max(3, int(round(min_len_s / step)))
    sigma0 = _sigma_resid(csv, 0, min(35, n - 1))
    thr = max(sigma_mult * sigma0, 1e-5)
    # ---- 前期拟合区间终点 End1：从 0 向后扩展 ----
    coarse = 5
    End1 = None
    for e in range(min_len, n, coarse):
        if _sigma_resid(csv, 0, e) > thr:
            End1 = e
            break
    if End1 is None:
        End1 = n - 1
    else:
        lo = max(min_len, End1 - coarse)
        for ee in range(lo, End1 + 1):
            if _sigma_resid(csv, 0, ee) > thr:
                End1 = ee
                break
    End1 = max(min_len, End1 - margin_pts)
    # ---- 后期拟合区间起点 Start2：从末尾向前扩展 ----
    Start2 = None
    for s in range(n - 1 - min_len, 0, -coarse):
        if _sigma_resid(csv, s, n - 1) > thr:
            Start2 = s
            break
    if Start2 is None:
        Start2 = 0
    else:
        hi = min(n - 1 - min_len, Start2 + coarse)
        for ss in range(hi, Start2 - 1, -1):
            if _sigma_resid(csv, ss, n - 1) > thr:
                Start2 = ss
                break
    Start2 = min(n - 1 - min_len, Start2 + margin_pts)
    if Start2 < End1 + min_len:
        Start2 = min(n - 1 - min_len, End1 + min_len)
    return [0, End1, Start2, n - 1]

def find_start_end_point_dissolution_linear_ext(csv, sigma_mult=3.5, margin_pts=5, min_len_s=20.0, k_mult=2.5, t_heat_start=None, plateau_len_s=60.0):
    """溶解热推荐选点：线性扩展法（3 区间 6 点）。

    曲线形态：P1 前基线 → 溶解吸热急降段 → P2 谷底平台 → 电加热回升段 → P3 后基线。
    返回 [0, E1, S2, E2, S3, len-1]，其中：
      E1 前平台终点 / S3 后平台起点：从两端向中间扩展，用拟合残差标准差
        σ_res 是否超过 σ0 的 sigma_mult 倍（σ0 为前期噪声水平）判断"线性性"
        被破坏的位置（同燃烧热线性扩展法）；
      E2 谷底平台右端：优先取实验记录的加热开始时间 t_heat_start（秒）
        之前 margin_pts 点；t1 缺失或不合理时，才退回以中间段全局最低点
        p_min（谷底）为锚、向右扩展"线性良好"窗口块的数据判据。
      S2 谷底平台左端：不再从 p_min 向两侧扩展（那样会把降温尾段的圆弧
        一起包进来，G4 曾因此把 S2 选到 166.8 s、仍在降温段，R² 只有 0.22），
        改为从 E2 向前取 plateau_len_s 秒的固定基线窗口，并以真实谷底和
        急降段为下界。固定窗口既保证选点数量，又不以最大化 R² 为目标而
        把区间缩到几个点。

    原滑动窗口标准差状态机对噪声阈值过敏感，会把"温漂起点"当升温起点、
    把弛豫段误判为未平稳，且选点会进入主变化段（如溶解急降段），故弃用。
    """
    if csv is None:
        return [0, 0, 0, 0, 0, 0]
    n = len(csv)
    if n < 60:
        return [0, 0, 0, 0, n - 1, n - 1]
    step = np.median(np.diff(csv[:, 0]))
    min_len = max(3, int(round(min_len_s / step)))
    sigma0 = _sigma_resid(csv, 0, min(35, n - 1))
    thr = max(sigma_mult * sigma0, 1e-5)
    coarse = 5
    # ---- E1: 前平台终点，从 0 向后扩展 ----
    E1 = None
    for e in range(min_len, n, coarse):
        if _sigma_resid(csv, 0, e) > thr:
            E1 = e
            break
    if E1 is None:
        E1 = n - 1
    else:
        lo = max(min_len, E1 - coarse)
        for ee in range(lo, E1 + 1):
            if _sigma_resid(csv, 0, ee) > thr:
                E1 = ee
                break
    E1 = max(min_len, E1 - margin_pts)
    # ---- S3: 后平台起点，从末尾向前扩展 ----
    S3 = None
    for s in range(n - 1 - min_len, E1 + 2 * min_len, -coarse):
        if _sigma_resid(csv, s, n - 1) > thr:
            S3 = s
            break
    if S3 is None:
        S3 = min(n - 1 - min_len, E1 + 2 * min_len)
    else:
        hi = min(n - 1 - min_len, S3 + coarse)
        for ss in range(hi, S3 - 1, -1):
            if _sigma_resid(csv, ss, n - 1) > thr:
                S3 = ss
                break
    S3 = min(n - 1 - min_len, S3 + margin_pts)
    if S3 < E1 + 2 * min_len:
        S3 = min(n - 1 - min_len, E1 + 2 * min_len)
    # ---- 斜率阈值：由前后基线斜率估计 ----
    k_front = np.polyfit(csv[0:E1 + 1, 0], csv[0:E1 + 1, 1], 1)[0]
    k_back = np.polyfit(csv[S3:n, 0], csv[S3:n, 1], 1)[0]
    k_thr = k_mult * max(abs(k_front), abs(k_back), 1e-5)
    # ---- 谷底锚点：中间段全局最低点 ----
    mid = csv[E1:S3 + 1, 1]
    p_min = E1 + int(np.argmin(mid))
    # ---- 平台判据：窗口 [i, i+min_len] 内 σ_res ≤ thr 且 |斜率| ≤ k_thr ----
    def _plat_good(i):
        j = min(n - 1, i + min_len)
        return _sigma_resid(csv, i, j) <= thr and abs(
            np.polyfit(csv[i:j + 1, 0], csv[i:j + 1, 1], 1)[0]) <= k_thr
    # ---- E2: 谷底平台右端 ----
    # 优先直接采用实验记录的加热开始时间 t1：平台右端取 t1 前 margin_pts
    # 点。加热开始后温度有热滞后，但不同设备/记录方式可能有偏差，保守地
    # 停在 t1 之前比事后判断“开始爬升”更稳。只有 t1 缺失或不合理时，才
    # 退回“从谷底向右扩展线性窗口”的数据判据。
    i = p_min
    e_right = None
    while i <= S3 - min_len - 1 and _plat_good(i):
        e_right = i
        i += 1
    E2 = (e_right + min_len) if e_right is not None else S3 - 1
    if t_heat_start is not None:
        t1_idx = int(np.argmin(np.abs(csv[:, 0] - t_heat_start)))
        if t1_idx > E1 + 2 * min_len:
            E2 = t1_idx - margin_pts
    E2 = min(S3 - 1, max(E2, E1 + 2 * min_len))
    # ---- S2: 从 E2 向前取固定长度的低温平台基线 ----
    # 旧方法从谷底向两侧扩展“线性窗口”，会沿着谷底圆弧一路回到降温尾段
    # （G4 的 S2=166.8 s，整段跨过谷底，R² 仅 0.22）。改为固定窗口：
    # 选点数量由 plateau_len_s 保证，不靠最大化 R² 来缩短区间。
    window_s = max(float(plateau_len_s), float(min_len_s))
    S2 = int(np.searchsorted(csv[:, 0], csv[E2, 0] - window_s, side="left"))
    S2 = max(E1 + min_len, S2)
    # 真实谷底（E2 处已明显高于最低点）时，左端不得早于谷底，避免把
    # “先降后升”的圆弧包进拟合区间；若曲线一直单调下降（如 G1），则
    # 谷底就在 E2 附近，不能用它作下界，否则会只剩几个点。
    if csv[E2, 1] - csv[p_min, 1] > max(5 * sigma0, 2e-3):
        S2 = max(S2, p_min)
    # 急降段保护：固定窗口若越过溶解吸热的急降段，用局部斜率把左端推到
    # 急降段之后。k_thr 由前后基线斜率估计，正常平台温漂不会超过它。
    last_steep = None
    for i in range(E1 + 1, E2 - min_len + 1):
        j = min(n - 1, i + min_len)
        slope = np.polyfit(csv[i:j + 1, 0], csv[i:j + 1, 1], 1)[0]
        if abs(slope) > k_thr:
            last_steep = i
    if last_steep is not None:
        S2 = max(S2, last_steep + margin_pts)
    S2 = min(S2, E2 - min_len)
    # ---- 钳制顺序与最小段长 ----
    if S2 < E1 + min_len:
        S2 = E1 + min_len
    if E2 < S2 + min_len:
        E2 = min(S3 - 1, S2 + min_len)
    if S3 < E2 + min_len:
        S3 = min(n - 1 - min_len, E2 + min_len)
    return [0, E1, S2, E2, S3, n - 1]

def find_start_end_point(csv, code: str, time_lower_limit: int or float, time_upper_limit: int or float, std_limit: float, t_heat_start: float or None = None): # 建议时间下限30s，时间上限40s，标准差上限0.01
    if code == "燃烧热":
        # 燃烧热模式：改用线性扩展法（原滑动窗口标准差状态机对噪声阈值过敏感，
        # 前期温漂/主升温弛豫会使选点临界抖动，且会进入主升温段，见 find_start_end_point_linear_ext 注释）
        return find_start_end_point_linear_ext(csv)
    # 溶解热模式：改用线性扩展法（3 区间 6 点），原理见
    # find_start_end_point_dissolution_linear_ext 注释（原状态机选点会进入
    # 溶解急降段/加热段，拟合区间不满足雷诺校正要求的"基线线性良好"）。
    # t_heat_start（加热开始时间，秒）由 GUI 从数据文件参数行传入，用于确定
    # 谷底平台右端 E2；低温平台左端 S2 由 E2 前 plateau_len_s 秒的固定窗口确定。
    return find_start_end_point_dissolution_linear_ext(csv, t_heat_start=t_heat_start)