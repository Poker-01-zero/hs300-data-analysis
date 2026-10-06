# -*- coding: utf-8 -*-
"""沪深300成分股 历史数据清洗与探索性分析(EDA)
数据流: 事实表(stock_data) + 维度表(industry) -> 清洗 -> 关联 -> 聚合 -> 可视化
"""
import pandas as pd
import matplotlib.pyplot as plt

# 中文字体: 不设置则标题/坐标轴显示为方块; 负号需单独关闭, 否则负刻度也变方块
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ===== 第一步: 读取数据 =====
# dtype 把股票代码读成字符串: 否则 "000001" 会被解析成数字 1, 与维度表主键对不上
# encoding='utf-8-sig': 两文件都带 BOM 头, 用普通 utf-8 会把首列名读成 "﻿股票代码"
price = pd.read_csv('data/stock_data.csv', encoding='utf-8-sig', dtype={'股票代码': str})
ind = pd.read_csv('data/industry.csv', encoding='utf-8-sig', dtype={'stock_code': str})
print(f'行情表 {price.shape} | 维度表 {ind.shape}')
print(price.head(3)); price.info()

# ===== 第二步: 数据清洗 =====
# 2.1 日期转换: 原值为字符串, 不转 datetime 就无法按年/月分组
price['日期'] = pd.to_datetime(price['日期'])
# 2.2 排序: ffill 是"按顺序向下带值", 顺序错就会取到错误日期的值, 必须先按 股票+日期 排好
price = price.sort_values(['股票代码', '日期'])
# 2.3 缺失值: 缺失集中在 23 只个股的停牌日, 用 ffill 前向填充, 且必须 groupby 分股票填充
#     为何不用均值填充: ①均值用了全期数据, 把未来信息泄露给了过去;
#     ②成交/价格是连续序列, 停牌的真实业务含义就是"沿用上一交易日", 均值会破坏连续性;
#     ③均值会凭空造出当天并不存在的成交量, 污染后续的波动率计算
vol_cols = ['成交量', '成交额', '换手率']
price[vol_cols] = price.groupby('股票代码')[vol_cols].ffill()
price['涨跌幅'] = price['涨跌幅'].fillna(0)  # 停牌当日无成交 -> 收益本就应为 0, 比 ffill 更准确
# 2.4 去重: 按整行判断。重复行会让同一笔成交被统计两次, 直接虚增成交量与收益
n0 = len(price); price = price.drop_duplicates()
print(f'去重 {n0 - len(price)} 行, 残留缺失 {int(price.isna().sum().sum())} 个')

# ===== 第三步: 关联维度表 =====
# 行情表只有股票代码, 没有"行业"这一分析维度, 维度表正是用来补齐它的 —— 典型的事实表-维度表关联
# how='left' 以行情表为准, 保证不因维度表缺记录而丢行情; 但 left join 匹配不上会静默产生 NaN, 故必须校验
df = pd.merge(price, ind, left_on='股票代码', right_on='stock_code', how='left')
print(f'维度表关联率 {df["industry"].notna().mean():.2%}, 未匹配 {int(df["industry"].isna().sum())} 行')

# ===== 第四步: 多维度分析 =====
df['日收益率'] = df['涨跌幅'] / 100        # 涨跌幅单位是 %, 除以 100 得到小数收益率
df['月份'] = df['日期'].dt.to_period('M')  # 预造月份列, 供分组与透视使用
# 4.1 行业 × 月份: 月均收益率衡量赚钱能力, 月波动率(收益率标准差)衡量风险水平
monthly = df.groupby(['industry', '月份'])['日收益率'].agg(月均收益率='mean', 月波动率='std').reset_index()
# 4.2 行业总览: 把各月指标在行业维度再求平均, 得到行业整体画像, 并按收益降序排列
sector = monthly.groupby('industry')[['月均收益率', '月波动率']].mean().sort_values('月均收益率', ascending=False)
sector['收益波动比'] = sector['月均收益率'] / sector['月波动率']  # 每承担 1 单位风险换来的收益
print('\n各行业整体表现(按收益降序):'); print(sector.round(5).to_string())
# 4.3 数据透视表: 行=行业, 列=年份, 值=收益率标准差, 用来观察波动率随时间的变化
pivot = pd.pivot_table(df, values='日收益率', index='industry', columns=df['日期'].dt.year, aggfunc='std')
print('\n行业 × 年份 波动率透视表:'); print(pivot.round(5).to_string())

# ===== 第五步: 可视化 =====
# 图1: 各行业月均收益率对比。用单色即可 —— 柱高已经表达了大小, 彩虹配色反而干扰阅读
plt.figure(figsize=(11, 5))
plt.bar(sector.index, sector['月均收益率'] * 100, color='#4C78A8')
plt.axhline(0, color='gray', linewidth=1)  # 0 轴参考线, 用于区分正负收益
plt.title('沪深300各行业月均收益率对比(申万一级行业)')
plt.xlabel('行业'); plt.ylabel('月均收益率(%)')
plt.xticks(rotation=90); plt.grid(axis='y', alpha=0.3)  # 网格弱化, 不与数据抢视觉
plt.tight_layout(); plt.savefig('chart1_行业收益率对比.png', dpi=150)

# 图2: 取收益率第一的行业, 用该行业内累计成交额最大的股票作为代表股, 画其收盘价走势
top_ind = sector.index[0]
sub = df[df['industry'] == top_ind]
top_code = sub.groupby('股票代码')['成交额'].sum().idxmax()
top_name = sub.loc[sub['股票代码'] == top_code, 'stock_name'].iloc[0]
ts = sub[sub['股票代码'] == top_code].set_index('日期')['收盘']
plt.figure(figsize=(11, 5))
plt.plot(ts.index, ts.values, color='#E45756', linewidth=1.8)
plt.title(f'{top_ind}行业代表股 {top_name}({top_code}) 收盘价走势')
plt.xlabel('日期'); plt.ylabel('收盘价(元)'); plt.grid(alpha=0.3)
plt.tight_layout(); plt.savefig('chart2_代表股走势.png', dpi=150)
plt.show()
print(f'\n收益第一行业: {top_ind} | 代表股: {top_name}({top_code})')
