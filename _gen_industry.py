# -*- coding: utf-8 -*-
"""生成行业维度表 data/industry.csv —— 数据源为申万一级行业分类的官方成分股接口。

依赖 akshare 且需联网:  pip install akshare
产物 industry.csv 已随仓库提交, 正常跑主脚本 eda_hs300.py 不需要执行本文件。
本文件仅用于说明行业维度表的来源, 并在分类更新时重新生成。
"""
import akshare as ak
import pandas as pd

# 1. 拉取申万 31 个一级行业的全部成分股, 建立 股票代码 -> 行业 映射(共 5000+ 只)
code2ind = {}
for _, row in ak.sw_index_first_info().iterrows():
    cons = ak.index_component_sw(symbol=row['行业代码'].split('.')[0])
    for c in cons['证券代码'].astype(str).str.zfill(6):
        code2ind[c] = row['行业名称']
print(f'申万官方数据覆盖 {len(code2ind)} 只股票')

# 2. 只保留沪深300成分股; 股票名称沿用原始名单表, 保证与行情表口径一致
lst = pd.read_csv('data/hs300_stock_list.csv', encoding='utf-8-sig', dtype={'code': str})
lst['stock_code'] = lst['code'].str.split('.').str[-1]   # sh.600000 -> 600000
lst['industry'] = lst['stock_code'].map(code2ind)

missing = lst.loc[lst['industry'].isna(), 'stock_code'].tolist()
if missing:
    raise SystemExit(f'以下成分股未在申万分类中找到, 需人工确认: {missing}')

# 3. 输出三列维度表
out = lst[['stock_code', 'code_name', 'industry']].rename(columns={'code_name': 'stock_name'})
out.to_csv('data/industry.csv', index=False, encoding='utf-8-sig')
print(f'已生成 data/industry.csv: {len(out)} 行, 覆盖 {out["industry"].nunique()} 个申万一级行业')
