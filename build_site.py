import pandas as pd
from jinja2 import Template
import json
import sys
import os
import datetime # 导入 datetime 模块

# ==========================================
# 1. 基础配置与排序权重定义
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
MY_DOMAIN = "www.aipulse.run"

CORE_COMPANIES = ['OpenAI', 'Google', 'Anthropic', 'Meta', '字节跳动', '阿里巴巴', '腾讯', '百度']
SECONDARY_COMPANIES = ['Kimi', 'MiniMax', '智谱', 'xAI', '可灵', 'DeepSeek']
SECONDARY_TITLE = "其余重点关注公司"
# 话题优先级：数据洞察 > 技术迭代 > 产品动态 > 商业动态 > 春节活动
TOPIC_ORDER = ['数据洞察', '技术迭代', '产品动态', '商业动态', '春节活动']

OTHER_PRIORITY = [
    'Perplexity', 'Character.ai', 'Midjourney', 'Pika', 'Runway', 
    'Suno', 'Luma', 'Grok', 'Mistral', 'Cohere', 'Hugging Face', 'OpenClaw',
    'Microsoft', 'Apple', 'NVIDIA', 'AMD', 'Intel', 'TSMC', 'Samsung', 'Amazon',
    'Tesla', 'Notion', 'Canva', 'Adobe', 'GitHub', 'Arc', 'Cursor', 'Groq',
    '特斯拉', '波士顿动力', '宇树', '智元', '银河', '星海图', 'Fiture', 'Figure', 
    'Sanctuary AI', '1X Technologies', 'Agility Robotics'
]

# --- 新增日期解析函数 ---
def parse_date_for_sort(date_str):
    """
    解析日期字符串，用于排序。
    如果日期是 'yyyy/mm/dd至yyyy/mm/dd' 格式，则使用结束日期进行排序。
    否则，使用单一日期。
    """
    if '至' in date_str:
        # 对于日期范围，我们使用范围的结束日期进行排序，确保最新范围排在前面
        date_part = date_str.split('至')[1].strip()
    else:
        date_part = date_str.strip()
        
    try:
        return datetime.datetime.strptime(date_part, '%Y/%m/%d')
    except ValueError:
        # 如果日期格式不符合预期，返回一个极小值，确保它排在最后
        print(f"警告: 无法解析日期字符串 '{date_str}'。将其排在最后。")
        return datetime.datetime.min

def main():
    # ==========================================
    # 2. 数据读取与预处理
    # ==========================================
    try:
        df = pd.read_csv(SHEET_URL)
    except Exception as e:
        print(f"❌ 无法从 Google Sheets 获取数据: {e}")
        if os.path.exists("data.csv"):
            df = pd.read_csv("data.csv")
        else:
            sys.exit(1)

    df.columns = [c.strip() for c in df.columns]
    name_map = {'字节': '字节跳动', '阿里': '阿里巴巴', 'Baidu': '百度', 'minimax': 'MiniMax', '智谱AI': '智谱', 'OpenAI ': 'OpenAI'}
    df['公司'] = df['公司'].replace(name_map)
    
    # 转换“是否头条”为数字，处理空格和空值
    df['是否头条'] = pd.to_numeric(df['是否头条'], errors='coerce').fillna(0).astype(int)
    df = df.fillna("")
    
    # 提取所有不重复公司（供检索使用）
    all_unique_companies = sorted(df['公司'].unique().tolist(), key=lambda x: x.encode('gbk') if isinstance(x, str) else x)
    # --- 新增：提取所有不重复话题（供检索使用） ---
    all_unique_topics = sorted(df['话题'].unique().tolist())

    # --- 修改这里：获取所有唯一日期并按最新日期降序排列 ---
    all_dates = df['日期'].unique().tolist()
    all_dates.sort(key=parse_date_for_sort, reverse=True) # 使用自定义函数进行排序，最新日期在前
    # ---------------------------------------------------

    news_data_map = {}
    headlines_map = {}

    for date in all_dates: # 这里的循环将按照排序后的日期顺序进行
        day_df = df[df['日期'] == date].copy() # 使用原始 df，因为 df_sorted 没有被再次修改
        
        # --- A. 今日头条板块排序 ---
        # 逻辑：1. 数字从小到大排 (1 > 2)； 2. 数字相同时按公司顺序排； 3. 公司相同时按话题排
        headline_df = day_df[day_df['是否头条'] > 0].copy()
        if not headline_df.empty:
            headline_df['c_rank'] = headline_df['公司'].apply(get_company_rank)
            headline_df['t_rank'] = headline_df['话题'].apply(get_topic_rank)
            headlines_map[date] = headline_df.sort_values(by=['是否头条', 'c_rank', 't_rank'], ascending=[True, True, True]).to_dict('records')
        else:
            headlines_map[date] = []

        news_data_map[date] = {}
        
        # --- B. 分公司/板块内部排序辅助函数 ---
        def sort_section_data(data_df, is_other=False):
            # 排序权重：
            # 1. 头条(数字>0)永远在非头条(数字=0)之前
            # 2. 如果都是头条，按数字 1,2,3 升序
            # 3. 如果都不是头条，按话题优先级排
            # 4. 最后按公司预设权重排
            
            def calc_internal_score(row):
                val = row['是否头条']
                t_idx = get_topic_rank(row['话题'])
                if val > 0:
                    # 头条区间：0-100分。数字越小分数越低，越靠前
                    return val 
                else:
                    # 非头条区间：1000分起。按话题权重累加
                    return 1000 + t_idx

            data_df['internal_score'] = data_df.apply(calc_internal_score, axis=1)
            
            if is_other:
                data_df['co_rank'] = data_df['公司'].apply(lambda x: OTHER_PRIORITY.index(x) if x in OTHER_PRIORITY else 999)
                return data_df.sort_values(by=['internal_score', 'co_rank']).to_dict('records')
            else:
                return data_df.sort_values(by='internal_score').to_dict('records')

        # 1. 核心大厂
        for company in CORE_COMPANIES:
            comp_df = day_df[day_df['公司'] == company].copy()
            if not comp_df.empty:
                news_data_map[date][company] = sort_section_data(comp_df)
        
        # 2. 重点关注模型
        sec_df = day_df[day_df['公司'].isin(SECONDARY_COMPANIES)].copy()
        if not sec_df.empty:
            news_data_map[date][SECONDARY_TITLE] = sort_section_data(sec_df)
        
        # 3. 其余行业新闻
        other_df = day_df[~df['公司'].isin(CORE_COMPANIES + SECONDARY_COMPANIES)].copy()
        if not other_df.empty:
            news_data_map[date]['行业新闻'] = sort_section_data(other_df, is_other=True)

    final_json_str = json.dumps(df.to_dict('records'), ensure_ascii=False)

    # ==========================================
    # 4. HTML 模板
    # ==========================================
    template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>全球 AI 核心动态内参</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700&display=swap" rel="stylesheet">
        <style>
            :root { --primary: #1a73e8; --header-bg: #475569; --bg: #ffffff; --text: #334155; --border: #f1f5f9; --sub-bg: #f8fafc; }
            body { font-family: -apple-system, "PingFang SC", sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.5; -webkit-font-smoothing: antialiased; }
            .container { max-width: 780px; margin: auto; padding: 10px; }
            header h1 { font-family: 'Noto Serif SC', serif; text-align: center; font-size: 20px; margin: 15px 0 10px; color: #0f172a; }
            .control-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 0 4px 6px 4px; border-bottom: 1px solid #f1f5f9; }
            .time-label { font-size: 10px; color: #94a3b8; }
            .date-picker { font-size: 10px; color: var(--primary); font-weight: bold; border: 1px solid #e2e8f0; border-radius: 2px; padding: 1px 4px; background: transparent; cursor: pointer; }
            .tabs-nav { display: flex; justify-content: center; margin-bottom: 15px; border-bottom: 1px solid #f1f5f9; }
            .tab-btn { padding: 8px 16px; cursor: pointer; border: none; background: none; font-size: 13.5px; font-weight: 600; color: #94a3b8; position: relative; }
            .tab-btn.active { color: var(--primary) !important; }
            .tab-btn.active::after { content: ''; position: absolute; bottom: -1px; left: 0; width: 100%; height: 2px; background: var(--primary); }
            .tab-content { display: none; }
            .tab-content.active { display: block; }
            .sticky-title { position: -webkit-sticky; position: sticky; top: 0; z-index: 1000; background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(8px); padding: 8px 0 8px 10px; margin: 0; color: var(--primary); border-left: 4px solid var(--primary); font-size: 15px; font-weight: 700; border-bottom: 1px solid #f1f5f9; font-family: 'Noto Serif SC', serif; }
            .headline-title { position: -webkit-sticky; position: sticky; top: 0; z-index: 1001; background: var(--header-bg); padding: 10px 0; margin: 0; color: #ffffff; text-align: center; font-size: 15px; font-weight: 700; letter-spacing: 3px; font-family: 'Noto Serif SC', serif; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
            .headline-section { margin-bottom: 30px; background: var(--sub-bg); padding-bottom: 10px; border-radius: 0 0 4px 4px; }
            .hl-item { padding: 12px; border-bottom: 1px solid #edf2f7; }
            .hl-item:last-child { border-bottom: none; }
            .hl-title { font-size: 15px; font-weight: 700; color: #1e293b; text-decoration: none; display: block; margin-bottom: 4px; font-family: 'Noto Serif SC', serif; line-height: 1.4; }
            .hl-content { font-size: 12px; color: #475569; line-height: 1.6; margin: 6px 0; text-align: justify; }
            .news-item { padding: 10px 4px; border-bottom: 1px solid #f1f5f9; cursor: pointer; }
            .tag-group { margin-bottom: 4px; display: flex; gap: 6px; align-items: center; }
            .tag { font-size: 9px; padding: 1px 5px; font-weight: 600; background: #f1f5f9; color: #64748b; border-radius: 2px; }
            .tag-important { background: #e0f2fe; color: #0369a1; }
            .tag-domestic { background: #fef3c7; color: #b45309; }
            .title-row { font-size: 14px; font-weight: 600; color: #334155; display: flex; justify-content: space-between; align-items: center; }
            .title-row::after { content: '+'; font-size: 14px; color: #cbd5e1; }
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
        <div id="panel-daily" class="tab-content active">
            <div class="control-bar">
                <div id="current-time-label" class="time-label">监测周期：加载中...</div>
                <div style="display: flex; align-items: center;">
                    <span style="font-size:10px; color:#94a3b8;">日期：</span>
                    <select id="dateSelect" class="date-picker" onchange="changeDate(this.value)">
                        {% for d in dates %}
                        <option value="{{d}}">
                            {% if '至' in d %}{{ d.split('至')[1].strip() }}{% else %}{{ d }}{% endif %}
                        </option>
                        {% endfor %}
                    </select>
                </div>
            </div>
            {% for d in dates %}
            <div id="date-group-{{d}}" class="date-container" style="display: {{ 'block' if loop.first else 'none' }}">
                {% if headlines_map[d] %}
                <div class="headline-section">
                    <h2 class="headline-title">今日头条</h2>
                    {% for hl in headlines_map[d] %}
                    <div class="hl-item">
                        <div class="tag-group">
                            <span class="tag tag-important">{{hl['话题']}}</span>
                            <span class="tag">公司/模型：{{hl['公司']}}</span>
                        </div>
                        <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a>
                        <div class="hl-content">{{hl['核心内容']}}</div>
                        <div class="footer"><span>来源: {{hl['来源']}}</span><a href="{{hl['链接']}}" class="link-btn" target="_blank">阅读原文</a></div>
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
                            <span class="tag tag-important">{{it['话题']}}</span>
                            {% if co == SECONDARY_TITLE or co == '行业新闻' %}<span class="tag tag-domestic">{{it['公司']}}</span>{% endif %}
                        </div>
                        <span class="title-row">{{it['标题']}}</span>
                        <div class="content-box">{{it['核心内容']}}<div class="footer"><span>来源: {{it['来源']}}</span><a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a></div></div>
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
        <div id="panel-filter" class="tab-content">
            <div style="padding:10px 0; display:flex; gap:6px; margin-bottom:15px; position: sticky; top: 0; z-index: 101; background: #fff; border-bottom: 1px solid #eee;">
                <select id="f-date" style="flex:1; font-size:11px;"><option value="all">全时间段</option>{% for d in dates %}<option value="{{d}}">{% if '至' in d %}{{ d.split('至')[1].strip() }}{% else %}{{ d }}{% endif %}</option>{% endfor %}</select>
                <select id="f-co" style="flex:1; font-size:11px;"><option value="all">所有公司/模型</option>{% for c in all_companies %}<option value="{{c}}">{{c}}</option>{% endfor %}</select>
                <!-- NEW: 话题筛选器 -->
                <select id="f-topic" style="flex:1; font-size:11px;"><option value="all">所有话题</option>{% for t in all_topics %}<option value="{{t}}">{{t}}</option>{% endfor %}</select>
                <button onclick="doSearch()" style="background:var(--primary); color:white; border:none; padding:4px 12px; font-size:11px; border-radius:2px; cursor:pointer;">检索</button>
            </div>
            <div id="results"></div>
        </div>
    </div>
    <script>
        const rawData = {{ final_json_str | safe }};
        function switchTab(id) {
            document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('panel-' + id).classList.add('active');
            document.getElementById('btn-' + id).classList.add('active');
            window.scrollTo(0,0);
            if(id === 'filter') doSearch(); // 切换到历史检索时自动触发一次检索
        }
        function changeDate(d) {
            document.querySelectorAll('.date-container').forEach(g => g.style.display = 'none');
            const target = document.getElementById('date-group-' + d);
            if(target) { target.style.display = 'block'; updateTimeLabel(d); }
        }
        
        function updateTimeLabel(d) {
            let startLabel = ""; let endLabel = "";
            if (d.includes("至")) {
                const parts = d.split("至");
                const startObj = new Date(parts[0].trim());
                const endObj = new Date(parts[1].trim());
                if (!isNaN(startObj) && !isNaN(endObj)) {
                    startObj.setDate(startObj.getDate() - 1);
                    startLabel = startObj.getFullYear() + '/' + (startObj.getMonth() + 1) + '/' + startObj.getDate() + ' 17:00';
                    endLabel = endObj.getFullYear() + '/' + (endObj.getMonth() + 1) + '/' + endObj.getDate() + ' 17:00';
                }
            } else {
                const current = new Date(d);
                if (!isNaN(current)) {
                    const prev = new Date(current);
                    prev.setDate(current.getDate() - 1);
                    startLabel = prev.getFullYear() + '/' + (prev.getMonth() + 1) + '/' + prev.getDate() + ' 17:00';
                    endLabel = current.getFullYear() + '/' + (current.getMonth() + 1) + '/' + current.getDate() + ' 17:00';
                }
            }
            if (startLabel && endLabel) {
                document.getElementById('current-time-label').innerText = "监测周期：" + startLabel + " 至 " + endLabel;
            } else {
                document.getElementById('current-time-label').innerText = "监测周期：" + d;
            }
        }

        window.onload = () => { 
            const select = document.getElementById('dateSelect'); 
            if(select) changeDate(select.value); 
        };

        function doSearch() {
            const d = document.getElementById('f-date').value;
            const c = document.getElementById('f-co').value;
            const t = document.getElementById('f-topic').value; // NEW: 获取话题类型

            const filtered = rawData.filter(it => 
                (d === 'all' || it['日期'] == d) && 
                (c === 'all' || it['公司'] == c) &&
                (t === 'all' || it['话题'] == t) // NEW: 添加话题筛选条件
            );
            const resDiv = document.getElementById('results');
            resDiv.innerHTML = filtered.length ? '' : '<p style="text-align:center; padding:30px; font-size:11px; color:#999;">无匹配情报</p>';
            filtered.forEach(it => {
                const item = document.createElement('div'); item.className = 'news-item'; item.onclick = () => item.classList.toggle('open');
                const showD = it['日期'].includes('至') ? it['日期'].split('至')[1].trim() : it['日期'];
                item.innerHTML = `<div class="tag-group"><span class="tag tag-important">${it['话题']}</span><span class="tag">${showD}</span><span class="tag">公司/模型：${it['公司']}</span></div><span class="title-row">${it['标题']}</span><div class="content-box">${it['核心内容']}<div class="footer"><span>来源: ${it['来源']}</span><a href="${it['链接']}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a></div></div>`;
                resDiv.appendChild(item);
            });
        }
    </script>
    </body>
    </html>
    """

    # 最终渲染输出
    html = Template(template_str).render(
        dates=all_dates, # 传递已经排序的日期列表
        news_data_map=news_data_map, 
        headlines_map=headlines_map, 
        final_json_str=final_json_str, 
        all_companies=all_unique_companies,
        all_topics=all_unique_topics, # NEW: 传递所有话题
        SECONDARY_TITLE=SECONDARY_TITLE
    )
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    with open("CNAME", "w") as f:
        f.write(MY_DOMAIN)

if __name__ == "__main__":
    main()
