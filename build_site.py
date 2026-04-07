import pandas as pd
from jinja2 import Template
import json
import sys
import os
import datetime

# ==========================================
# 1. 基础配置与排序权重定义
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
MY_DOMAIN = "www.aipulse.run"

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

# --- 辅助函数 ---
def parse_date_for_sort(date_str):
    d_part = date_str.split('至')[1].strip() if '至' in date_str else date_str.strip()
    try:
        return datetime.datetime.strptime(d_part, '%Y/%m/%d')
    except:
        return datetime.datetime.min

def get_company_rank(c_val):
    if c_val in CORE_COMPANIES: return CORE_COMPANIES.index(c_val)
    if c_val in SECONDARY_COMPANIES: return len(CORE_COMPANIES) + SECONDARY_COMPANIES.index(c_val)
    return 999

def get_topic_rank(t_val):
    main_topic = t_val[0] if isinstance(t_val, list) and len(t_val) > 0 else t_val
    return TOPIC_ORDER.index(main_topic) if main_topic in TOPIC_ORDER else 99

def main():
    try:
        df = pd.read_csv(SHEET_URL)
    except Exception as e:
        print(f"❌ 读取错误: {e}")
        if os.path.exists("data.csv"): df = pd.read_csv("data.csv")
        else: sys.exit(1)

    df.columns = [c.strip() for c in df.columns]
    name_map = {'字节': '字节跳动', '阿里': '阿里巴巴', 'Baidu': '百度', 'minimax': 'MiniMax', '智谱AI': '智谱', 'OpenAI ': 'OpenAI'}
    df['公司'] = df['公司'].replace(name_map)
    df['是否头条'] = pd.to_numeric(df['是否头条'], errors='coerce').fillna(0).astype(int)
    df = df.fillna("")
    
    # 话题与公司拆分
    df['话题_list'] = df['话题'].apply(lambda x: [i.strip() for i in str(x).replace(' ', '').split('、')] if x else [])
    df['公司_list'] = df['公司'].apply(lambda x: [i.strip() for i in str(x).split('、')] if x else [])
    
    # 提取所有不重复公司
    all_individual_companies = set()
    for c_list in df['公司_list']:
        all_individual_companies.update(c_list)
    all_unique_companies_clean = sorted(list(all_individual_companies), key=lambda x: x.encode('gbk') if isinstance(x, str) else x)

    # 提取所有不重复话题
    all_individual_topics = set()
    for t_list in df['话题_list']:
        all_individual_topics.update(t_list)
    all_unique_topics = sorted(list(all_individual_topics))

    # 解析年月日用于级联
    def get_ymd(date_str):
        dt = parse_date_for_sort(date_str)
        # 格式化日期显示（移除“至”前面的部分）
        clean_d = date_str.split('至')[1].strip() if '至' in date_str else date_str.strip()
        return dt.year, dt.month, clean_d

    df['year'] = df['日期'].apply(lambda x: get_ymd(x)[0])
    df['month'] = df['日期'].apply(lambda x: get_ymd(x)[1])
    df['day_display'] = df['日期'].apply(lambda x: get_ymd(x)[2])

    # 爆炸处理
    df_exploded = df.explode('公司_list')
    all_dates = df['日期'].unique().tolist()
    all_dates.sort(key=parse_date_for_sort, reverse=True)

    # 分发排序逻辑
    news_data_map = {}
    headlines_map = {}

    for date in all_dates:
        day_df_orig = df[df['日期'] == date].copy()
        headline_df = day_df_orig[day_df_orig['是否头条'] > 0].copy()
        if not headline_df.empty:
            headline_df['c_rank'] = headline_df['公司'].apply(get_company_rank)
            headline_df['t_rank'] = headline_df['话题_list'].apply(get_topic_rank)
            headlines_map[date] = headline_df.sort_values(by=['是否头条', 'c_rank', 't_rank']).to_dict('records')
        else:
            headlines_map[date] = []

        day_df_exp = df_exploded[df_exploded['日期'] == date].copy()
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

    # 导出包含年月日的完整数据给 JS
    final_json_str = json.dumps(df.to_dict('records'), ensure_ascii=False)

    template_str = """
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
            :root { --primary: #1a73e8; --header-bg: #475569; --bg: #ffffff; --text: #334155; --border: #e2e8f0; --sub-bg: #f8fafc; }
            body { font-family: -apple-system, "PingFang SC", sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.5; }
            .container { max-width: 780px; margin: auto; padding: 10px; }
            header h1 { font-family: 'Noto Serif SC', serif; text-align: center; font-size: 20px; margin: 15px 0 10px; color: #0f172a; }
            
            /* 控制条外形统一 */
            .control-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 0 4px 6px 4px; border-bottom: 1px solid #f1f5f9; }
            .time-label { font-size: 10px; color: #94a3b8; }
            
            /* 统一筛选框外形 */
            select { 
                -webkit-appearance: none; 
                appearance: none;
                font-size: 13px; 
                color: #475569; 
                border: 1px solid var(--border); 
                border-radius: 6px; 
                padding: 6px 12px; 
                background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E") no-repeat right 10px center;
                cursor: pointer;
                transition: all 0.2s;
            }
            select:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.1); }
            
            .tabs-nav { display: flex; justify-content: center; margin-bottom: 15px; border-bottom: 1px solid #f1f5f9; }
            .tab-btn { padding: 8px 16px; cursor: pointer; border: none; background: none; font-size: 13.5px; font-weight: 600; color: #94a3b8; position: relative; }
            .tab-btn.active { color: var(--primary) !important; }
            .tab-btn.active::after { content: ''; position: absolute; bottom: -1px; left: 0; width: 100%; height: 2px; background: var(--primary); }
            .tab-content { display: none; }
            .tab-content.active { display: block; }

            /* 历史检索面板布局 */
            .filter-group { background: #f8fafc; padding: 15px; border-radius: 12px; margin-bottom: 20px; display: flex; flex-direction: column; gap: 10px; }
            .filter-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
            .filter-full-row { display: grid; grid-template-columns: 1fr 100px; gap: 8px; }
            .btn-search { background: var(--primary); color: white; border: none; padding: 8px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 13px; }

            /* 内容样式 */
            .sticky-title { position: -webkit-sticky; position: sticky; top: 0; z-index: 1000; background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(8px); padding: 8px 0 8px 10px; margin: 0; color: var(--primary); border-left: 4px solid var(--primary); font-size: 15px; font-weight: 700; border-bottom: 1px solid #f1f5f9; font-family: 'Noto Serif SC', serif; }
            .headline-title { position: -webkit-sticky; position: sticky; top: 0; z-index: 1001; background: var(--header-bg); padding: 10px 0; margin: 0; color: #ffffff; text-align: center; font-size: 15px; font-weight: 700; letter-spacing: 3px; font-family: 'Noto Serif SC', serif; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
            .headline-section { margin-bottom: 30px; background: var(--sub-bg); padding-bottom: 10px; border-radius: 0 0 4px 4px; }
            .news-item { padding: 10px 4px; border-bottom: 1px solid #f1f5f9; cursor: pointer; }
            .tag-group { margin-bottom: 4px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
            .tag { font-size: 9px; padding: 1px 5px; font-weight: 600; background: #f1f5f9; color: #64748b; border-radius: 2px; }
            .tag-important { background: #e0f2fe; color: #0369a1; }
            .tag-domestic { background: #fef3c7; color: #b45309; }
            .title-row { font-size: 14px; font-weight: 600; color: #334155; display: flex; justify-content: space-between; align-items: center; }
            .title-row::after { content: '+'; font-size: 14px; color: #cbd5e1; margin-left: 8px; }
            .news-item.open .title-row::after { content: '−'; color: var(--primary); }
            .content-box { display: none; padding: 8px 0; font-size: 12px; color: #475569; line-height: 1.7; text-align: justify; }
            .news-item.open .content-box { display: block; }
            .footer { font-size: 10px; color: #94a3b8; display: flex; justify-content: space-between; margin-top: 8px; }
            .link-btn { color: var(--primary); text-decoration: none; font-weight: 700; }
        </style>
    </head>
    <body>
    <div class="container">
        <header><h1>全球 AI 核心动态内参</h1></header>
        <div class="tabs-nav">
            <div class="tab-btn active" id="btn-daily" onclick="switchTab('daily')">每日综述</div>
            <div class="tab-btn" id="btn-filter" onclick="switchTab('filter')">历史检索</div>
        </div>
        
        <div id="main-control-bar" class="control-bar">
            <div id="current-time-label" class="time-label">监测周期：加载中...</div>
            <select id="dateSelect" onchange="changeDate(this.value)">
                {% for d in dates %}<option value="{{d}}">{% if '至' in d %}{{ d.split('至')[1].strip() }}{% else %}{{ d }}{% endif %}</option>{% endfor %}
            </select>
        </div>
        
        <div id="panel-daily" class="tab-content active">
            {% for d in dates %}
            <div id="date-group-{{d}}" class="date-container" style="display: {{ 'block' if loop.first else 'none' }}">
                {% if headlines_map[d] %}<div class="headline-section"><h2 class="headline-title">今日重点</h2>
                {% for hl in headlines_map[d] %}<div class="hl-item"><div class="tag-group">{% for tag in hl['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}<span class="tag">{{hl['公司']}}</span></div>
                <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a><div class="hl-content">{{hl['核心内容']}}</div><div class="footer"><span>来源: {{hl['来源']}}</span><a href="{{hl['链接']}}" class="link-btn" target="_blank">阅读原文</a></div></div>{% endfor %}</div>{% endif %}
                {% for co, items in news_data_map[d].items() %}<div class="company-section"><h2 class="sticky-title">{{co}}</h2>
                {% for it in items %}<div class="news-item" onclick="this.classList.toggle('open')"><div class="tag-group">{% for tag in it['话题_list'] %}<span class="tag tag-important">{{tag}}</span>{% endfor %}{% if co == SECONDARY_TITLE or co == '行业新闻' %}<span class="tag tag-domestic">{{it['公司']}}</span>{% endif %}</div>
                <span class="title-row">{{it['标题']}}</span><div class="content-box">{{it['核心内容']}}<div class="footer"><span>来源: {{it['来源']}}</span><a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a></div></div></div>{% endfor %}</div>{% endfor %}
            </div>
            {% endfor %}
        </div>

        <div id="panel-filter" class="tab-content">
            <div class="filter-group">
                <div class="filter-row">
                    <select id="f-year" onchange="updateMonthList()"><option value="all">年份</option></select>
                    <select id="f-month" onchange="updateDayList()"><option value="all">月份</option></select>
                    <select id="f-day"><option value="all">具体日期</option></select>
                </div>
                <div class="filter-row" style="grid-template-columns: 1fr 1fr;">
                    <select id="f-co"><option value="all">所有公司</option>{% for c in all_companies_clean %}<option value="{{c}}">{{c}}</option>{% endfor %}</select>
                    <select id="f-topic"><option value="all">所有话题</option>{% for t in all_topics %}<option value="{{t}}">{{t}}</option>{% endfor %}</select>
                </div>
                <button onclick="doSearch()" class="btn-search">立即检索新闻</button>
            </div>
            <div id="results"></div>
        </div>
    </div>
    <script>
        const rawData = {{ final_json_str | safe }};
        
        // 级联筛选初始化
        function initCascade() {
            const years = [...new Set(rawData.map(it => it.year))].sort((a,b) => b-a);
            const ySelect = document.getElementById('f-year');
            years.forEach(y => {
                let opt = new Option(y + '年', y);
                ySelect.add(opt);
            });
        }

        function updateMonthList() {
            const y = document.getElementById('f-year').value;
            const mSelect = document.getElementById('f-month');
            mSelect.innerHTML = '<option value="all">月份</option>';
            document.getElementById('f-day').innerHTML = '<option value="all">具体日期</option>';
            
            if(y === 'all') return;
            const months = [...new Set(rawData.filter(it => it.year == y).map(it => it.month))].sort((a,b) => a-b);
            months.forEach(m => {
                let opt = new Option(m + '月', m);
                mSelect.add(opt);
            });
        }

        function updateDayList() {
            const y = document.getElementById('f-year').value;
            const m = document.getElementById('f-month').value;
            const dSelect = document.getElementById('f-day');
            dSelect.innerHTML = '<option value="all">具体日期</option>';
            
            if(m === 'all') return;
            const days = [...new Set(rawData.filter(it => it.year == y && it.month == m).map(it => it.日期))];
            days.forEach(d => {
                let display = d.includes('至') ? d.split('至')[1].trim() : d;
                let opt = new Option(display, d);
                dSelect.add(opt);
            });
        }

        function switchTab(id) {
            document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('panel-' + id).classList.add('active');
            document.getElementById('btn-' + id).classList.add('active');
            const ctrlBar = document.getElementById('main-control-bar');
            if (ctrlBar) { ctrlBar.style.display = (id === 'filter') ? 'none' : 'flex'; }
            if(id === 'filter') { initCascade(); doSearch(); }
        }

        function changeDate(d) {
            document.querySelectorAll('.date-container').forEach(g => g.style.display = 'none');
            const target = document.getElementById('date-group-' + d);
            if(target) target.style.display = 'block';
            updateTimeLabel(d);
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
            if (labelEl) { labelEl.innerText = startLabel ? "监测周期：" + startLabel + " 至 " + endLabel : "监测周期：" + d; }
        }

        window.onload = () => { 
            const select = document.getElementById('dateSelect'); 
            if(select) { changeDate(select.value); }
        };

        function doSearch() {
            const y = document.getElementById('f-year').value;
            const m = document.getElementById('f-month').value;
            const d = document.getElementById('f-day').value;
            const c = document.getElementById('f-co').value;
            const t = document.getElementById('f-topic').value;
            
            const filtered = rawData.filter(it => {
                let dateMatch = true;
                if (d !== 'all') { dateMatch = (it['日期'] === d); }
                else if (m !== 'all') { dateMatch = (it['year'].toString() === y && it['month'].toString() === m); }
                else if (y !== 'all') { dateMatch = (it['year'].toString() === y); }

                const coMatch = (c === 'all' || it['公司'].includes(c));
                const topicMatch = (t === 'all' || it['话题_list'].includes(t));
                return dateMatch && coMatch && topicMatch;
            });

            const resDiv = document.getElementById('results');
            resDiv.innerHTML = filtered.length ? '' : '<p style="text-align:center; padding:30px; font-size:11px; color:#999;">无匹配新闻</p>';
            filtered.forEach(it => {
                const item = document.createElement('div'); item.className = 'news-item'; item.onclick = () => item.classList.toggle('open');
                const showD = it['日期'].includes('至') ? it['日期'].split('至')[1].strip() : it['日期'].trim();
                let tagsHtml = it['话题_list'].map(tag => `<span class="tag tag-important">${tag}</span>`).join('');
                item.innerHTML = `<div class="tag-group">${tagsHtml}<span class="tag">${showD}</span><span class="tag">${it['公司']}</span></div><span class="title-row">${it['标题']}</span><div class="content-box">${it['核心内容']}<div class="footer"><span>来源: ${it['来源']}</span><a href="${it['链接']}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a></div></div>`;
                resDiv.appendChild(item);
            });
        }
    </script>
    </body>
    </html>
    """

    html = Template(template_str).render(
        dates=all_dates, 
        news_data_map=news_data_map, 
        headlines_map=headlines_map, 
        final_json_str=final_json_str, 
        all_companies_clean=all_unique_companies_clean,
        all_topics=all_unique_topics,
        SECONDARY_TITLE=SECONDARY_TITLE
    )
    
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)
    with open("CNAME", "w") as f: f.write(MY_DOMAIN)

    verify_filename = "9e6e1fc6e963e82b5025e7569958c4bb.txt"
    verify_content = "9228ad55ba9d00917e9f086a3830b550f27e545c"
    with open(verify_filename, "w", encoding="utf-8") as f:
        f.write(verify_content)

if __name__ == "__main__":
    main()
