import pandas as pd
from jinja2 import Template
import json

# 1. 基础配置
SHEET_URL = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
COMPANY_ORDER = ['OpenAI', 'Anthropic', 'Google', 'Meta', '字节', '阿里', '腾讯', '其他']
TOPIC_ORDER = ['技术迭代', '产品动态', '商业动态', '春节活动', '数据洞察']

def main():
    # 2. 读取并清洗数据
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # 填充缺失值防止 JS 报错
        df = df.fillna("")
    except Exception as e:
        print(f"数据读取失败: {e}")
        return

    # 3. 排序逻辑（用于 Tab 1）
    def get_sort_score(row):
        c_val = row['公司'] if row['公司'] in COMPANY_ORDER else '其他'
        c_idx = COMPANY_ORDER.index(c_val)
        t_idx = TOPIC_ORDER.index(row['话题']) if row['话题'] in TOPIC_ORDER else 99
        return (c_idx, t_idx)

    df['sort_score'] = df.apply(get_sort_score, axis=1)
    # 按日期倒序，公司和话题正序
    df_sorted = df.sort_values(by=['日期', 'sort_score'], ascending=[False, True])
    
    all_dates = df_sorted['日期'].unique().tolist()
    all_companies = [c for c in COMPANY_ORDER if c in df['公司'].unique() or c == '其他']

    # 4. 组织嵌套数据（用于 Tab 1 渲染）
    news_data = {}
    for date in all_dates:
        day_df = df_sorted[df_sorted['日期'] == date]
        news_data[date] = {}
        for company in COMPANY_ORDER:
            if company == '其他':
                comp_df = day_df[~day_df['公司'].isin(COMPANY_ORDER[:-1])]
            else:
                comp_df = day_df[day_df['公司'] == company]
            
            if not comp_df.empty:
                news_data[date][company] = comp_df.to_dict('records')

    # 5. 准备全量 JSON 数据（用于 Tab 2 筛选）
    json_data = json.dumps(df.to_dict('records'), ensure_ascii=False)

    # 6. HTML 模板
    template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI 行业分析看板</title>
        <style>
            :root { --primary: #1a73e8; --bg: #f8f9fa; --card-bg: #ffffff; --text: #202124; --secondary-text: #5f6368; }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.6; }
            .container { max-width: 900px; margin: auto; padding: 20px; }
            
            /* Header & Tabs */
            header { text-align: center; margin-bottom: 30px; }
            .tabs { display: flex; justify-content: center; gap: 30px; border-bottom: 1px solid #ddd; margin-bottom: 25px; }
            .tab-btn { padding: 12px 24px; cursor: pointer; border: none; background: none; font-size: 16px; font-weight: 500; color: var(--secondary-text); transition: 0.3s; }
            .tab-btn.active { color: var(--primary); border-bottom: 3px solid var(--primary); }
            .tab-content { display: none; animation: fadeIn 0.4s; }
            .tab-content.active { display: block; }

            /* Filters */
            .filter-section { background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; gap: 10px; flex-wrap: wrap; }
            .filter-item { flex: 1; min-width: 140px; }
            label { display: block; font-size: 12px; color: var(--secondary-text); margin-bottom: 5px; }
            select { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #ddd; background: #fff; outline: none; }

            /* Cards */
            .company-header { color: var(--primary); border-left: 5px solid var(--primary); padding-left: 15px; margin: 35px 0 15px; font-size: 22px; }
            .card { background: var(--card-bg); border: 1px solid #eee; padding: 20px; margin-bottom: 15px; border-radius: 12px; transition: transform 0.2s, box-shadow 0.2s; position: relative; }
            .card:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); border-color: var(--primary); }
            .tag-group { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
            .tag { font-size: 12px; padding: 3px 10px; border-radius: 6px; font-weight: bold; }
            .tag-topic { background: #e8f0fe; color: var(--primary); }
            .tag-date { background: #f1f3f4; color: var(--secondary-text); }
            .tag-region { background: #fef7e0; color: #f29900; }
            .title { font-size: 18px; font-weight: 600; color: #111; margin-bottom: 10px; display: block; }
            .content { font-size: 15px; color: #444; margin-bottom: 15px; }
            .footer { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: var(--secondary-text); border-top: 1px solid #f5f5f5; pt: 10px; padding-top: 12px; }
            .btn-link { color: var(--primary); text-decoration: none; font-weight: 600; border: 1px solid var(--primary); padding: 4px 12px; border-radius: 6px; transition: 0.2s; }
            .btn-link:hover { background: var(--primary); color: #fff; }

            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            @media (max-width: 600px) { .filter-item { flex: 100%; } }
        </style>
    </head>
    <body>
    <div class="container">
        <header>
            <h1>🤖 AI 行业分析看板</h1>
            <p style="color:var(--secondary-text)">每日自动更新 · 深度结构化分析</p>
        </header>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab(event, 'daily')">每日综述</button>
            <button class="tab-btn" onclick="switchTab(event, 'filter')">深度筛选</button>
        </div>

        <div id="daily" class="tab-content active">
            <div style="text-align: right; margin-bottom: 20px;">
                📅 切换日期：
                <select id="dateSelect" onchange="showDate(this.value)" style="width: auto; display: inline-block;">
                    {% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}
                </select>
            </div>
            {% for d, cos in news.items() %}
            <div id="group-{{d}}" class="day-group" style="display: {{ 'block' if loop.first else 'none' }}">
                {% for co, items in cos.items() %}
                    <h2 class="company-header">{{co}}</h2>
                    {% for it in items %}
                    <div class="card">
                        <div class="tag-group">
                            <span class="tag tag-topic">{{it['话题']}}</span>
                            <span class="tag tag-region">{{it['海外/国内']}}</span>
                        </div>
                        <span class="title">{{it['标题']}}</span>
                        <p class="content">{{it['核心内容']}}</p>
                        <div class="footer">
                            <span>来源：{{it['来源']}}</span>
                            <a href="{{it['链接']}}" class="btn-link" target="_blank">阅读原文 →</a>
                        </div>
                    </div>
                    {% endfor %}
                {% endfor %}
            </div>
            {% endfor %}
        </div>

        <div id="filter" class="tab-content">
            <div class="filter-section">
                <div class="filter-item">
                    <label>日期范围</label>
                    <select id="f-date"><option value="all">全部日期</option>{% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                </div>
                <div class="filter-item">
                    <label>地区</label>
                    <select id="f-region"><option value="all">全部地区</option><option value="海外">海外</option><option value="国内">国内</option></select>
                </div>
                <div class="filter-item">
                    <label>公司主体</label>
                    <select id="f-company"><option value="all">全部公司</option>{% for co in company_list %}<option value="{{co}}">{{co}}</option>{% endfor %}</select>
                </div>
                <div style="display: flex; align-items: flex-end;">
                    <button onclick="applyFilter()" style="background:var(--primary); color:white; border:none; padding:10px 25px; border-radius:8px; cursor:pointer; font-weight:bold;">搜索</button>
                </div>
            </div>
            <div id="filter-results"></div>
        </div>
    </div>

    <script>
        const rawData = {{ json_data | safe }};

        function switchTab(evt, tabId) {
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            evt.currentTarget.classList.add('active');
            document.getElementById(tabId).classList.add('active');
            if(tabId === 'filter') applyFilter();
        }

        function showDate(d) {
            document.querySelectorAll('.day-group').forEach(el => el.style.display = 'none');
            document.getElementById('group-' + d).style.display = 'block';
        }

        function applyFilter() {
            const d = document.getElementById('f-date').value;
            const r = document.getElementById('f-region').value;
            const c = document.getElementById('f-company').value;
            
            let filtered = rawData.filter(it => {
                return (d === 'all' || it['日期'] == d) &&
                       (r === 'all' || it['海外/国内'] == r) &&
                       (c === 'all' || it['公司'] == c);
            });

            const container = document.getElementById('filter-results');
            container.innerHTML = filtered.length ? '' : '<p style="text-align:center; color:#999; margin-top:50px;">未找到匹配的数据条目</p>';
            
            filtered.forEach(it => {
                container.innerHTML += `
                    <div class="card">
                        <div class="tag-group">
                            <span class="tag tag-topic">${it['话题']}</span>
                            <span class="tag tag-date">${it['日期']}</span>
                            <span class="tag tag-region">${it['海外/国内']}</span>
                        </div>
                        <span class="title">${it['标题']}</span>
                        <p class="content">${it['核心内容']}</p>
                        <div class="footer">
                            <span>公司：<b>${it['公司']}</b> | 来源：${it['来源']}</span>
                            <a href="${it['链接']}" class="btn-link" target="_blank">阅读原文 →</a>
                        </div>
                    </div>`;
            });
        }
    </script>
    </body>
    </html>
    """

    # 7. 渲染与输出
    html = Template(template_str).render(
        dates=all_dates, 
        news=news_data, 
        json_data=json_data, 
        company_list=COMPANY_ORDER
    )
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("看板生成成功：index.html")

if __name__ == "__main__":
    main()
