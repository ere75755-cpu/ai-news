import pandas as pd
from jinja2 import Template
import json

# 1. 基础配置
SHEET_URL = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
CORE_COMPANIES = ['OpenAI', 'Anthropic', 'Google', 'Meta', '字节跳动', '阿里巴巴', '腾讯', '百度']
DOMESTIC_MODELS = ['Kimi', 'MiniMax', '智谱']
TOPIC_ORDER = ['技术迭代', '产品动态', '商业动态', '春节活动', '数据洞察']
MY_DOMAIN = "www.aipulse.run"

def main():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        name_map = {'字节': '字节跳动', '阿里': '阿里巴巴', 'Baidu': '百度', 'minimax': 'MiniMax', '智谱AI': '智谱'}
        df['公司'] = df['公司'].replace(name_map)
        
        if '是否头条' in df.columns:
            df['是否头条'] = pd.to_numeric(df['是否头条'], errors='coerce').fillna(0).astype(int)
        else:
            df['是否头条'] = 0
        df = df.fillna("")
    except Exception as e:
        print(f"数据读取失败: {e}"); return

    all_unique_companies = sorted(df['公司'].unique().tolist())

    # 排序权重逻辑
    def get_sort_score(row):
        c_val = row['公司']
        if c_val in CORE_COMPANIES: c_idx = CORE_COMPANIES.index(c_val)
        elif c_val in DOMESTIC_MODELS: c_idx = len(CORE_COMPANIES)
        else: c_idx = len(CORE_COMPANIES) + 1
        t_idx = TOPIC_ORDER.index(row['话题']) if row['话题'] in TOPIC_ORDER else 99
        return (c_idx, t_idx)

    df['sort_score'] = df.apply(get_sort_score, axis=1)
    df_sorted = df.sort_values(by=['日期', 'sort_score'], ascending=[False, True])
    all_dates = df_sorted['日期'].unique().tolist()

    news_data_map = {}
    headlines_map = {}
    
    for date in all_dates:
        day_df = df_sorted[df_sorted['日期'] == date]
        headlines_map[date] = day_df[day_df['是否头条'] == 1].to_dict('records')
        news_data_map[date] = {}
        
        for company in CORE_COMPANIES:
            comp_df = day_df[day_df['公司'] == company]
            if not comp_df.empty: news_data_map[date][company] = comp_df.to_dict('records')
        
        domestic_df = day_df[day_df['公司'].isin(DOMESTIC_MODELS)].copy()
        if not domestic_df.empty:
            domestic_df['d_rank'] = domestic_df['公司'].apply(lambda x: DOMESTIC_MODELS.index(x))
            domestic_df['t_rank'] = domestic_df['话题'].apply(lambda x: TOPIC_ORDER.index(x) if x in TOPIC_ORDER else 99)
            domestic_df = domestic_df.sort_values(by=['d_rank', 't_rank'])
            news_data_map[date]['Kimi / MiniMax / 智谱'] = domestic_df.to_dict('records')
        
        other_df = day_df[~day_df['公司'].isin(CORE_COMPANIES + DOMESTIC_MODELS)]
        if not other_df.empty: news_data_map[date]['其他'] = other_df.to_dict('records')

    final_json = json.dumps(df.to_dict('records'), ensure_ascii=False)

    template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>全球 AI 核心动态内参</title>
        <style>
            :root { --primary: #1a73e8; --bg: #ffffff; --text: #202124; --border: #eeeeee; }
            body { font-family: -apple-system, "PingFang SC", sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.4; }
            .container { max-width: 780px; margin: auto; padding: 10px; }
            
            header h1 { text-align: center; font-size: 22px; margin: 15px 0 5px; font-weight: 800; border-bottom: 3px solid var(--primary); padding-bottom: 5px; }
            .time-label { text-align: center; font-size: 11px; color: #777; margin-bottom: 15px; background: #f8f9fa; padding: 4px; border-radius: 2px; }

            .tabs-nav { display: flex; border: 1px solid #ddd; margin-bottom: 15px; background: #fff; border-radius: 4px; overflow: hidden; }
            .tab-btn { padding: 8px; cursor: pointer; border: none; background: none; font-size: 13px; font-weight: bold; color: #5f6368; flex: 1; }
            .tab-btn.active { color: #fff; background: var(--primary); }
            .tab-pane { display: none; }
            .tab-pane.active { display: block; }

            /* 头条部分 */
            .headline-section { background: #fff; padding: 12px; border: 1px solid var(--primary); margin-bottom: 20px; position: relative; }
            .headline-label { background: #d93025; color: #fff; padding: 2px 6px; font-size: 10px; font-weight: bold; position: absolute; top: -9px; left: 12px; }
            .hl-item { border-bottom: 1px dashed #eee; padding: 6px 0; }
            .hl-item:last-child { border-bottom: none; }
            .hl-title { font-size: 15px; font-weight: bold; color: var(--primary); text-decoration: none; display: block; }

            /* 公司标题吸顶 */
            .company-section { margin-top: 20px; }
            .co-title { 
                position: sticky; top: 0; z-index: 100; 
                background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(4px);
                padding: 6px 0 6px 10px; margin: 0;
                color: var(--primary); border-left: 4px solid var(--primary); font-size: 16px; font-weight: 800; 
                border-bottom: 1px solid #f0f0f0;
            }
            
            /* 新闻列表 - 无边框样式 */
            .news-item { 
                padding: 10px 5px; 
                border-bottom: 1px solid var(--border); 
                cursor: pointer; 
                transition: background 0.2s;
            }
            .news-item:hover { background: #fafafa; }
            .news-item:last-child { border-bottom: none; }
            
            .tag-group { margin-bottom: 4px; display: flex; gap: 4px; align-items: center; }
            .tag { font-size: 9px; padding: 1px 5px; font-weight: bold; background: #f1f3f4; color: #5f6368; border-radius: 2px; }
            .tag-important { background: #e8f0fe; color: var(--primary); }
            .tag-domestic { background: #fff7e0; color: #f29900; }
            
            .title-row { font-size: 14px; font-weight: 600; color: #222; display: flex; justify-content: space-between; align-items: center; }
            .title-row::after { content: '+'; font-size: 14px; color: #ccc; font-weight: normal; }
            .news-item.open .title-row::after { content: '−'; color: var(--primary); }
            
            .content-box { display: none; padding: 8px 0; font-size: 12.5px; color: #444; line-height: 1.6; animation: fadeIn 0.2s; }
            .news-item.open .content-box { display: block; }
            
            .footer { font-size: 11px; color: #999; display: flex; justify-content: space-between; margin-top: 8px; }
            .link-btn { color: var(--primary); text-decoration: none; font-weight: bold; }

            @media (max-width: 600px) {
                header h1 { font-size: 19px; }
                .co-title { font-size: 15px; }
                .title-row { font-size: 13.5px; }
                .content-box { font-size: 12px; }
            }
        </style>
    </head>
    <body>
    <div class="container">
        <header><h1>全球 AI 产业核心动态内参</h1></header>
        <div class="tabs-nav">
            <div class="tab-btn active" onclick="openTab(event, 'daily')">每日综述</div>
            <div class="tab-btn" onclick="openTab(event, 'filter')">历史检索</div>
        </div>

        <div id="daily" class="tab-pane active">
            <div style="text-align: right; margin-bottom:10px;">
                <select id="dateSelect" onchange="changeDate(this.value)" style="font-size:11px; border:1px solid #ddd; padding:2px;">
                    {% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}
                </select>
            </div>
            
            {% for d in dates %}
            <div id="date-{{d}}" class="date-group" style="display: {{ 'block' if loop.first else 'none' }}">
                <div class="time-label">数据周期加载中...</div>
                
                {% if headlines_data[d] %}
                <div class="headline-section">
                    <span class="headline-label">今日头条</span>
                    {% for hl in headlines_data[d] %}
                    <div class="hl-item">
                        <div class="tag-group">
                            <span class="tag tag-important">{{hl['话题']}}</span>
                            <span class="tag">{{hl['公司']}}</span>
                        </div>
                        <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a>
                        <div class="footer" style="margin-top:4px;"><span>来源: {{hl['来源']}}</span><a href="{{hl['链接']}}" class="link-btn" target="_blank">原文 →</a></div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                {% for co, items in news_data[d].items() %}
                <div class="company-section">
                    <h2 class="co-title">{{co}}</h2>
                    {% for it in items %}
                    <div class="news-item" onclick="this.classList.toggle('open')">
                        <div class="tag-group">
                            <span class="tag tag-important">{{it['话题']}}</span>
                            {% if co == 'Kimi / MiniMax / 智谱' or co == '其他' %}
                            <span class="tag tag-domestic">{{it['公司']}}</span>
                            {% endif %}
                        </div>
                        <span class="title-row">{{it['标题']}}</span>
                        <div class="content-box">
                            {{it['核心内容']}}
                            <div class="footer">
                                <span>来源: {{it['来源']}}</span>
                                <a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">查看原文</a>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </div>

        <div id="filter" class="tab-pane">
            <div style="background:#fff; padding:10px; border:1px solid #ddd; display:flex; gap:8px; margin-bottom:15px; position: sticky; top: 0; z-index: 101;">
                <select id="f-date" style="flex:1; font-size:11px;"><option value="all">全时间段</option>{% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                <select id="f-co" style="flex:1; font-size:11px;"><option value="all">所有公司</option>{% for c in all_companies %}<option value="{{c}}">{{c}}</option>{% endfor %}</select>
                <button onclick="doSearch()" style="background:var(--primary); color:white; border:none; padding:4px 12px; font-weight:bold; font-size:11px; border-radius:2px;">搜索</button>
            </div>
            <div id="results"></div>
        </div>
    </div>

    <script>
        const rawData = {{ json_data | safe }};
        function openTab(evt, id) {
            document.querySelectorAll('.tab-pane, .tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            evt.currentTarget.classList.add('active');
            if(id === 'filter') doSearch();
        }
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
            if(labelEl) labelEl.innerText = "数据监测周期：" + label;
        }
        window.onload = () => { 
            const select = document.getElementById('dateSelect');
            if(select) changeDate(select.value);
        };
        function doSearch() {
            const d = document.getElementById('f-date').value, c = document.getElementById('f-co').value;
            const filtered = rawData.filter(it => (d === 'all' || it['日期'] == d) && (c === 'all' || it['公司'] == c));
            const resDiv = document.getElementById('results');
            resDiv.innerHTML = filtered.length ? '' : '<p style="font-size:11px; text-align:center;">无结果</p>';
            filtered.forEach(it => {
                const item = document.createElement('div');
                item.className = 'news-item';
                item.onclick = () => item.classList.toggle('open');
                item.innerHTML = `<div class="tag-group"><span class="tag tag-important">${it['话题']}</span><span class="tag">${it['日期']}</span><span class="tag">${it['公司']}</span></div><span class="title-row">${it['标题']}</span><div class="content-box">${it['核心内容']}<div class="footer"><span>来源: ${it['来源']}</span><a href="${it['链接']}" class="link-btn" target="_blank" onclick="event.stopPropagation();">查看原文</a></div></div>`;
                resDiv.appendChild(item);
            });
        }
        function fadeIn(el) { el.style.opacity = 0; (function fade() { var val = parseFloat(el.style.opacity); if (!((val += .1) > 1)) { el.style.opacity = val; requestAnimationFrame(fade); } })(); }
    </script>
    </body>
    </html>
    """

    # 渲染
    html = Template(template_str).render(
        dates=all_dates, 
        news_data=news_data_map, 
        headlines_data=headlines_map, 
        json_data=final_json, 
        all_companies=all_unique_companies
    )
    
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)
    with open("CNAME", "w") as f: f.write(MY_DOMAIN)

if __name__ == "__main__":
    main()
