import pandas as pd
from jinja2 import Template
import json
import sys
import os
import datetime

# ==========================================
# 1. 基础配置与排序权重定义
# ==========================================
# 两个独立数据源
SHEET_URL_AI = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
SHEET_URL_BROWSER_IME = "https://docs.google.com/spreadsheets/d/1ldaqKpPhuMkhSQblBAtjyARIStpq5CXunjWLzDV5FDw/export?format=csv&gid=0"
MY_DOMAIN = "www.aipulse.run"

# AI 板块配置
CORE_COMPANIES = ['OpenAI', 'Google', 'Anthropic', 'Meta', '字节跳动', '阿里巴巴', '腾讯', '百度']
SECONDARY_COMPANIES = ['Kimi', 'MiniMax', '智谱', 'xAI', '可灵', 'DeepSeek', 'Apple', '美团']
SECONDARY_TITLE = "其余重点关注公司"

TOPIC_ORDER = ['技术迭代', '产品动态', '数据洞察', '行业洞察', '商业动态', '运营活动', '春节活动']

OTHER_PRIORITY = [
    'Perplexity', 'Character.ai', 'Midjourney', 'Pika', 'Runway', 
    'Suno', 'Luma', 'Grok', 'Mistral', 'Cohere', 'OpenClaw',
    'Microsoft', 'Apple', '英伟达', 'AMD', 'Intel', 'TSMC', 'Samsung', 'Amazon',
    'Tesla', 'Notion', 'Canva', 'Adobe', 'GitHub', 'Arc', 'Cursor', 'Groq',
    '特斯拉', '波士顿动力', '宇树', '智元', '银河', '星海图', 'Fiture', 'Figure', 
    'Sanctuary AI', '1X Technologies', 'Agility Robotics', '小红书', '森森'
]

# 浏览器/输入法板块配置 - 重点关注公司
# 格式：(数据匹配名, 展示用公司名) — 同一公司名会自动合并
# 数据匹配名 = Google Sheet 中"公司"列的实际值
BROWSER_COMPANIES = [
    ('Google', 'Google'),
    ('Perplexity', 'Perplexity'),
    ('Dia', 'The Browser Company'),
    ('OpenAI', 'OpenAI'),
    ('Tabbit', '美团'),
    ('夸克', '阿里巴巴'),
    ('UC浏览器', '阿里巴巴'),
    ('豆包浏览器', '字节跳动'),
    ('360浏览器', '360浏览器'),
    ('QQ浏览器', '腾讯'),
]
IME_COMPANIES = [
    ('豆包输入法', '字节跳动'),
    ('搜狗输入法', '腾讯'),
    ('腾讯', '腾讯'),
    ('千问输入法', '阿里巴巴'),
    ('讯飞输入法', '科大讯飞'),
    ('百度输入法', '百度'),
    ('Typeless', 'Typeless'),
    ('Wisper Flow', 'Wisper Flow'),
    ('微信输入法', '腾讯'),
]

# 提取产品名列表用于数据匹配
BROWSER_PRODUCT_NAMES = [item[0] for item in BROWSER_COMPANIES]
IME_PRODUCT_NAMES = [item[0] for item in IME_COMPANIES]

# 展示用公司名有序列表（去重保序）
def _unique_display_names(company_list):
    seen = []
    for _, display in company_list:
        if display not in seen:
            seen.append(display)
    return seen

BROWSER_DISPLAY_ORDER = _unique_display_names(BROWSER_COMPANIES)
IME_DISPLAY_ORDER = _unique_display_names(IME_COMPANIES)

# 构建"数据中公司名 → 展示名"的完整映射（包含 product_name 和 display_name 本身）
def _build_match_map(company_list):
    """返回 {匹配名: 展示名} 字典，同时将展示名本身也作为匹配名"""
    m = {}
    for product_name, display_name in company_list:
        m[product_name] = display_name
        if display_name not in m:
            m[display_name] = display_name
    return m

BROWSER_MATCH_MAP = _build_match_map(BROWSER_COMPANIES)
IME_MATCH_MAP = _build_match_map(IME_COMPANIES)

# 所有可匹配到重点公司的名称集合
BROWSER_ALL_MATCH_NAMES = set(BROWSER_MATCH_MAP.keys())
IME_ALL_MATCH_NAMES = set(IME_MATCH_MAP.keys())

# --- 辅助函数 ---
def parse_date_for_sort(date_str):
    d_part = date_str.split('至')[1].strip() if '至' in date_str else date_str.strip()
    try:
        return datetime.datetime.strptime(d_part, '%Y/%m/%d')
    except:
        return datetime.datetime.min

def get_week_range(dt):
    """
    计算给定日期所属的周范围（周六~周五）
    返回 (week_start, week_end) 均为 datetime.date
    """
    # weekday(): Mon=0, Tue=1, ..., Sat=5, Sun=6
    # 我们要以周六为周起始
    d = dt.date() if isinstance(dt, datetime.datetime) else dt
    weekday = d.weekday()  # 0=Mon,...,5=Sat,6=Sun
    # 距离上一个周六的天数
    if weekday == 5:  # Saturday
        days_since_sat = 0
    elif weekday == 6:  # Sunday
        days_since_sat = 1
    else:  # Mon-Fri (0-4)
        days_since_sat = weekday + 2
    week_start = d - datetime.timedelta(days=days_since_sat)
    week_end = week_start + datetime.timedelta(days=6)  # Friday
    return week_start, week_end

def get_weeks_in_month(all_dates_dt, target_year, target_month):
    """
    给定所有日期和目标年月，返回该月应包含的周列表。
    跨月的周以结束日（周五）所在月份为准。
    返回 [(week_start, week_end), ...] 按时间降序排列
    """
    weeks_set = set()
    for dt in all_dates_dt:
        ws, we = get_week_range(dt)
        # 该周归属于 week_end 所在的月份
        if we.year == target_year and we.month == target_month:
            weeks_set.add((ws, we))
    # 按 week_end 降序排列（最新的周在前）
    return sorted(list(weeks_set), key=lambda x: x[1], reverse=True)

def get_company_rank(c_val):
    if c_val in CORE_COMPANIES: return CORE_COMPANIES.index(c_val)
    if c_val in SECONDARY_COMPANIES: return len(CORE_COMPANIES) + SECONDARY_COMPANIES.index(c_val)
    return 999

def get_topic_rank(t_val):
    main_topic = t_val[0] if isinstance(t_val, list) and len(t_val) > 0 else t_val
    return TOPIC_ORDER.index(main_topic) if main_topic in TOPIC_ORDER else 99

def main():
    # 2. 数据读取与预处理 — 两个独立数据源
    # --- 读取 AI 数据 ---
    try:
        df_ai = pd.read_csv(SHEET_URL_AI)
        print(f"✅ AI 数据源读取成功: {len(df_ai)} 条")
    except Exception as e:
        print(f"❌ AI 数据源读取错误: {e}")
        df_ai = pd.DataFrame()

    # --- 读取浏览器/输入法数据 ---
    try:
        df_bi = pd.read_csv(SHEET_URL_BROWSER_IME)
        print(f"✅ 浏览器/输入法数据源读取成功: {len(df_bi)} 条")
    except Exception as e:
        print(f"❌ 浏览器/输入法数据源读取错误: {e}")
        df_bi = pd.DataFrame()

    # 预处理函数
    def preprocess(df, default_category='AI'):
        if df.empty:
            return df
        df.columns = [c.strip() for c in df.columns]
        # 列名兼容：将 '公司/模型' 等变体统一为 '公司'
        col_rename = {}
        if '公司/模型' in df.columns and '公司' not in df.columns:
            col_rename['公司/模型'] = '公司'
        if col_rename:
            df = df.rename(columns=col_rename)
        name_map = {'字节': '字节跳动', '阿里': '阿里巴巴', 'Baidu': '百度', 'minimax': 'MiniMax', '智谱AI': '智谱', 'OpenAI ': 'OpenAI'}
        df['公司'] = df['公司'].replace(name_map)
        if '是否头条' in df.columns:
            df['是否头条'] = pd.to_numeric(df['是否头条'], errors='coerce').fillna(0).astype(int)
        else:
            df['是否头条'] = 0
        # 排序列处理
        if '排序' in df.columns:
            df['排序'] = pd.to_numeric(df['排序'], errors='coerce').fillna(999).astype(int)
        else:
            df['排序'] = 999
        df = df.fillna("")
        if '分类' not in df.columns:
            df['分类'] = default_category
        df['话题_list'] = df['话题'].apply(lambda x: [i.strip() for i in str(x).replace(' ', '').split('、')] if x else [])
        df['公司_list'] = df['公司'].apply(lambda x: [i.strip() for i in str(x).split('、')] if x else [])
        def get_ymd(date_str):
            dt = parse_date_for_sort(date_str)
            return dt.year, dt.month
        df['year'], df['month'] = zip(*df['日期'].apply(get_ymd))
        return df

    df_ai = preprocess(df_ai, default_category='AI')
    df_bi = preprocess(df_bi, default_category='浏览器')

    # 从 AI 数据中去除与浏览器/输入法表重复的条目（以标题为唯一标识）
    if not df_ai.empty and not df_bi.empty:
        bi_titles = set(df_bi['标题'].tolist())
        before_count = len(df_ai)
        df_ai = df_ai[~df_ai['标题'].isin(bi_titles)].copy()
        removed = before_count - len(df_ai)
        if removed > 0:
            print(f"⚠️ 从 AI 数据中去除 {removed} 条与浏览器/输入法重复的新闻")

    # 合并全量数据（用于历史检索）
    df = pd.concat([df_ai, df_bi], ignore_index=True) if not df_ai.empty or not df_bi.empty else pd.DataFrame()

    # 拆分浏览器和输入法
    df_browser = df_bi[df_bi['分类'] == '浏览器'].copy() if not df_bi.empty else pd.DataFrame()
    df_ime = df_bi[df_bi['分类'] == '输入法'].copy() if not df_bi.empty else pd.DataFrame()

    # --- AI 部分处理 ---
    all_individual_topics_ai = set()
    for t_list in df_ai['话题_list']: all_individual_topics_ai.update(t_list)
    all_unique_topics_ai = sorted(list(all_individual_topics_ai))

    all_individual_companies_ai = set()
    for c_list in df_ai['公司_list']: all_individual_companies_ai.update(c_list)
    all_unique_companies_ai = sorted(list(all_individual_companies_ai), key=lambda x: x.encode('gbk') if isinstance(x, str) else x)

    df_ai_exploded = df_ai.explode('公司_list')
    ai_dates = df_ai['日期'].unique().tolist()
    ai_dates.sort(key=parse_date_for_sort, reverse=True)

    # AI 核心分发逻辑
    news_data_map = {}
    headlines_map = {}

    for date in ai_dates:
        day_df_orig = df_ai[df_ai['日期'] == date].copy()
        headline_df = day_df_orig[day_df_orig['是否头条'] > 0].copy()
        if not headline_df.empty:
            headline_df['c_rank'] = headline_df['公司'].apply(get_company_rank)
            headline_df['t_rank'] = headline_df['话题_list'].apply(get_topic_rank)
            headlines_map[date] = headline_df.sort_values(by=['是否头条', 'c_rank', 't_rank']).to_dict('records')
        else:
            headlines_map[date] = []

        day_df_exp = df_ai_exploded[df_ai_exploded['日期'] == date].copy()
        news_data_map[date] = {}

        def sort_section_data(data_df, is_other=False):
            def calc_company_internal_score(c_name):
                if is_other: return OTHER_PRIORITY.index(c_name) if c_name in OTHER_PRIORITY else 999
                return get_company_rank(c_name)
            def calc_item_rank_score(row):
                val = row['是否头条']
                t_idx = get_topic_rank(row['话题_list'])
                return val if val > 0 else (1000 + t_idx)
            data_df['co_group_rank'] = data_df['公司_list'].apply(calc_company_internal_score)
            data_df['item_internal_rank'] = data_df.apply(calc_item_rank_score, axis=1)
            return data_df.sort_values(by=['co_group_rank', 'item_internal_rank']).to_dict('records')

        for company in CORE_COMPANIES:
            comp_df = day_df_exp[day_df_exp['公司_list'] == company].copy()
            if not comp_df.empty: news_data_map[date][company] = sort_section_data(comp_df)
        sec_df = day_df_exp[day_df_exp['公司_list'].isin(SECONDARY_COMPANIES)].copy()
        if not sec_df.empty: news_data_map[date][SECONDARY_TITLE] = sort_section_data(sec_df)
        other_df = day_df_exp[~day_df_exp['公司_list'].isin(CORE_COMPANIES + SECONDARY_COMPANIES)].copy()
        if not other_df.empty: news_data_map[date]['行业新闻'] = sort_section_data(other_df, is_other=True)

    # --- 浏览器部分处理 (按月+按周+按公司分组) ---
    # 结构: browser_months = ['2026/5', ...]
    #        browser_weeks_by_month = {'2026/5': [{'start':'2026/5/16','end':'2026/5/22','key':'2026-5-16_2026-5-22'}, ...]}
    #        browser_week_headlines = {'2026-5-16_2026-5-22': [items]}
    #        browser_data_by_month = {'2026/5': {company: [all month items]}}
    browser_months = []
    browser_weeks_by_month = {}
    browser_week_headlines = {}
    browser_data_by_month = {}

    if not df_browser.empty:
        df_browser_exploded = df_browser.explode('公司_list')
        # 解析所有日期
        df_browser['date_dt'] = df_browser['日期'].apply(parse_date_for_sort)
        df_browser_exploded['date_dt'] = df_browser_exploded['日期'].apply(parse_date_for_sort)
        all_browser_dates_dt = [d for d in df_browser['date_dt'] if d != datetime.datetime.min]
        
        # 收集所有涉及的月份（以 week_end 所在月为准）
        month_set = set()
        for dt in all_browser_dates_dt:
            ws, we = get_week_range(dt)
            month_set.add((we.year, we.month))
        
        for (y, m) in sorted(month_set, reverse=True):
            month_key = f"{y}/{m}"
            browser_months.append(month_key)
            
            # 计算该月包含的所有周
            weeks = get_weeks_in_month(all_browser_dates_dt, y, m)
            browser_weeks_by_month[month_key] = []
            for ws, we in weeks:
                week_key = f"{ws.year}-{ws.month}-{ws.day}_{we.year}-{we.month}-{we.day}"
                week_label = f"{ws.year}/{ws.month}/{ws.day}-{we.year}/{we.month}/{we.day}"
                browser_weeks_by_month[month_key].append({
                    'key': week_key,
                    'label': week_label,
                    'start': ws,
                    'end': we
                })
                # 该周的动态（有头条则只展示头条，无头条则展示该周所有新闻）
                # 排序：优先按"排序"列升序，再按日期降序
                week_df = df_browser[(df_browser['date_dt'] >= datetime.datetime.combine(ws, datetime.time.min)) & 
                                     (df_browser['date_dt'] <= datetime.datetime.combine(we, datetime.time.max))].copy()
                headline_df = week_df[week_df['是否头条'] > 0].copy()
                if not headline_df.empty:
                    headline_df = headline_df.sort_values(by=['排序', 'date_dt'], ascending=[True, False])
                    browser_week_headlines[week_key] = headline_df.to_dict('records')
                elif not week_df.empty:
                    week_df = week_df.sort_values(by=['排序', 'date_dt'], ascending=[True, False])
                    browser_week_headlines[week_key] = week_df.to_dict('records')
                else:
                    browser_week_headlines[week_key] = []
            
            # 本月所有数据按公司分组（包含所有归属于本月各周的数据）
            all_week_starts_b = [w['start'] for w in browser_weeks_by_month[month_key]]
            all_week_ends_b = [w['end'] for w in browser_weeks_by_month[month_key]]
            if all_week_starts_b and all_week_ends_b:
                range_start_b = datetime.datetime.combine(min(all_week_starts_b), datetime.time.min)
                range_end_b = datetime.datetime.combine(max(all_week_ends_b), datetime.time.max)
            else:
                range_start_b = datetime.datetime(y, m, 1)
                range_end_b = datetime.datetime(y, m + 1, 1) - datetime.timedelta(seconds=1) if m < 12 else datetime.datetime(y + 1, 1, 1) - datetime.timedelta(seconds=1)
            month_exp = df_browser_exploded[(df_browser_exploded['date_dt'] >= range_start_b) & 
                                            (df_browser_exploded['date_dt'] <= range_end_b)].copy()
            browser_data_by_month[month_key] = {}
            for display_name in BROWSER_DISPLAY_ORDER:
                browser_data_by_month[month_key][display_name] = []
            for _, row_data in month_exp.iterrows():
                company_val = row_data['公司_list']
                if company_val in BROWSER_MATCH_MAP:
                    display_name = BROWSER_MATCH_MAP[company_val]
                    browser_data_by_month[month_key][display_name].append(row_data.to_dict())
                else:
                    if '其他浏览器' not in browser_data_by_month[month_key]:
                        browser_data_by_month[month_key]['其他浏览器'] = []
                    browser_data_by_month[month_key]['其他浏览器'].append(row_data.to_dict())
            # 各公司内按日期降序排列
            for k in browser_data_by_month[month_key]:
                browser_data_by_month[month_key][k].sort(key=lambda x: parse_date_for_sort(x.get('日期', '')), reverse=True)

    # --- 输入法部分处理 (按月+按周+按公司分组) ---
    ime_months = []
    ime_weeks_by_month = {}
    ime_week_headlines = {}
    ime_data_by_month = {}

    if not df_ime.empty:
        df_ime_exploded = df_ime.explode('公司_list')
        df_ime['date_dt'] = df_ime['日期'].apply(parse_date_for_sort)
        df_ime_exploded['date_dt'] = df_ime_exploded['日期'].apply(parse_date_for_sort)
        all_ime_dates_dt = [d for d in df_ime['date_dt'] if d != datetime.datetime.min]
        
        month_set = set()
        for dt in all_ime_dates_dt:
            ws, we = get_week_range(dt)
            month_set.add((we.year, we.month))
        
        for (y, m) in sorted(month_set, reverse=True):
            month_key = f"{y}/{m}"
            ime_months.append(month_key)
            
            weeks = get_weeks_in_month(all_ime_dates_dt, y, m)
            ime_weeks_by_month[month_key] = []
            for ws, we in weeks:
                week_key = f"{ws.year}-{ws.month}-{ws.day}_{we.year}-{we.month}-{we.day}"
                week_label = f"{ws.year}/{ws.month}/{ws.day}-{we.year}/{we.month}/{we.day}"
                ime_weeks_by_month[month_key].append({
                    'key': week_key,
                    'label': week_label,
                    'start': ws,
                    'end': we
                })
                week_df = df_ime[(df_ime['date_dt'] >= datetime.datetime.combine(ws, datetime.time.min)) & 
                                  (df_ime['date_dt'] <= datetime.datetime.combine(we, datetime.time.max))].copy()
                headline_df = week_df[week_df['是否头条'] > 0].copy()
                if not headline_df.empty:
                    headline_df = headline_df.sort_values(by=['排序', 'date_dt'], ascending=[True, False])
                    ime_week_headlines[week_key] = headline_df.to_dict('records')
                elif not week_df.empty:
                    week_df = week_df.sort_values(by=['排序', 'date_dt'], ascending=[True, False])
                    ime_week_headlines[week_key] = week_df.to_dict('records')
                else:
                    ime_week_headlines[week_key] = []
            
            # 本月所有数据按公司分组（包含所有归属于本月各周的数据）
            # 收集本月所有周的日期范围
            all_week_starts = [w['start'] for w in ime_weeks_by_month[month_key]]
            all_week_ends = [w['end'] for w in ime_weeks_by_month[month_key]]
            if all_week_starts and all_week_ends:
                range_start = datetime.datetime.combine(min(all_week_starts), datetime.time.min)
                range_end = datetime.datetime.combine(max(all_week_ends), datetime.time.max)
            else:
                range_start = datetime.datetime(y, m, 1)
                range_end = datetime.datetime(y, m + 1, 1) - datetime.timedelta(seconds=1) if m < 12 else datetime.datetime(y + 1, 1, 1) - datetime.timedelta(seconds=1)
            month_exp = df_ime_exploded[(df_ime_exploded['date_dt'] >= range_start) & 
                                        (df_ime_exploded['date_dt'] <= range_end)].copy()
            ime_data_by_month[month_key] = {}
            for display_name in IME_DISPLAY_ORDER:
                ime_data_by_month[month_key][display_name] = []
            for _, row_data in month_exp.iterrows():
                company_val = row_data['公司_list']
                if company_val in IME_MATCH_MAP:
                    display_name = IME_MATCH_MAP[company_val]
                    ime_data_by_month[month_key][display_name].append(row_data.to_dict())
                else:
                    if '其他输入法' not in ime_data_by_month[month_key]:
                        ime_data_by_month[month_key]['其他输入法'] = []
                    ime_data_by_month[month_key]['其他输入法'].append(row_data.to_dict())
            # 各公司内按日期降序排列
            for k in ime_data_by_month[month_key]:
                ime_data_by_month[month_key][k].sort(key=lambda x: parse_date_for_sort(x.get('日期', '')), reverse=True)

    # --- 全量数据用于历史检索 ---
    all_individual_topics = set()
    for t_list in df['话题_list']: all_individual_topics.update(t_list)
    all_unique_topics = sorted(list(all_individual_topics))

    all_individual_companies = set()
    for c_list in df['公司_list']: all_individual_companies.update(c_list)
    all_unique_companies_clean = sorted(list(all_individual_companies), key=lambda x: x.encode('gbk') if isinstance(x, str) else x)

    # 历史检索用数据：只保留必要字段
    search_fields = ['日期', '分类', '话题', '公司', '标题', '核心内容', '来源', '链接', '话题_list', '公司_list', 'year', 'month']
    df_search = df[[c for c in search_fields if c in df.columns]].copy()
    final_json_str = json.dumps(df_search.to_dict('records'), ensure_ascii=False)
    with open("data.json", "w", encoding="utf-8") as f:
        f.write(final_json_str)

    template_str = r"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>全球 AI 核心动态内参</title>
        <meta name="description" content="AI Pulse 深度内参：每日追踪 OpenAI、Google、字节跳动等全球顶级 AI 大厂动态。">
        <meta property="og:image" content="https://www.aipulse.run/logo.jpg?v=2026">
        <link rel="shortcut icon" href="https://www.aipulse.run/logo.jpg">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700&display=swap" rel="stylesheet">
        <style>
            :root { --primary: #1a73e8; --primary-browser: #1a73e8; --primary-ime: #1a73e8; --header-bg: #475569; --bg: #ffffff; --text: #334155; --border: #f1f5f9; --sub-bg: #f8fafc; }
            body { font-family: -apple-system, "PingFang SC", sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.5; }
            .container { max-width: 780px; margin: auto; padding: 10px; }
            header h1 { font-family: 'Noto Serif SC', serif; text-align: center; font-size: 20px; margin: 15px 0 10px; color: #0f172a; }
            
            select { 
                -webkit-appearance: none; appearance: none;
                width: 100%; font-size: 13px; color: #475569; 
                border: 1px solid var(--border); border-radius: 6px; 
                padding: 8px 12px; background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E") no-repeat right 10px center;
                cursor: pointer; transition: all 0.2s;
            }
            select:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.1); }
            
            .control-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 0 4px 6px 4px; border-bottom: 1px solid #f1f5f9; }
            .time-label { font-size: 10px; color: #94a3b8; }
            .date-picker-mini { width: auto !important; padding: 2px 24px 2px 8px !important; font-size: 11px !important; font-weight: bold; color: var(--primary); }

            .tabs-nav { display: flex; justify-content: center; margin-bottom: 15px; border-bottom: 1px solid #f1f5f9; flex-wrap: wrap; gap: 0; }
            .tab-btn { padding: 8px 10px; cursor: pointer; border: none; background: none; font-size: 12.5px; font-weight: 600; color: #94a3b8; position: relative; white-space: nowrap; }
            .tab-btn.active { color: var(--primary) !important; }
            .tab-btn.active::after { content: ''; position: absolute; bottom: -1px; left: 0; width: 100%; height: 2px; background: var(--primary); }
            .tab-content { display: none; }
            .tab-content.active { display: block; }

            .headline-section { margin-bottom: 30px; background: var(--sub-bg); padding-bottom: 10px; border-radius: 0 0 4px 4px; border: 1px solid #edf2f7; border-top: none; }
            .hl-item { padding: 12px; border-bottom: 1px solid #edf2f7; }
            .hl-item:last-child { border-bottom: none; }
            .hl-title { font-size: 15px; font-weight: 700; color: #1e293b; text-decoration: none; display: block; margin-bottom: 4px; font-family: 'Noto Serif SC', serif; line-height: 1.4; }
            .hl-content { font-size: 12px; color: #475569; line-height: 1.6; margin: 6px 0; text-align: justify; }

            .filter-panel { background: #f8fafc; padding: 12px; border-radius: 10px; margin-bottom: 15px; display: flex; flex-direction: column; gap: 8px; }
            .filter-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
            .filter-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
            .btn-search { background: var(--primary); color: white; border: none; padding: 10px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 13px; margin-top: 4px; }

            .sticky-title { position: -webkit-sticky; position: sticky; top: 0; z-index: 1000; background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(8px); padding: 8px 0 8px 10px; margin: 0; color: var(--primary); border-left: 4px solid var(--primary); font-size: 15px; font-weight: 700; border-bottom: 1px solid #f1f5f9; font-family: 'Noto Serif SC', serif; }
            .sticky-title.browser { color: var(--primary); border-left-color: var(--primary); }
            .sticky-title.ime { color: var(--primary); border-left-color: var(--primary); }
            .news-item { padding: 10px 4px; border-bottom: 1px solid #f1f5f9; cursor: pointer; }
            .tag-group { margin-bottom: 4px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
            .tag { font-size: 9px; padding: 1px 5px; font-weight: 600; background: #f1f5f9; color: #64748b; border-radius: 2px; }
            .tag-important { background: #e0f2fe; color: #0369a1; }
            .tag-domestic { background: #fef3c7; color: #b45309; }
            .tag-date { background: #f0fdf4; color: #166534; }
            .title-row { font-size: 14px; font-weight: 600; color: #334155; display: flex; justify-content: space-between; align-items: center; }
            .title-row::after { content: '+'; font-size: 14px; color: #cbd5e1; margin-left: 8px; }
            .news-item.open .title-row::after { content: '\2212'; color: var(--primary); }
            .content-box { display: none; padding: 8px 0; font-size: 12px; color: #475569; line-height: 1.7; text-align: justify; }
            .news-item.open .content-box { display: block; }
            .footer { font-size: 10px; color: #94a3b8; display: flex; justify-content: space-between; margin-top: 8px; }
            .link-btn { color: var(--primary); text-decoration: none; font-weight: 700; }
            .empty-state { text-align: center; padding: 40px 20px; color: #94a3b8; font-size: 13px; }
            .week-select { -webkit-appearance: none; appearance: none; width: auto; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.4); color: #fff; font-size: 11px; padding: 2px 22px 2px 8px; border-radius: 4px; cursor: pointer; font-weight: bold; letter-spacing: 0; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' fill='white' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 6px center; position: absolute; right: 12px; top: 50%; transform: translateY(-50%); }
            .week-select:focus { outline: none; border-color: rgba(255,255,255,0.7); }
            .headline-title { position: -webkit-sticky; position: sticky; top: 0; z-index: 1001; background: var(--header-bg); padding: 10px 0; margin: 0; color: #ffffff; text-align: center; font-size: 15px; font-weight: 700; letter-spacing: 3px; font-family: 'Noto Serif SC', serif; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-radius: 4px 4px 0 0; position: relative; }
            .section-divider { font-size: 14px; font-weight: 700; color: #475569; text-align: center; margin: 20px 0 0; padding: 8px 0; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; background: #f8fafc; font-family: 'Noto Serif SC', serif; letter-spacing: 2px; cursor: pointer; user-select: none; }
            .section-divider::after { content: ' ▾'; font-size: 10px; color: #94a3b8; }
            .section-divider.collapsed::after { content: ' ▸'; }
            .monthly-content { transition: max-height 0.3s ease; overflow: hidden; }
            .monthly-content.collapsed { max-height: 0 !important; }
        </style>
    </head>
    <body>
    <div class="container">
        <header><h1>全球 AI 核心动态内参</h1></header>
        <div class="tabs-nav">
            <div class="tab-btn active" id="btn-daily" onclick="switchTab('daily')">每日AI综述</div>
            <div class="tab-btn" id="btn-browser" onclick="switchTab('browser')">每周浏览器综述</div>
            <div class="tab-btn" id="btn-ime" onclick="switchTab('ime')">每周输入法综述</div>
            <div class="tab-btn" id="btn-filter" onclick="switchTab('filter')">历史检索</div>
        </div>
        
        <!-- ========== 每日AI综述 控制栏 ========== -->
        <div id="ctrl-daily" class="control-bar">
            <div id="current-time-label" class="time-label">监测周期：加载中...</div>
            <select id="dateSelect" class="date-picker-mini" onchange="changeDate(this.value)">
                {% for d in ai_dates %}<option value="{{d}}">{% if '至' in d %}{{ d.split('至')[1].strip() }}{% else %}{{ d }}{% endif %}</option>{% endfor %}
            </select>
        </div>

        <!-- ========== 每周浏览器综述 控制栏 ========== -->
        <div id="ctrl-browser" class="control-bar" style="display:none; justify-content: flex-end;">
            <select id="browserMonthSelect" class="date-picker-mini" onchange="changeBrowserMonth(this.value)">
                {% for m in browser_months %}<option value="{{m}}">{{m.split('/')[0]}}年{{m.split('/')[1]}}月</option>{% endfor %}
                {% if not browser_months %}<option value="">暂无数据</option>{% endif %}
            </select>
        </div>

        <!-- ========== 每周输入法综述 控制栏 ========== -->
        <div id="ctrl-ime" class="control-bar" style="display:none; justify-content: flex-end;">
            <select id="imeMonthSelect" class="date-picker-mini" onchange="changeImeMonth(this.value)">
                {% for m in ime_months %}<option value="{{m}}">{{m.split('/')[0]}}年{{m.split('/')[1]}}月</option>{% endfor %}
                {% if not ime_months %}<option value="">暂无数据</option>{% endif %}
            </select>
        </div>

        <!-- ========== Tab 1: 每日AI综述 ========== -->
        <div id="panel-daily" class="tab-content active">
            {% if ai_dates %}
            {% for d in ai_dates %}
            <div id="date-group-{{d}}" class="date-container" style="display: {{ 'block' if loop.first else 'none' }}">
                {% if headlines_map.get(d) %}
                <div class="headline-section">
                    <h2 class="headline-title">今日重点</h2>
                    {% for hl in headlines_map[d] %}
                    <div class="hl-item">
                        <div class="tag-group">
                            {% for tag in hl['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}
                            <span class="tag">{{hl['公司']}}</span>
                        </div>
                        <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a>
                        <div class="hl-content">{{hl['核心内容']}}</div>
                        <div class="footer">
                            <span>来源: {{hl['来源']}}</span>
                            <a href="{{hl['链接']}}" class="link-btn" target="_blank">阅读原文</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% for co, items in news_data_map[d].items() %}
                <div class="company-section">
                    <h2 class="sticky-title">{{co}}</h2>
                    {% for it in items %}
                    <div class="news-item" onclick="this.classList.toggle('open')">
                        <div class="tag-group">
                            {% for tag in it['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}
                            {% if co == SECONDARY_TITLE or co == '行业新闻' %}<span class="tag tag-domestic">{{it['公司']}}</span>{% endif %}
                        </div>
                        <span class="title-row">{{it['标题']}}</span>
                        <div class="content-box">
                            {{it['核心内容']}}
                            <div class="footer">
                                <span>来源: {{it['来源']}}</span>
                                <a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
            {% endfor %}
            {% else %}
            <div class="empty-state">暂无 AI 动态数据</div>
            {% endif %}
        </div>

        <!-- ========== Tab 2: 每周浏览器综述 ========== -->
        <div id="panel-browser" class="tab-content">
            {% if browser_months %}
            {% for month_key in browser_months %}
            <div id="browser-month-{{month_key.replace('/', '-')}}" class="browser-month-container" style="display: {{ 'block' if loop.first else 'none' }}">
                <!-- 本周动态 with week selector -->
                <div class="headline-section">
                    <h2 class="headline-title">本周动态
                        {% if browser_weeks_by_month.get(month_key) %}
                        <select class="week-select" onchange="changeBrowserWeek('{{month_key.replace('/', '-')}}', this.value)">
                            {% for w in browser_weeks_by_month[month_key] %}
                            <option value="{{w['key']}}">{{w['label']}}</option>
                            {% endfor %}
                        </select>
                        {% endif %}
                    </h2>
                    {% if browser_weeks_by_month.get(month_key) %}
                    {% for w in browser_weeks_by_month[month_key] %}
                    <div class="week-headlines-block" id="browser-week-{{month_key.replace('/', '-')}}-{{w['key']}}" style="display: {{ 'block' if loop.first else 'none' }}">
                        {% if browser_week_headlines.get(w['key']) %}
                        {% for hl in browser_week_headlines[w['key']] %}
                        <div class="hl-item">
                            <div class="tag-group">
                                {% for tag in hl['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}
                                <span class="tag">{{hl['公司']}}</span>
                                <span class="tag tag-date">{{hl['日期']}}</span>
                            </div>
                            <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a>
                            <div class="hl-content">{{hl['核心内容']}}</div>
                            <div class="footer">
                                <span>来源: {{hl['来源']}}</span>
                                <a href="{{hl['链接']}}" class="link-btn" target="_blank">阅读原文</a>
                            </div>
                        </div>
                        {% endfor %}
                        {% else %}
                        <div class="hl-item"><div class="hl-content" style="text-align:center;color:#94a3b8;">本周暂无重点动态</div></div>
                        {% endif %}
                    </div>
                    {% endfor %}
                    {% else %}
                    <div class="hl-item"><div class="hl-content" style="text-align:center;color:#94a3b8;">本月暂无数据</div></div>
                    {% endif %}
                </div>

                <!-- 按公司展示本月所有新闻 -->
                <h3 class="section-divider collapsed" onclick="toggleMonthly(this)">本月动态</h3>
                <div class="monthly-content collapsed">
                {% for company, items in browser_data_by_month[month_key].items() %}
                <div class="company-section">
                    <h2 class="sticky-title browser">{{company}}</h2>
                    {% if items %}
                    {% for it in items %}
                    <div class="news-item" onclick="this.classList.toggle('open')">
                        <div class="tag-group">
                            {% for tag in it['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}
                            <span class="tag tag-date">{{it['日期']}}</span>
                        </div>
                        <span class="title-row">{{it['标题']}}</span>
                        <div class="content-box">
                            {{it['核心内容']}}
                            <div class="footer">
                                <span>来源: {{it['来源']}}</span>
                                <a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                    {% else %}
                    <div class="news-item" style="cursor:default;"><span style="font-size:13px;color:#94a3b8;">无</span></div>
                    {% endif %}
                </div>
                {% endfor %}
                </div>
            </div>
            {% endfor %}
            {% else %}
            <div class="empty-state">暂无浏览器相关新闻</div>
            {% endif %}
        </div>

        <!-- ========== Tab 3: 每周输入法综述 ========== -->
        <div id="panel-ime" class="tab-content">
            {% if ime_months %}
            {% for month_key in ime_months %}
            <div id="ime-month-{{month_key.replace('/', '-')}}" class="ime-month-container" style="display: {{ 'block' if loop.first else 'none' }}">
                <!-- 本周动态 with week selector -->
                <div class="headline-section">
                    <h2 class="headline-title">本周动态
                        {% if ime_weeks_by_month.get(month_key) %}
                        <select class="week-select" onchange="changeImeWeek('{{month_key.replace('/', '-')}}', this.value)">
                            {% for w in ime_weeks_by_month[month_key] %}
                            <option value="{{w['key']}}">{{w['label']}}</option>
                            {% endfor %}
                        </select>
                        {% endif %}
                    </h2>
                    {% if ime_weeks_by_month.get(month_key) %}
                    {% for w in ime_weeks_by_month[month_key] %}
                    <div class="week-headlines-block" id="ime-week-{{month_key.replace('/', '-')}}-{{w['key']}}" style="display: {{ 'block' if loop.first else 'none' }}">
                        {% if ime_week_headlines.get(w['key']) %}
                        {% for hl in ime_week_headlines[w['key']] %}
                        <div class="hl-item">
                            <div class="tag-group">
                                {% for tag in hl['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}
                                <span class="tag">{{hl['公司']}}</span>
                                <span class="tag tag-date">{{hl['日期']}}</span>
                            </div>
                            <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a>
                            <div class="hl-content">{{hl['核心内容']}}</div>
                            <div class="footer">
                                <span>来源: {{hl['来源']}}</span>
                                <a href="{{hl['链接']}}" class="link-btn" target="_blank">阅读原文</a>
                            </div>
                        </div>
                        {% endfor %}
                        {% else %}
                        <div class="hl-item"><div class="hl-content" style="text-align:center;color:#94a3b8;">本周暂无重点动态</div></div>
                        {% endif %}
                    </div>
                    {% endfor %}
                    {% else %}
                    <div class="hl-item"><div class="hl-content" style="text-align:center;color:#94a3b8;">本月暂无数据</div></div>
                    {% endif %}
                </div>

                <!-- 按公司展示本月所有新闻 -->
                <h3 class="section-divider collapsed" onclick="toggleMonthly(this)">本月动态</h3>
                <div class="monthly-content collapsed">
                {% for company, items in ime_data_by_month[month_key].items() %}
                <div class="company-section">
                    <h2 class="sticky-title ime">{{company}}</h2>
                    {% if items %}
                    {% for it in items %}
                    <div class="news-item" onclick="this.classList.toggle('open')">
                        <div class="tag-group">
                            {% for tag in it['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}
                            <span class="tag tag-date">{{it['日期']}}</span>
                        </div>
                        <span class="title-row">{{it['标题']}}</span>
                        <div class="content-box">
                            {{it['核心内容']}}
                            <div class="footer">
                                <span>来源: {{it['来源']}}</span>
                                <a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                    {% else %}
                    <div class="news-item" style="cursor:default;"><span style="font-size:13px;color:#94a3b8;">无</span></div>
                    {% endif %}
                </div>
                {% endfor %}
                </div>
            </div>
            {% endfor %}
            {% else %}
            <div class="empty-state">暂无输入法相关新闻</div>
            {% endif %}
        </div>

        <!-- ========== Tab 4: 历史检索 ========== -->
        <div id="panel-filter" class="tab-content">
            <div class="filter-panel">
                <div class="filter-row-3">
                    <select id="f-category">
                        <option value="all">所有分类</option>
                        <option value="AI">AI动态</option>
                        <option value="浏览器">浏览器动态</option>
                        <option value="输入法">输入法动态</option>
                    </select>
                    <select id="f-year" onchange="updateMonths()"><option value="all">所有年份</option></select>
                    <select id="f-month" onchange="updateDays()"><option value="all">所有月份</option></select>
                </div>
                <div class="filter-row-3">
                    <select id="f-day"><option value="all">具体日期</option></select>
                    <select id="f-co"><option value="all">所有公司</option>{% for c in all_companies_clean %}<option value="{{c}}">{{c}}</option>{% endfor %}</select>
                    <select id="f-topic"><option value="all">所有话题</option>{% for t in all_topics %}<option value="{{t}}">{{t}}</option>{% endfor %}</select>
                </div>
                <button onclick="doSearch()" class="btn-search">立即检索新闻</button>
            </div>
            <div id="results"></div>
        </div>
    </div>
    <script>
        let rawData = [];
        fetch('data.json').then(r => r.json()).then(data => { rawData = data; }).catch(() => { rawData = []; });
        
        function initFilter() {
            const years = [...new Set(rawData.map(it => it.year))].sort((a,b) => b-a);
            const ySelect = document.getElementById('f-year');
            ySelect.innerHTML = '<option value="all">所有年份</option>';
            years.forEach(y => ySelect.add(new Option(y + '年', y)));
            updateMonths();
        }

        function updateMonths() {
            const year = document.getElementById('f-year').value;
            const mSelect = document.getElementById('f-month');
            mSelect.innerHTML = '<option value="all">所有月份</option>';
            let filtered = rawData;
            if(year !== 'all') filtered = rawData.filter(it => it.year == year);
            const months = [...new Set(filtered.map(it => it.month))].sort((a,b) => a-b);
            months.forEach(m => mSelect.add(new Option(m + '月', m)));
            updateDays();
        }

        function updateDays() {
            const year = document.getElementById('f-year').value;
            const month = document.getElementById('f-month').value;
            const dSelect = document.getElementById('f-day');
            dSelect.innerHTML = '<option value="all">具体日期</option>';
            let filtered = rawData;
            if(year !== 'all') filtered = filtered.filter(it => it.year == year);
            if(month !== 'all') filtered = filtered.filter(it => it.month == month);
            const dates = [...new Set(filtered.map(it => it['日期']))];
            dates.forEach(d => {
                const display = d.includes('至') ? d.split('至')[1].trim() : d;
                dSelect.add(new Option(display, d));
            });
        }

        function switchTab(id) {
            document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('panel-' + id).classList.add('active');
            document.getElementById('btn-' + id).classList.add('active');
            // 控制各 tab 的控制栏显示
            document.getElementById('ctrl-daily').style.display = (id === 'daily') ? 'flex' : 'none';
            document.getElementById('ctrl-browser').style.display = (id === 'browser') ? 'flex' : 'none';
            document.getElementById('ctrl-ime').style.display = (id === 'ime') ? 'flex' : 'none';
            if(id === 'filter') { initFilter(); doSearch(); }
        }

        function changeDate(d) {
            document.querySelectorAll('.date-container').forEach(g => g.style.display = 'none');
            const target = document.getElementById('date-group-' + d);
            if(target) target.style.display = 'block';
            updateTimeLabel(d);
        }

        function changeBrowserMonth(monthKey) {
            document.querySelectorAll('.browser-month-container').forEach(g => g.style.display = 'none');
            const target = document.getElementById('browser-month-' + monthKey.replace('/', '-'));
            if(target) target.style.display = 'block';
        }

        function changeImeMonth(monthKey) {
            document.querySelectorAll('.ime-month-container').forEach(g => g.style.display = 'none');
            const target = document.getElementById('ime-month-' + monthKey.replace('/', '-'));
            if(target) target.style.display = 'block';
        }

        function changeBrowserWeek(monthKey, weekKey) {
            const container = document.getElementById('browser-month-' + monthKey);
            if(!container) return;
            container.querySelectorAll('.week-headlines-block').forEach(b => b.style.display = 'none');
            const target = document.getElementById('browser-week-' + monthKey + '-' + weekKey);
            if(target) target.style.display = 'block';
        }

        function changeImeWeek(monthKey, weekKey) {
            const container = document.getElementById('ime-month-' + monthKey);
            if(!container) return;
            container.querySelectorAll('.week-headlines-block').forEach(b => b.style.display = 'none');
            const target = document.getElementById('ime-week-' + monthKey + '-' + weekKey);
            if(target) target.style.display = 'block';
        }

        function updateMonthTimeLabel(monthKey, labelId) {
            const parts = monthKey.split('/');
            const year = parseInt(parts[0]);
            const month = parseInt(parts[1]);
            const lastDay = new Date(year, month, 0).getDate();
            const labelEl = document.getElementById(labelId);
            if (labelEl) labelEl.innerText = '监测周期：' + year + '/' + month + '/1 至 ' + year + '/' + month + '/' + lastDay;
        }

        function updateTimeLabel(d) {
            let startLabel = ""; let endLabel = "";
            if (d.includes("至")) {
                const parts = d.split("至");
                const startObj = new Date(parts[0].trim()); const endObj = new Date(parts[1].trim());
                if (!isNaN(startObj)) {
                    startObj.setDate(startObj.getDate() - 1);
                    startLabel = startObj.getFullYear() + '/' + (startObj.getMonth() + 1) + '/' + startObj.getDate() + ' 17:00';
                    endLabel = endObj.getFullYear() + '/' + (endObj.getMonth() + 1) + '/' + endObj.getDate() + ' 17:00';
                }
            } else {
                const current = new Date(d);
                if (!isNaN(current)) {
                    const prev = new Date(current); prev.setDate(current.getDate() - 1);
                    startLabel = prev.getFullYear() + '/' + (prev.getMonth() + 1) + '/' + prev.getDate() + ' 17:00';
                    endLabel = current.getFullYear() + '/' + (current.getMonth() + 1) + '/' + current.getDate() + ' 17:00';
                }
            }
            const labelEl = document.getElementById('current-time-label');
            if (labelEl) labelEl.innerText = startLabel ? "监测周期：" + startLabel + " 至 " + endLabel : "监测周期：" + d;
        }

        window.onload = () => { 
            const select = document.getElementById('dateSelect'); 
            if(select && select.value) changeDate(select.value);
        };

        function toggleMonthly(el) {
            el.classList.toggle('collapsed');
            const content = el.nextElementSibling;
            if(content) content.classList.toggle('collapsed');
        }

        function doSearch() {
            const category = document.getElementById('f-category').value;
            const year = document.getElementById('f-year').value;
            const month = document.getElementById('f-month').value;
            const day = document.getElementById('f-day').value;
            const company = document.getElementById('f-co').value;
            const topic = document.getElementById('f-topic').value;
            const filtered = rawData.filter(it => {
                const catMatch = (category === 'all' || it['分类'] === category);
                let dateMatch = true;
                if (day !== 'all') { dateMatch = it['日期'] === day; }
                else if (month !== 'all') { dateMatch = (it.year == year && it.month == month); }
                else if (year !== 'all') { dateMatch = it.year == year; }
                const coMatch = (company === 'all' || it['公司'].includes(company));
                const topicMatch = (topic === 'all' || it['话题_list'].includes(topic));
                return catMatch && dateMatch && coMatch && topicMatch;
            });
            const resDiv = document.getElementById('results');
            resDiv.innerHTML = filtered.length ? '' : '<p style="text-align:center; padding:30px; font-size:11px; color:#999;">无匹配新闻</p>';
            filtered.forEach(it => {
                const item = document.createElement('div'); item.className = 'news-item'; item.onclick = () => item.classList.toggle('open');
                const showD = it['日期'].includes('至') ? it['日期'].split('至')[1].trim() : it['日期'].trim();
                let tagsHtml = it['话题_list'].map(tag => '<span class="tag tag-important">' + tag + '</span>').join('');
                let catTag = '';
                if(it['分类'] === '浏览器') catTag = '<span class="tag" style="background:#f5f3ff;color:#7c3aed;">浏览器</span>';
                else if(it['分类'] === '输入法') catTag = '<span class="tag" style="background:#ecfdf5;color:#059669;">输入法</span>';
                else catTag = '<span class="tag" style="background:#eff6ff;color:#1d4ed8;">AI</span>';
                item.innerHTML = '<div class="tag-group">' + catTag + tagsHtml + '<span class="tag tag-date">' + showD + '</span><span class="tag">' + it['公司'] + '</span></div><span class="title-row">' + it['标题'] + '</span><div class="content-box">' + it['核心内容'] + '<div class="footer"><span>来源: ' + it['来源'] + '</span><a href="' + it['链接'] + '" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a></div></div>';
                resDiv.appendChild(item);
            });
        }
    </script>
    </body>
    </html>
    """

    # 4.1 输出生成
    html = Template(template_str).render(
        ai_dates=ai_dates, 
        news_data_map=news_data_map, 
        headlines_map=headlines_map, 
        browser_months=browser_months,
        browser_data_by_month=browser_data_by_month,
        browser_weeks_by_month=browser_weeks_by_month,
        browser_week_headlines=browser_week_headlines,
        ime_months=ime_months,
        ime_data_by_month=ime_data_by_month,
        ime_weeks_by_month=ime_weeks_by_month,
        ime_week_headlines=ime_week_headlines,
        all_companies_clean=all_unique_companies_clean,
        all_topics=all_unique_topics,
        SECONDARY_TITLE=SECONDARY_TITLE
    )
    
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)
    with open("CNAME", "w") as f: f.write(MY_DOMAIN)

    # 微信验证文件
    verify_filename = "9e6e1fc6e963e82b5025e7569958c4bb.txt"
    verify_content = "9228ad55ba9d00917e9f086a3830b550f27e545c"
    with open(verify_filename, "w", encoding="utf-8") as f:
        f.write(verify_content)

    print("✅ index.html 已生成")
    print(f"✅ CNAME: {MY_DOMAIN}")
    print(f"✅ 微信验证文件: {verify_filename}")

if __name__ == "__main__":
    main()
