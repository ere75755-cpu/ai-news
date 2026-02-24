import pandas as pd
from jinja2 import Template
import json
from datetime import datetime

# 1. 基础配置
SHEET_URL = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
# 正式定义的 8 家核心展示公司
CORE_COMPANIES = ['OpenAI', 'Anthropic', 'Google', 'Meta', '字节跳动', '阿里巴巴', '腾讯', '百度']
TOPIC_ORDER = ['技术迭代', '产品动态', '商业动态', '春节活动', '数据洞察']
MY_DOMAIN = "www.aipulse.run"

def main():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        
        # 兼容性清洗：确保表格中的简称能正确匹配到核心公司列表
        name_map = {'字节': '字节跳动', '阿里': '阿里巴巴', 'Baidu': '百度'}
        df['公司'] = df['公司'].replace(name_map)
        
        if '是否头条' in df.columns:
            df['是否头条'] = pd.to_numeric(df['是否头条'], errors='coerce').fillna(0).astype(int)
        df = df.fillna("")
    except Exception as e:
        print(f"Error: {e}"); return

    all_unique_companies = sorted(df['公司'].unique().tolist())

    # 排序权重逻辑
    def get_sort_score(row):
        c_val = row['公司']
        c_idx = CORE_COMPANIES.index(c_val) if c_val in CORE_COMPANIES else len(CORE_COMPANIES)
        t_val = row['话题']
        t_idx = TOPIC_ORDER.index(t_val) if t_val in TOPIC_ORDER else 99
        return (c_idx, t_idx)

    df['sort'] = df.apply(get_sort_score, axis=1)
    df_sorted = df.sort_values(by=['日期', 'sort'], ascending=[False, True])
    all_dates = df_sorted['日期'].unique().tolist()

    # 组织渲染数据
    news_data = {}; headlines = {}
    for d in all_dates:
        day_df = df_sorted[df_sorted['日期'] == d]
        headlines[d] = day_df[day_df['是否头条'] == 1].to_dict('records')
        news_data[d] = {}
        for co in CORE_COMPANIES:
            comp_df = day_df[day_df['公司'] == co]
            if not comp_df.empty: news_data[d][co] = comp_df.to_dict('records')
        other_df = day_df[~day_df['公司'].isin(CORE_COMPANIES)]
        if not other_df.empty: news_data[d]['其他'] = other_df.to_dict('records')

    template_str = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>全球 AI 产业核心动态内参</title>
    <style>
        :root { --primary: #1a73e8; --bg: #f8f9fa; --text: #202124; --border: #e0e0e0; }
        body { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); margin: 0; }
        .container { max-width: 900px; margin: auto; padding: 20px; }
        header h1 { text-align: center; font-size: 34px; margin: 30px 0 10px; font-weight: 800; color: #111; border-bottom: 4px solid #111; display: inline-block; width: 100%; padding-bottom: 10px; }
        
        .tabs-nav { display: flex; border: 1px solid var(--border); margin-bottom: 25px; background: #fff; border-radius: 4px; overflow: hidden; }
        .tab-btn { padding: 15px; cursor: pointer; border: none; background: none; font-size: 16px; font-weight: bold; color: #5f6368; flex: 1; transition: 0.2s; }
        .tab-btn.active { color: #fff; background: #333; }
        .tab-pane { display: none; } .tab-pane.active { display: block; }
        
        .time-label { text-align: center; font-size: 14px; color: #666; margin-bottom: 30px; font-style: italic; background: #eee; padding: 5px; border-radius: 4px; }

        /* 头条展示区 */
        .headline-section { background: #fff; padding: 25px; border: 1px solid #111; margin-bottom: 40px; position: relative; }
        .headline-label { background: #d93025; color: #fff; padding: 4px 12px; font-size: 12px; font-weight: bold; position: absolute; top: -12px; left: 20px; }
        .hl-title { font-size: 22px; font-weight: bold; color: #111; text-decoration: none; display: block; margin: 15px 0 10px; }
        .hl-content { font-size: 15px; color: #444; line-height: 1.7; }

        /* 分公司标题 - 强化样式 */
        .co-title { color: #111; border-left: 8px solid #333; padding-left: 15px; margin: 50px 0 20px; font-size: 28px; font-weight: 900; text-transform: uppercase; }
        
        /* 手风琴新闻卡片 */
        .card { background: #fff; border: 1px solid var(--border); padding: 20px; margin-bottom: 15px; border-radius: 2px; cursor: pointer; position: relative; }
        .card:hover { border-color: #333; background: #fafafa; }
        .tag-group { margin-bottom: 10px; }
        .tag { font-size: 11px; padding: 2px 8px; font-weight: bold; margin-right: 6px; background: #f1f3f4; color: #5f6368; border: 1px solid #ddd; }
        .tag-important { background: #e8f0fe; color: var(--primary); border-color: #c2d7fa; }
        
        .title-row { font-size: 18px; font-weight: 700; color: #222; display: flex; justify-content: space-between; align-items: flex-start; line-height: 1.4; }
        .title-row::after { content: '+'; font-size: 20px; color: #999; margin-left: 10px; transition: 0.3s; }
        .card.open .title-row::after { content: '-'; transform: rotate(180deg); color: #333; }
        
        .content-box { display: none; padding-top: 20px; margin-top: 15px; border-top: 1px dashed #eee; color: #444; font-size: 15px; line-height: 1.8; animation: slideDown 0.2s ease-out; }
        .card.open .content-box { display: block; }
        
        @keyframes slideDown { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
        .footer { font-size: 13px; color: #888; display: flex; justify-content: space-between; margin-top: 20px; }
        .link-btn { color: var(--primary); text-decoration: none; font-weight: bold; }
    </style></head>
    <body><div class="container">
        <header><h1>全球 AI 产业核心动态内参</h1></header>
        <div class="tabs-nav"><div class="tab-btn active" onclick="openTab(event, 'daily')">每日综述</div><div class="tab-btn" onclick="openTab(event, 'filter')">历史检索</div></div>
        
        <div id="daily" class="tab-pane active">
            <div style="text-align:right; margin-bottom:20px;">
                <label style="font-weight:bold;">报告日期：</label>
                <select id="dateSelect" onchange="changeDate(this.value)" style="padding:5px 10px; border:1px solid #333; font-weight:bold;">
                    {% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}
                </select>
            </div>
            
            {% for d in dates %}
            <div id="date-{{d}}" class="date-group" style="display: {{ 'block' if loop.first else 'none' }}">
                <div class="time-label" id="time-label-{{d}}">数据周期：加载中...</div>
                
                {% if headlines_data[d] %}<div class="headline-section"><span class="headline-label">战略核心提要</span>
                {% for hl in headlines_data[d] %}<div class="hl-item"><a href="{{hl['链接']}}" class="hl-title" target="_blank">{{hl['标题']}}</a><p class="hl-content">{{hl['核心内容']}}</p></div>{% endfor %}</div>{% endif %}
                
                {% for co, items in news_data[d].items() %}<h2 class="co-title">{{co}}</h2>
                {% for it in items %}
                <div class="card" onclick="this.classList.toggle('open')">
                    <div class="tag-group">
                        <span class="tag tag-important">{{it['话题']}}</span>
                        {% if co == '其他' %}<span class="tag">来源：{{it['公司']}}</span>{% endif %}
                    </div>
                    <span class="title-row">{{it['标题']}}</span>
                    <div class="content-box">
                        {{it['核心内容']}}
                        <div class="footer"><span>发布来源: {{it['来源']}}</span><a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文调查 →</a></div>
                    </div>
                </div>{% endfor %}{% endfor %}
            </div>{% endfor %}
        </div>
        
        <div id="filter" class="tab-pane">
            <div style="background:#fff;padding:25px;border:1px solid #ddd;display:flex;gap:15px;margin-bottom:25px;">
                <div style="flex:1;"><label style="display:block;font-size:12px;margin-bottom:5px;">发布日期</label><select id="f-date" style="width:100%;padding:8px;"><option value="all">全时间段</option>{% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}</select></div>
                <div style="flex:1;"><label style="display:block;font-size:12px;margin-bottom:5px;">涉及公司</label><select id="f-co" style="width:100%;padding:8px;"><option value="all">全公司主体</option>{% for c in all_companies %}<option value="{{c}}">{{c}}</option>{% endfor %}</select></div>
                <div style="display:flex;align-items:flex-end;"><button onclick="doSearch()" style="background:#333;color:white;border:none;padding:10px 30px;cursor:pointer;font-weight:bold;">开始检索</button></div>
            </div><div id="results"></div>
        </div>
    </div>
    <script>
        const rawData = {{ json_data | safe }};
        function openTab(evt, id) { document.querySelectorAll('.tab-pane, .tab-btn').forEach(el => el.classList.remove('active')); document.getElementById(id).classList.add('active'); evt.currentTarget.classList.add('active'); if(id === 'filter') doSearch(); }
        
        function changeDate(d) { 
            document.querySelectorAll('.date-group').forEach(g => g.style.display = 'none'); 
            const target = document.getElementById('date-' + d);
            if(target) { target.style.display = 'block'; updateTimeLabel(d); }
        }

        function updateTimeLabel(d) {
            const current = new Date(d);
            const prev = new Date(current);
            prev.setDate(current.getDate() - 1);
            const label = `${prev.getFullYear()}/${prev.getMonth()+1}/${prev.getDate()} 17:00 至 ${current.getFullYear()}/${current.getMonth()+1}/${current.getDate()} 17:00`;
            const labelEl = document.querySelector('#date-' + d.replace(/\//g, '\\\\/') + ' .time-label');
            if(labelEl) labelEl.innerText = "本期监测数据周期：" + label;
        }

        window.onload = () => { if(document.getElementById('dateSelect')) updateTimeLabel(document.getElementById('dateSelect').value); };

        function doSearch() {
            const d = document.getElementById('f-date').value, c = document.getElementById('f-co').value;
            const filtered = rawData.filter(it => (d === 'all' || it['日期'] == d) && (c === 'all' || it['公司'] == c));
            const resDiv = document.getElementById('results'); resDiv.innerHTML = filtered.length ? '' : '<p>未检索到相关情报</p>';
            filtered.forEach(it => { resDiv.innerHTML += `<div class="card open" style="cursor:default;border-left:4px solid #333;"><div class="tag-group"><span class="tag tag-important">${it['话题']}</span><span class="tag">${it['日期']}</span></div><span class="title-row" style="pointer-events:none">${it['标题']}</span><div class="content-box" style="display:block">${it['核心内容']}</div></div>`; });
        }
    </script></body></html>
    """

    html = Template(template_str).render(dates=all_dates, news_data=news_data, headlines_data=headlines, json_data=json_data, all_companies=all_unique_companies)
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)
    with open("CNAME", "w") as f: f.write(MY_DOMAIN)

if __name__ == "__main__": main()
