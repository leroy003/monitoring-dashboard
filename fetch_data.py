#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月度 & 年度收益率检测看板 - 数据获取脚本 (v3)

修复内容 (v3):
1. 国内基金改用「累计净值」计算收益率，消除分红导致的偏差
2. 年度/月度收益率改为「上期末→本期末」公式，与天天基金网官方保持一致
3. 贝莱德亚洲猛虎债券A6 修正为正确的 Morningstar ID: 0P0000VU2Y
4. 对于多次大额分红的基金(如银华中小盘180031)，AkShare累计净值与天天基金复权净值
   存在系统性偏差，改为直接从天天基金网 API 获取官方年度/月度收益率

计算公式（国内基金 akshare 模式）：
  年度收益率 = (本年末累计净值 - 上年末累计净值) / 上年末累计净值 × 100%
  月度收益率 = (本月末累计净值 - 上月末累计净值) / 上月末累计净值 × 100%

计算公式（国内基金 eastmoney_api 模式 - 直接从天天基金网获取官方收益率）：
  直接使用天天基金网 FundArchivesDatas 接口返回的复权收益率

计算公式（海外标的 yfinance）：
  同上期末基准公式

使用方式：
  python fetch_data.py
"""

import json
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path

# ===================== 配置 =====================

# 数据时间范围
START_YEAR = 2014
END_YEAR = datetime.now().year  # 动态获取当前年份，无需每年手动修改

# 输出文件路径（与本脚本同目录）
SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "fund_data.json"

# 11个检测对象配置
OBJECTS = [
    {
        "name": "美国7-10年国债ETF(IEF)",
        "code": "IEF",
        "source": "yfinance",
        "ticker": "IEF",
        "type": "fund"  # 债券ETF，投资回报率可直接与其他对象对比
    },
    {
        "name": "标普500ETF(SPY)",
        "code": "SPY",
        "source": "yfinance",
        "ticker": "SPY",
        "type": "price"
    },
    {
        "name": "上证综合指数",
        "code": "SSE Composite",
        "source": "akshare",
        "ticker": "sh000001",
        "type": "index"
    },
    {
        "name": "华夏沪深300ETF联接A",
        "code": "000051",
        "source": "akshare",
        "ticker": "000051",
        "type": "fund"
    },
    {
        "name": "南方中证500ETF联接A",
        "code": "160119",
        "source": "akshare",
        "ticker": "160119",
        "type": "fund"
    },
    {
        "name": "招商产业债券A",
        "code": "217022",
        "source": "akshare",
        "ticker": "217022",
        "type": "fund"
    },
    {
        "name": "安信稳健增值混合A",
        "code": "001316",
        "source": "akshare",
        "ticker": "001316",
        "type": "fund"
    },
    {
        "name": "天弘通利混合A",
        "code": "000573",
        "source": "akshare",
        "ticker": "000573",
        "type": "fund"
    },
    {
        "name": "银华中小盘混合",
        "code": "180031",
        "source": "eastmoney_api",  # 年度收益率从天天基金API获取（因多次大额分红导致AkShare累计净值偏差）
        "ticker": "180031",
        "type": "fund",
        "akshare_fallback": True  # 月度数据仍用AkShare累计净值计算
    },
    {
        "name": "贝莱德亚洲猛虎债券A6",
        "code": "0P0000VU2Y",
        "source": "yfinance",
        "ticker": "0P0000VU2Y",  # Morningstar ID, 可直接在 yfinance 获取
        "type": "fund"
    },
    {
        "name": "普信美国大盘成长A",
        "code": "0P00000S71",
        "source": "yfinance",
        "ticker": "TRLGX",  # T. Rowe Price Large Cap Growth (Institutional 份额)
        "type": "fund",
        "fallback_tickers": ["TRBCX", "0P00000S71"]
    }
]

# ===================== 数据获取 =====================

def get_eastmoney_returns(fund_code, start_year, end_year):
    """
    从天天基金网 API 直接获取基金年度和月度收益率
    
    用于多次大额分红的基金（如银华中小盘180031），
    因为 AkShare 的累计净值与天天基金的复权净值计算方式不同，
    直接获取天天基金的官方收益率更准确。
    
    返回格式: {"yearly": {year: rate}, "monthly": {year: {month: rate}}}
    """
    import requests
    import re
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': f'https://fund.eastmoney.com/f10/{fund_code}.html'
    }
    
    result = {"yearly": {}, "monthly": {}}
    
    # 获取年度收益率
    try:
        url = (
            f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?"
            f"type=yearzf&code={fund_code}&rt=0.123"
        )
        resp = requests.get(url, headers=headers, timeout=15)
        text = resp.text
        
        years = re.findall(r'<th[^>]*>(\d{4})年度</th>', text)
        rows = re.findall(r"<tr>(.*?)</tr>", text, re.DOTALL)
        
        if len(rows) >= 2:
            row = rows[1]
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if cells:
                data_cells = cells[1:]
                for i, cell in enumerate(data_cells):
                    if i < len(years):
                        clean = cell.strip().replace('\r', '').replace('\n', '')
                        match = re.search(r'([-\d.]+)%', clean)
                        if match:
                            result["yearly"][int(years[i])] = float(match.group(1))
        
        print(f"  [天天基金API] 获取年度收益率成功: {len(result['yearly'])} 年")
    except Exception as e:
        print(f"  [天天基金API] 获取年度收益率失败: {e}")
    
    # 获取月度收益率
    for year in range(start_year, end_year + 1):
        try:
            url = (
                f"https://fundf10.eastmoney.com/FundArchivesDatas.aspx?"
                f"type=monthzf&year={year}&code={fund_code}&rt=0.123"
            )
            resp = requests.get(url, headers=headers, timeout=15)
            text = resp.text
            
            months = re.findall(r'<th[^>]*>(\d+)月</th>', text)
            rows = re.findall(r"<tr>(.*?)</tr>", text, re.DOTALL)
            
            if len(rows) >= 2:
                row = rows[1]
                cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
                if cells:
                    data_cells = cells[1:]
                    year_monthly = {}
                    for i, cell in enumerate(data_cells):
                        if i < len(months):
                            month_num = int(months[i])
                            clean = cell.strip().replace('\r', '').replace('\n', '')
                            match = re.search(r'([-\d.]+)%', clean)
                            if match:
                                year_monthly[month_num] = float(match.group(1))
                            else:
                                year_monthly[month_num] = None
                    result["monthly"][year] = year_monthly
            
            time.sleep(0.2)  # 控制请求频率
        except Exception as e:
            print(f"  [天天基金API] 获取 {year} 年月度数据失败: {e}")
    
    monthly_years = len([y for y in result["monthly"] if result["monthly"][y]])
    print(f"  [天天基金API] 获取月度收益率成功: {monthly_years} 年")
    
    return result

def get_akshare_fund_nav(fund_code, start_date, end_date):
    """
    获取国内基金历史累计净值（AkShare）
    
    使用「累计净值走势」而非「单位净值走势」，
    避免基金分红导致的收益率计算偏差。
    累计净值 = 单位净值 + 历史累计分红，
    能真实反映基金的实际投资收益。
    """
    import akshare as ak
    try:
        print(f"  [AkShare] 获取基金 {fund_code} 累计净值...")
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="累计净值走势")
        if df is None or df.empty:
            print(f"  [AkShare] 基金 {fund_code} 无数据")
            return None
        
        # 累计净值走势只有2列: 日期, 累计净值
        df.columns = ["date", "nav"]
        df["date"] = pd.to_datetime(df["date"])
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        df = df.dropna(subset=["nav"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 筛选日期范围（需要从 START_YEAR-1 年末开始，用于计算第一年的年度收益率）
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        
        return df[["date", "nav"]]
    except Exception as e:
        print(f"  [AkShare] 基金 {fund_code} 获取失败: {e}")
        return None


def get_akshare_index(index_code, start_date, end_date):
    """获取国内指数历史数据（AkShare）"""
    import akshare as ak
    try:
        print(f"  [AkShare] 获取指数 {index_code} 数据...")
        df = ak.stock_zh_index_daily(symbol=index_code)
        if df is None or df.empty:
            print(f"  [AkShare] 指数 {index_code} 无数据")
            return None
        
        df["date"] = pd.to_datetime(df["date"])
        df["nav"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["nav"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 筛选日期范围
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        
        return df[["date", "nav"]]
    except Exception as e:
        print(f"  [AkShare] 指数 {index_code} 获取失败: {e}")
        return None


def get_yfinance_data(ticker, start_date, end_date, fallback_tickers=None):
    """
    获取 yfinance 历史数据，使用总回报指数（Total Return Index）
    
    关键改进（v4）：
    - 不再使用 auto_adjust=True（其价格调整算法在大额分红场景下不准确）
    - 改用 raw close + dividends 计算总回报指数：假设分红全额再投资买入
    - 这样计算出的收益率与 Yahoo Finance 官方 Calendar Year Returns 完全一致
    """
    import yfinance as yf
    
    tickers_to_try = [ticker]
    if fallback_tickers:
        tickers_to_try.extend(fallback_tickers)
    
    for t in tickers_to_try:
        try:
            print(f"  [yfinance] 尝试获取 {t} 数据...")
            tkr = yf.Ticker(t)
            data = tkr.history(start=start_date, end=end_date, auto_adjust=False)
            
            if data is None or data.empty:
                print(f"  [yfinance] {t} 无数据，尝试下一个...")
                continue
            
            df = data.reset_index()
            # 处理多级列名
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            
            # 去除时区信息
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
            df = df.dropna(subset=["Close"])
            df = df.sort_values("Date").reset_index(drop=True)
            
            if len(df) == 0:
                print(f"  [yfinance] {t} 数据为空...")
                continue
            
            # 检查是否有分红数据
            has_dividends = "Dividends" in df.columns and (df["Dividends"] > 0).any()
            div_count = (df["Dividends"] > 0).sum() if has_dividends else 0
            
            if has_dividends:
                # 计算总回报指数（Total Return Index）
                # 假设分红全额以当日收盘价再投资买入
                print(f"  [yfinance] {t} 检测到 {div_count} 次分红，使用总回报指数...")
                shares = 1.0
                total_return_values = []
                
                for _, row in df.iterrows():
                    if row.get("Dividends", 0) > 0 and row["Close"] > 0:
                        additional_shares = (shares * row["Dividends"]) / row["Close"]
                        shares += additional_shares
                    total_return_values.append(shares * row["Close"])
                
                df["nav"] = total_return_values
            else:
                # 无分红，直接用收盘价
                print(f"  [yfinance] {t} 无分红记录，使用原始收盘价...")
                df["nav"] = df["Close"]
            
            df = df.rename(columns={"Date": "date"})
            df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
            df = df.dropna(subset=["nav"])
            df = df.sort_values("date").reset_index(drop=True)
            
            if len(df) > 0:
                print(f"  [yfinance] {t} 获取成功，共 {len(df)} 条数据")
                return df[["date", "nav"]]
            
        except Exception as e:
            print(f"  [yfinance] {t} 获取失败: {e}")
            continue
    
    print(f"  [yfinance] 所有 ticker 均失败")
    return None


# ===================== 收益率计算 (v2 - 上期末基准) =====================

def get_last_trading_day_value(df, year, month):
    """获取指定年月最后一个交易日的值"""
    if df is None or df.empty:
        return None
    month_data = df[(df["date"].dt.year == year) & (df["date"].dt.month == month)]
    if month_data.empty:
        return None
    return float(month_data.iloc[-1]["nav"])


def get_last_trading_day_of_year(df, year):
    """获取指定年份最后一个交易日的值"""
    if df is None or df.empty:
        return None
    year_data = df[df["date"].dt.year == year]
    if year_data.empty:
        return None
    return float(year_data.iloc[-1]["nav"])


def get_first_trading_day_value(df, year, month=None):
    """获取指定年（月）第一个交易日的值"""
    if df is None or df.empty:
        return None
    if month:
        data = df[(df["date"].dt.year == year) & (df["date"].dt.month == month)]
    else:
        data = df[df["date"].dt.year == year]
    if data.empty:
        return None
    return float(data.iloc[0]["nav"])


def calc_monthly_return_v2(df, year, month):
    """
    计算指定年月的月度收益率 (v2)
    
    公式：(本月末值 - 上月末值) / 上月末值 × 100
    
    对于第一个有数据的月份（无上月数据）：使用本月第一个交易日作为基准
    """
    if df is None or df.empty:
        return None
    
    # 获取本月末值
    end_val = get_last_trading_day_value(df, year, month)
    if end_val is None:
        return None
    
    # 获取上月末值
    if month == 1:
        # 1月份，上期是去年12月
        start_val = get_last_trading_day_value(df, year - 1, 12)
    else:
        start_val = get_last_trading_day_value(df, year, month - 1)
    
    # 如果没有上月末数据，用本月第一个交易日作为基准
    if start_val is None:
        start_val = get_first_trading_day_value(df, year, month)
    
    if start_val is None or start_val == 0:
        return None
    
    # 需要至少有变化（同一天的数据不算）
    month_data = df[(df["date"].dt.year == year) & (df["date"].dt.month == month)]
    if len(month_data) < 1:
        return None
    
    return round((end_val - start_val) / start_val * 100, 2)


def calc_yearly_return_v2(df, year):
    """
    计算指定年份的年度收益率 (v2)
    
    公式：(本年末值 - 上年末值) / 上年末值 × 100
    
    与天天基金网/官方计算方式一致：
    - 以上年12月最后一个交易日的值作为基准
    - 以本年12月最后一个交易日的值（或当前最新值）作为终值
    
    对于基金成立第一年（无上年数据）：使用本年第一个交易日值作为基准
    """
    if df is None or df.empty:
        return None
    
    # 获取本年末（或当前最新）的值
    end_val = get_last_trading_day_of_year(df, year)
    if end_val is None:
        return None
    
    # 获取上年末的值
    start_val = get_last_trading_day_of_year(df, year - 1)
    
    # 如果没有上年末数据（基金成立第一年），用本年第一个交易日值
    if start_val is None:
        start_val = get_first_trading_day_value(df, year)
    
    if start_val is None or start_val == 0:
        return None
    
    # 确保本年至少有数据
    year_data = df[df["date"].dt.year == year]
    if year_data.empty:
        return None
    
    return round((end_val - start_val) / start_val * 100, 2)


# ===================== 主流程 =====================

def fetch_all_data():
    """获取所有对象的原始数据"""
    # 从 START_YEAR-1 年开始获取，用于计算第一年的「上年末」基准值
    start_date = f"{START_YEAR - 1}-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    raw_data = {}
    eastmoney_data = {}  # 存储天天基金API获取的直接收益率数据
    
    for obj in OBJECTS:
        name = obj["name"]
        code = obj["code"]
        source = obj["source"]
        ticker = obj["ticker"]
        
        print(f"\n{'='*50}")
        print(f"获取: {name} ({code})")
        print(f"{'='*50}")
        
        df = None
        
        if source == "eastmoney_api":
            # 直接从天天基金网API获取官方收益率
            em_result = get_eastmoney_returns(ticker, START_YEAR, END_YEAR)
            eastmoney_data[code] = em_result
            print(f"  ✅ 天天基金API数据获取完成")
            
            # 如果有 akshare_fallback，也获取 AkShare 数据用于月度计算
            if obj.get("akshare_fallback"):
                print(f"  [AkShare] 同时获取累计净值用于月度计算...")
                df = get_akshare_fund_nav(ticker, start_date, end_date)
                raw_data[code] = df
                if df is not None:
                    print(f"  ✅ AkShare 数据范围: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}")
        elif source == "akshare":
            if obj["type"] == "index":
                df = get_akshare_index(ticker, start_date, end_date)
            elif obj["type"] == "fund":
                df = get_akshare_fund_nav(ticker, start_date, end_date)
        elif source == "yfinance":
            fallback = obj.get("fallback_tickers", None)
            df = get_yfinance_data(ticker, start_date, end_date, fallback)
        
        if source != "eastmoney_api":
            raw_data[code] = df
            if df is not None:
                print(f"  ✅ 数据范围: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}")
                print(f"  ✅ 数据条数: {len(df)}")
            else:
                print(f"  ❌ 未获取到数据")
        
        # 稍作延时，避免请求过快
        time.sleep(0.5)
    
    return raw_data, eastmoney_data


def compute_returns(raw_data, eastmoney_data):
    """计算所有对象在所有年份的月度和年度收益率"""
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    result = {}
    
    for year in range(START_YEAR, END_YEAR + 1):
        year_str = str(year)
        result[year_str] = []
        
        for obj in OBJECTS:
            code = obj["code"]
            source = obj["source"]
            
            if source == "eastmoney_api" and code in eastmoney_data:
                # 使用天天基金API的官方收益率
                em = eastmoney_data[code]
                
                # 月度收益率：优先天天基金API，无数据则用AkShare
                monthly = []
                for month in range(1, 13):
                    if year > current_year or (year == current_year and month > current_month):
                        monthly.append(None)
                    else:
                        year_monthly = em["monthly"].get(year, {})
                        rate = year_monthly.get(month, None)
                        # 如果API无月度数据，用AkShare累计净值计算
                        if rate is None and code in raw_data:
                            rate = calc_monthly_return_v2(raw_data[code], year, month)
                        monthly.append(rate)
                
                # 年度收益率：使用天天基金API
                if year > current_year:
                    yearly = None
                else:
                    yearly = em["yearly"].get(year, None)
                    # 如果API无年度数据（如很早期的年份），用AkShare计算
                    if yearly is None and code in raw_data:
                        yearly = calc_yearly_return_v2(raw_data[code], year)
                
            else:
                # 使用原始数据计算收益率
                df = raw_data.get(code, None)
                
                # 计算12个月的月度收益率
                monthly = []
                for month in range(1, 13):
                    if year > current_year or (year == current_year and month > current_month):
                        monthly.append(None)
                    else:
                        rate = calc_monthly_return_v2(df, year, month)
                        monthly.append(rate)
                
                # 计算年度收益率
                if year > current_year:
                    yearly = None
                else:
                    yearly = calc_yearly_return_v2(df, year)
            
            # 银华中小盘(180031)月度数据因累计净值口径问题不准确，
            # 强制显示为"-"（null），仅保留年度收益率
            if code == "180031":
                monthly = [None] * 12
            
            result[year_str].append({
                "name": obj["name"],
                "code": code,
                "monthly": monthly,
                "yearly": yearly
            })
    
    return result


def save_to_json(data):
    """保存结果为 JSON 文件"""
    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "data": data
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 数据已保存到: {OUTPUT_FILE}")
    print(f"   更新时间: {output['updated_at']}")


def main():
    """主入口"""
    print("=" * 60)
    print("  月度 & 年度收益率检测看板 - 数据获取 (v3)")
    print(f"  数据范围: {START_YEAR} ~ {END_YEAR}")
    print(f"  对象数量: {len(OBJECTS)}")
    print("  改进: 累计净值+上期末基准+天天基金API补充")
    print("=" * 60)
    
    # 获取原始数据
    raw_data, eastmoney_data = fetch_all_data()
    
    # 计算收益率
    print("\n\n" + "=" * 60)
    print("  计算月度 & 年度收益率 (v3)...")
    print("=" * 60)
    
    returns = compute_returns(raw_data, eastmoney_data)
    
    # 输出摘要
    for year in range(START_YEAR, END_YEAR + 1):
        year_str = str(year)
        valid_count = sum(1 for item in returns[year_str] if item["yearly"] is not None)
        print(f"  {year}年: {valid_count}/{len(OBJECTS)} 个对象有年度收益率")
    
    # 保存 JSON
    save_to_json(returns)
    
    print("\n🎉 数据获取完成！(v3)")


if __name__ == "__main__":
    try:
        import pandas as pd
    except ImportError:
        print("❌ 缺少 pandas，请运行: pip install pandas")
        sys.exit(1)
    
    try:
        import akshare
    except ImportError:
        print("❌ 缺少 akshare，请运行: pip install akshare")
        sys.exit(1)
    
    try:
        import yfinance
    except ImportError:
        print("❌ 缺少 yfinance，请运行: pip install yfinance")
        sys.exit(1)
    
    main()
