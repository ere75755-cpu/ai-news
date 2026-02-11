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
        # 处理“是否头条”字段
        if '是否头条' in df.columns:
            df['是否头条'] = pd.to_numeric(df['是否头条'], errors='coerce').fillna(0).astype(int)
        else:
            df['是否头条'] = 0
        df = df.fillna("")
    except Exception as e:
        print(f"数据读取失败: {e}")
        return

    # 3. 排序逻辑
    def get_sort_score(row):
        c_val = row['公司'] if row['公司'] in COMPANY_ORDER else '其他'
        c_idx = COMPANY_ORDER.index(c_val)
        t_idx = TOPIC_ORDER.index(row['话题']) if row['话题'] in TOPIC_ORDER else 99
        return (c_idx, t_idx)

    df['sort_score'] = df.apply(get_sort_score, axis=1)
    df_sorted = df.sort_values(by=['日期', 'sort_score'], ascending=[False, True])
    
    all_dates = df_sorted['日期'].unique().tolist()

    # 4. 组织展示数据 (今日头条 + 按公司汇总)
    news_data_map = {}
    headlines_map = {}
    for date in all_dates:
        day_df = df_sorted[df_sorted['日期'] == date]
        
        # 提取该日期的今日头条 (1为头条)
        headlines_map[date] = day_df[day_df['是否头条'] == 1].to_dict('records')

        news_data_map[date] = {}
        for company in COMPANY_ORDER:
            if company == '其他':
                comp_df = day_df[~day_df['公司'].isin(COMPANY_ORDER[:-1])]
            else:
                comp_df = day_df[day_df['公司'] == company]
            if not comp_df.empty:
                news_data_map[date][company] = comp_df.to_dict('records')

    # 5. 全量 JSON
    json_data = json.dumps(df.to_dict('records'), ensure_ascii=False)

    template_str = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI News速览</title>
        <style>
            :root { --primary: #1a73e8; --bg: #f8f9fa; --text: #202124; --headline-bg: #1a1c1e; }
            body { font-family: sans-serif; background: var(--bg); color: var(--text); margin: 0; }
            .container { max-width: 900px; margin: auto; padding: 20px; }
            
            /* Tabs */
            .tabs-nav { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 20px; background: #fff; border-radius: 8px 8px 0 0; }
            .tab-btn { padding: 15px 25px; cursor: pointer; border: none; background: none; font-size: 16px; font-weight: bold; color: #5f6368; flex: 1; transition: 0.3s; }
            .tab-btn.active { color: var(--primary); border-bottom: 3px solid var(--primary); background: #f1f3f4; }
            
            .tab-pane { display: none; padding: 10px; }
            .tab-pane.active { display: block; }

            /* Headline Section */
            .headline-section { background: var(--headline-bg); color: #fff; padding: 25px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
            .headline-label { background: #f4b400; color: #000; padding: 3px 10px; font-size: 11px; font-weight: bold; border-radius: 4px; display: inline-block; margin-bottom: 20px; }
            .hl-item { border-bottom: 1px solid #3c4043; padding: 15px 0; }
            .hl-item:last-child { border-bottom: none; }
            .hl-title { font-size: 20px; font-weight: bold; color: #fff; text-decoration: none; display: block; margin-bottom: 8px; }
            .hl-content { color: #bdc1c6; font-size: 15px; margin-bottom: 12px; }

            /* Cards */
            .company-section { margin-top: 30px; }
            .co-title { color: var(--primary); border-left: 5px solid var(--primary); padding-left: 10px; margin-bottom: 15px; font-size: 22px; }
            .card { background: #fff; border: 1px solid #eee; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 5px; }
            .tag-topic { background: #e8f0fe; color: var(--primary); }
            .tag-region { background: #fef7e0; color: #f29900; }
            .title { font-size: 18px; font-weight: bold; display: block; margin: 10px 0; }
            .footer { font-size: 13px; color: #888; display: flex; justify-content: space-between; margin-top: 15px; border-top: 1px solid #f9f9f9; padding-top: 12px; }
            a { color: var(--primary); text-decoration: none; font-weight: 500; }
        </style>
    </head>
    <body>
    <div class="container">
        <header style="text-align:center; margin-bottom:20px;"><h1>AI News速览</h1></header>
        
        <div class="tabs-nav">
            <div class="tab-btn active" onclick="openTab(event, 'daily-view')">每日综述</div>
            <div class="tab-btn" onclick="openTab(event, 'filter-view')">深度筛选</div>
        </div>

        <div id="daily-view" class="tab-pane active">
            <div style="text-align: right; margin-bottom:20px;">
                📅 切换日期: <select onchange="changeDate(this.value)">
                    {% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}
                </select>
            </div>
            
            {% for d in dates %}
            <div id="date-{{d}}" class="date-group" style="display: {{ 'block' if loop.first else 'none' }}">
                
                {% if headlines_data[d] %}
                <div class="headline-section">
                    <span class="headline-label">今日头条 TOP NEWS</span>
                    {% for hl in headlines_data[d] %}
                    <div class="hl-item">
                        <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a>
                        <p class="hl-content">{{hl['核心内容']}}</p>
                        <div style="font-size:12px; color:#888;">主体: {{hl['公司']}} | 来源: {{hl['来源']}}</div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                {% for co, items in news_data[d].items() %}
                <div class="company-section">
                    <h3 class="co-title">{{co}}</h3>
                    {% for it in items %}
                    <div class="card">
                        <span class="tag tag-topic">{{it['话题']}}</span>
                        <span class="tag tag-region">{{it['海外/国内']}}</span>
                        <span class="title">{{it['标题']}}</span>
                        <p style="font-size:15px; color:#444;">{{it['核心内容']}}</p>
                        <div class="footer"><span>来源: {{it['来源']}}</span><a href="{{it['链接']}}" target="_blank">阅读原文 →</a></div>
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </div>

        <div id="filter-view" class="tab-pane">
            <div style="background:#fff; padding:20px; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1); display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px;">
                <select id="f-date" style="flex:1; min-width:120px; padding:8px; border-radius:6px; border:1px solid #ddd;"><option value="all">所有日期</option>{% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                <select id="f-region" style="flex:1; min-width:120px; padding:8px; border-radius:6px; border:1px solid #ddd;"><option value="all">所有地区</option><option value="海外">海外</option><option value="国内">国内</option></select>
                <select id="f-co" style="flex:1; min-width:120px; padding:8px; border-radius:6px; border:1px solid #ddd;"><option value="all">所有公司</option>{% for c in company_list %}<option value="{{c}}">{{c}}</option>{% endfor %}</select>
                <button onclick="doSearch()" style="background:var(--primary); color:white; border:none; padding:8px 25px; border-radius:6px; cursor:pointer; font-weight:bold;">搜索</button>
            </div>
            <div id="results"></div>
        </div>
    </div>

    <script>
        const rawData = {{ json_data | safe }};

        function openTab(evt, tabId) {
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            evt.currentTarget.classList.add('active');
            if(tabId === 'filter-view') doSearch();
        }

        function changeDate(d) {
            document.querySelectorAll('.date-group').forEach(g => g.style.display = 'none');
            const target = document.getElementById('date-' + d);
            if(target) target.style.display = 'block';
        }

        function doSearch() {
            const d = document.getElementById('f-date').value;
            const r = document.getElementById('f-region').value;
            const c = document.getElementById('f-co').value;
            
            const filtered = rawData.filter(it => 
                (d === 'all' || it['日期'] == d) &&
                (r === 'all' || it['海外/国内'] == r) &&
                (c === 'all' || it['公司'] == c)
            );

            const resDiv = document.getElementById('results');
            resDiv.innerHTML = filtered.length ? '' : '<p style="text-align:center;color:#999;margin-top:50px;">无匹配结果</p>';
            
            filtered.forEach(it => {
                resDiv.innerHTML += `
                    <div class="card">
                        <span class="tag tag-topic">${it['话题']}</span>
                        <span class="tag tag-region">${it['海外/国内']}</span>
                        <span class="tag" style="background:#eee">${it['日期']}</span>
                        <span class="title">${it['标题']}</span>
                        <p style="font-size:15px;color:#444;">${it['核心内容']}</p>
                        <div class="footer"><span>公司: ${it['公司']} | 来源: ${it['来源']}</span><a href="${it['链接']}" target="_blank">原文 →</a></div>
                    </div>`;
            });
        }
    </script>
    </body>
    </html>
    """

    # 注意：这里的变量名必须与 HTML 模板中的 {% for %} 保持一致
    html = Template(template_str).render(
        dates=all_dates, 
        news_data=news_data_map, 
        headlines_data=headlines_map,
        json_data=json_data, 
        company_list=COMPANY_ORDER
    )
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    main()
