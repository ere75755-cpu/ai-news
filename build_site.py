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
    # 2. 读取并处理数据
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

    # 中英文混合排序逻辑（GBK 编码技巧）
    all_unique_companies = sorted(df['公司'].unique().tolist(), 
                                  key=lambda x: x.encode('gbk') if isinstance(x, str) else x)

    def get_sort_score(row):
        c_val = row['公司']
        if c_val in CORE_COMPANIES: c_idx = CORE_COMPANIES.index(c_val)
        elif c_val in DOMESTIC_MODELS: c_idx = len(CORE_COMPANIES)
        else: c_idx = len(CORE_COMPANIES) + 1
        t_val = row['话题']
        t_idx = TOPIC_ORDER.index(t_val) if t_val in TOPIC_ORDER else 99
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
        if not other_df.empty: news_data_map[date]['行业内其余新闻'] = other_df.to_dict('records')

    final_json_str = json.dumps(df.to_dict('records'), ensure_ascii=False)

    # 4. HTML 模板
    template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>全球 AI 核心动态内参</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700&display=swap" rel="stylesheet">
        <style>
            :root { --primary: #1a73e8; --header-bg: #1a365d; --bg: #ffffff; --text: #2c3e50; --border: #eeeeee; --sub-bg: #f8fafc; }
            body { 
                font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; 
                background: var(--bg); color: var(--text); margin: 0; line-height: 1.5; 
                -webkit-font-smoothing: antialiased;
            }
            .container { max-width: 780px; margin: auto; padding: 10px; overflow: visible; }
            header h1 { font-family: 'Noto Serif SC', serif; text-align: center; font-size: 20px; margin: 15px 0 10px; color: #1a1a1a; }
            
            .control-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 0 4px 6px 4px; border-bottom: 1px solid #f0f0f0; }
            .time-label { font-size: 10px; color: #999; white-space: nowrap; }
            .date-picker { font-size: 10px; color: var(--primary); font-weight: bold; border: 1px solid #ddd; border-radius: 2px; padding: 1px 2px; background: transparent; }

            .tabs-nav { display: flex; justify-content: center; margin-bottom: 15px; border-bottom: 1px solid #eee; }
            .tab-btn { padding: 8px 16px; cursor: pointer; border: none; background: none; font-size: 13.5px; font-weight: 600; color: #999; position: relative; }
            .tab-btn.active { color: var(--primary) !important; }
            .tab-btn.active::after { content: ''; position: absolute; bottom: -1px; left: 0; width: 100%; height: 2px; background: var(--primary); }

            .tab-content { display: none; overflow: visible; }
            .tab-content.active { display: block; }

            /* 普通公司名吸顶样式 */
            .sticky-title { 
                position: sticky; top: 0; z-index: 1000; 
                background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(8px);
                padding: 8px 0 8px 10px; margin: 0;
                color: var(--primary); border-left: 4px solid var(--primary); 
                font-size: 15px; font-weight: 700; border-bottom: 1px solid #f0f0f0;
                font-family: 'Noto Serif SC', serif;
            }

            /* 今日头条专用吸顶：深色背景，白色文字，居中 */
            .headline-title { 
                position: sticky; top: 0; z-index: 1001; 
                background: var(--header-bg); 
                padding: 10px 0; margin: 0;
                color: #ffffff; border-left: none; text-align: center;
                font-size: 16px; font-weight: 700; letter-spacing: 2px;
                border-bottom: 1px solid var(--header-bg);
                font-family: 'Noto Serif SC', serif;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }

            .headline-section { margin-bottom: 30px; background: var(--sub-bg); padding: 1px 0 10px 0; border-radius: 4px; }
            .hl-item { padding: 12px; border-bottom: 1px solid #eef2f6; }
            .hl-item:last-child { border-bottom: none; }
            .hl-title { font-size: 15px; font-weight: 700; color: var(--primary); text-decoration: none; display: block; margin-bottom: 4px; font-family: 'Noto Serif SC', serif; line-height: 1.4; }
            .hl-content { font-size: 12px; color: #444; line-height: 1.6; margin: 6px 0; text-align: justify; }

            .company-section { margin-top: 20px; }
            .news-item { padding: 10px 4px; border-bottom: 1px solid var(--border); cursor: pointer; }
            .news-item:last-child { border-bottom: none; }
            
            .tag-group { margin-bottom: 4px; display: flex; gap: 6px; align-items: center; }
            .tag { font-size: 9px; padding: 1px 5px; font-weight: 600; background: #f1f3f4; color: #888; border-radius: 2px; }
            .tag-important { background: #e8f0fe; color: var(--primary); }
            .tag-domestic { background: #fff7e0; color: #f39c12; }
            
            .title-row { font-size: 14px; font-weight: 600; color: #2c3e50; display: flex; justify-content: space-between; align-items: center; }
            .title-row::after { content: '+'; font-size: 14px; color: #ccc; }
            .news-item.open .title-row::after { content: '−'; color: var(--primary); }
            
            .content-box { display: none; padding: 8px 0; font-size: 12px; color: #444; line-height: 1.7; text-align: justify; }
            .news-item.open .content-box { display: block; }
            
            .footer { font-size: 10px; color: #aaa; display: flex; justify-content: space-between; margin-top: 8px; }
            .link-btn { color: var(--primary); text-decoration: none; font-weight: 700; }

            @media (max-width: 600px) {
                header h1 { font-size: 18px; }
                .hl-title, .sticky-title, .headline-title { font-size: 14.5px; }
            }
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
                <div id="current-time-label" class="time-label">监测：加载中...</div>
                <div style="display: flex; align-items: center;">
                    <span style="font-size:10px; color:#999;">日期：</span>
                    <select id="dateSelect" class="date-picker" onchange="changeDate(this.value)">
                        {% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}
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
                        <div class="footer" style="border:none; padding:0; margin-top:4px;">
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
                            <span class="tag tag-important">{{it['话题']}}</span>
                            {% if co == 'Kimi / MiniMax / 智谱' or co == '行业内其余新闻' %}
                            <span class="tag tag-domestic">{{it['公司']}}</span>
                            {% endif %}
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
        </div>

        <div id="panel-filter" class="tab-content">
            <div style="padding:10px 0; display:flex; gap:6px; margin-bottom:15px; position: sticky; top: 0; z-index: 101; background: #fff; border-bottom: 1px solid #eee;">
                <select id="f-date" style="flex:1; font-size:11px; padding:4px; border:1px solid #eee;"><option value="all">全时间段</option>{% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                <select id="f-co" style="flex:1; font-size:11px; padding:4px; border:1px solid #eee;"><option value="all">所有公司/模型</option>{% for c in all_companies %}<option value="{{c}}">{{c}}</option>{% endfor %}</select>
                <button onclick="doSearch()" style="background:var(--primary); color:white; border:none; padding:4px 12px; font-weight:bold; font-size:11px; border-radius:2px; cursor:pointer;">检索</button>
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
            if(id === 'filter') doSearch();
        }

        function changeDate(d) {
            document.querySelectorAll('.date-container').forEach(g => g.style.display = 'none');
            const target = document.getElementById('date-group-' + d);
            if(target) { target.style.display = 'block'; updateTimeLabel(d); }
        }

        function updateTimeLabel(d) {
            const current = new Date(d);
            const prev = new Date(current);
            prev.setDate(current.getDate() - 1);
            const label = prev.getFullYear() + '/' + (prev.getMonth()+1) + '/' + prev.getDate() + ' 17:00 至 ' + d + ' 17:00';
            document.getElementById('current-time-label').innerText = "监测：" + label;
        }

        window.onload = () => { 
            const select = document.getElementById('dateSelect');
            if(select) changeDate(select.value);
        };

        function doSearch() {
            const d = document.getElementById('f-date').value, c = document.getElementById('f-co').value;
            const filtered = rawData.filter(it => (d === 'all' || it['日期'] == d) && (c === 'all' || it['公司'] == c));
            const resDiv = document.getElementById('results');
            resDiv.innerHTML = filtered.length ? '' : '<p style="text-align:center; padding:30px; font-size:11px; color:#999;">无匹配情报</p>';
            
            filtered.forEach(it => {
                const item = document.createElement('div');
                item.className = 'news-item';
                item.onclick = () => item.classList.toggle('open');
                item.innerHTML = `<div class="tag-group"><span class="tag tag-important">${it['话题']}</span><span class="tag">${it['日期']}</span><span class="tag">公司/模型：${it['公司']}</span></div><span class="title-row">${it['标题']}</span><div class="content-box">${it['核心内容']}<div class="footer"><span>来源: ${it['来源']}</span><a href="${it['链接']}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文</a></div></div>`;
                resDiv.appendChild(item);
            });
        }
    </script>
    </body>
    </html>
    """

    html = Template(template_str).render(dates=all_dates, news_data_map=news_data_map, headlines_map=headlines_map, final_json_str=final_json_str, all_companies=all_unique_companies)
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)
    with open("CNAME", "w") as f: f.write(MY_DOMAIN)

if __name__ == "__main__":
    main()
