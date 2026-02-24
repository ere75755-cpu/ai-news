import pandas as pd
from jinja2 import Template
import json

# 1. 基础配置
SHEET_URL = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
# 核心展示公司：增加百度，并确保字节跳动、阿里巴巴的命名对齐
CORE_COMPANIES = ['OpenAI', 'Anthropic', 'Google', 'Meta', '字节跳动', '阿里巴巴', '腾讯', '百度']
TOPIC_ORDER = ['技术迭代', '产品动态', '商业动态', '春节活动', '数据洞察']
MY_DOMAIN = "www.aipulse.run"

def main():
    # 2. 读取数据
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        
        # 兼容性清洗：将表格里的简称统一
        name_map = {'字节': '字节跳动', '阿里': '阿里巴巴', 'Baidu': '百度'}
        df['公司'] = df['公司'].replace(name_map)
        
        if '是否头条' in df.columns:
            df['是否头条'] = pd.to_numeric(df['是否头条'], errors='coerce').fillna(0).astype(int)
        else:
            df['是否头条'] = 0
        df = df.fillna("")
    except Exception as e:
        print(f"数据读取失败: {e}")
        return

    # 获取全量公司列表（用于深度筛选）
    all_unique_companies = sorted(df['公司'].unique().tolist())

    # 3. 排序逻辑
    def get_sort_score(row):
        c_val = row['公司']
        c_idx = CORE_COMPANIES.index(c_val) if c_val in CORE_COMPANIES else len(CORE_COMPANIES)
        t_val = row['话题']
        t_idx = TOPIC_ORDER.index(row['话题']) if row['话题'] in TOPIC_ORDER else 99
        return (c_idx, t_idx)

    df['sort_score'] = df.apply(get_sort_score, axis=1)
    df_sorted = df.sort_values(by=['日期', 'sort_score'], ascending=[False, True])
    all_dates = df_sorted['日期'].unique().tolist()

    # 4. 组织数据
    news_data_map = {}
    headlines_map = {}
    
    for date in all_dates:
        day_df = df_sorted[df_sorted['日期'] == date]
        # 提取头条
        headlines_map[date] = day_df[day_df['是否头条'] == 1].to_dict('records')

        news_data_map[date] = {}
        for company in CORE_COMPANIES:
            comp_df = day_df[day_df['公司'] == company]
            if not comp_df.empty:
                news_data_map[date][company] = comp_df.to_dict('records')
        
        other_df = day_df[~day_df['公司'].isin(CORE_COMPANIES)]
        if not other_df.empty:
            news_data_map[date]['其他'] = other_df.to_dict('records')

    # 定义数据用于 JS 搜索
    final_json = json.dumps(df.to_dict('records'), ensure_ascii=False)

    # 5. HTML 模板
    template_str = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>全球 AI 核心动态内参</title>
        <style>
            :root { --primary: #1a73e8; --bg: #f8f9fa; --text: #202124; --border: #e0e0e0; }
            body { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.6; }
            .container { max-width: 900px; margin: auto; padding: 20px; }
            
            header h1 { text-align: center; font-size: 34px; margin: 30px 0 10px; font-weight: 800; border-bottom: 4px solid var(--primary); padding-bottom: 10px; color: var(--text); }
            .time-label { text-align: center; font-size: 14px; color: #666; margin-bottom: 30px; background: #eee; padding: 6px; border-radius: 4px; }

            .tabs-nav { display: flex; border: 1px solid var(--border); margin-bottom: 25px; background: #fff; border-radius: 4px; overflow: hidden; }
            .tab-btn { padding: 15px; cursor: pointer; border: none; background: none; font-size: 16px; font-weight: bold; color: #5f6368; flex: 1; transition: 0.2s; }
            .tab-btn.active { color: #fff; background: var(--primary); }
            .tab-pane { display: none; }
            .tab-pane.active { display: block; }

            /* 头条部分样式 */
            .headline-section { background: #fff; padding: 25px; border: 1px solid var(--primary); margin-bottom: 40px; position: relative; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
            .headline-label { background: #d93025; color: #fff; padding: 4px 12px; font-size: 12px; font-weight: bold; position: absolute; top: -12px; left: 20px; }
            .hl-item { border-bottom: 1px dashed #eee; padding: 15px 0; }
            .hl-item:last-child { border-bottom: none; }
            .hl-title { font-size: 22px; font-weight: bold; color: var(--primary); text-decoration: none; display: block; margin-bottom: 8px; }
            .hl-title:hover { opacity: 0.8; }

            /* 公司标题吸顶 */
            .company-section { margin-top: 50px; }
            .co-title { 
                position: sticky; top: 0; z-index: 100; 
                background: rgba(248, 249, 250, 0.95); backdrop-filter: blur(5px);
                padding: 15px 0 15px 15px; margin: 0 0 20px 0;
                color: var(--primary); border-left: 8px solid var(--primary); font-size: 28px; font-weight: 900; 
                box-shadow: 0 2px 5px rgba(0,0,0,0.02);
            }
            
            /* 卡片样式 */
            .card { background: #fff; border: 1px solid var(--border); padding: 20px; margin-bottom: 15px; cursor: pointer; border-radius: 2px; transition: 0.2s; }
            .card:hover { border-color: var(--primary); }
            .tag-group { margin-bottom: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
            .tag { font-size: 11px; padding: 2px 8px; font-weight: bold; background: #f1f3f4; color: #5f6368; border: 1px solid #ddd; border-radius: 4px; }
            .tag-important { background: #e8f0fe; color: var(--primary); border-color: #c2d7fa; }
            
            .title-row { font-size: 18px; font-weight: 700; color: #222; display: flex; justify-content: space-between; align-items: center; }
            .title-row::after { content: '+'; font-size: 20px; color: #999; transition: 0.3s; }
            .card.open .title-row::after { content: '-'; transform: rotate(180deg); color: var(--primary); }
            
            .content-box { display: none; padding-top: 20px; margin-top: 15px; border-top: 1px dashed #eee; font-size: 15px; color: #444; animation: fadeIn 0.3s; }
            .card.open .content-box { display: block; }
            
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            .footer { font-size: 13px; color: #888; display: flex; justify-content: space-between; align-items: center; margin-top: 20px; border-top: 1px solid #f9f9f9; padding-top: 10px; }
            .link-btn { color: var(--primary); text-decoration: none; font-weight: bold; }
            .link-btn:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
    <div class="container">
        <header><h1>全球 AI 核心动态内参</h1></header>
        
        <div class="tabs-nav">
            <div class="tab-btn active" onclick="openTab(event, 'daily')">每日综述</div>
            <div class="tab-btn" onclick="openTab(event, 'filter')">历史检索</div>
        </div>

        <div id="daily" class="tab-pane active">
            <div style="text-align: right; margin-bottom:20px;">
                <label style="font-weight:bold;">发布日期：</label>
                <select id="dateSelect" onchange="changeDate(this.value)" style="padding:5px; border:1px solid var(--primary); border-radius:4px; font-weight: bold;">
                    {% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}
                </select>
            </div>
            
            {% for d in dates %}
            <div id="date-{{d}}" class="date-group" style="display: {{ 'block' if loop.first else 'none' }}">
                <div class="time-label">数据周期：正在计算时间...</div>
                
                {% if headlines_data[d] %}
                <div class="headline-section">
                    <span class="headline-label">今日头条</span>
                    {% for hl in headlines_data[d] %}
                    <div class="hl-item">
                        <div class="tag-group">
                            <span class="tag tag-important">{{hl['话题']}}</span>
                            <span class="tag">公司：{{hl['公司']}}</span>
                        </div>
                        <a href="{{hl['链接']}}" target="_blank" class="hl-title">{{hl['标题']}}</a>
                        <p style="font-size:15px; color:#444; line-height: 1.7; margin-bottom: 10px;">{{hl['核心内容']}}</p>
                        <div class="footer" style="border:none; padding:0;">
                            <span>来源: {{hl['来源']}}</span>
                            <a href="{{hl['链接']}}" class="link-btn" target="_blank">阅读原文 →</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                {% for co, items in news_data[d].items() %}
                <div class="company-section">
                    <h2 class="co-title">{{co}}</h2>
                    {% for it in items %}
                    <div class="card" onclick="this.classList.toggle('open')">
                        <div class="tag-group">
                            <span class="tag tag-important">{{it['话题']}}</span>
                            {% if co == '其他' %}<span class="tag">公司/模型：{{it['公司']}}</span>{% endif %}
                        </div>
                        <span class="title-row">{{it['标题']}}</span>
                        <div class="content-box">
                            {{it['核心内容']}}
                            <div class="footer">
                                <span>来源: {{it['来源']}}</span>
                                <a href="{{it['链接']}}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文 →</a>
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
            <div style="background:#fff; padding:25px; border:1px solid #ddd; display:flex; gap:15px; margin-bottom:25px; position: sticky; top: 0; z-index: 101;">
                <select id="f-date" style="flex:1; padding:10px; border-radius:4px;"><option value="all">全时间段</option>{% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                <select id="f-co" style="flex:1; padding:10px; border-radius:4px;"><option value="all">所有公司</option>{% for c in all_companies %}<option value="{{c}}">{{c}}</option>{% endfor %}</select>
                <button onclick="doSearch()" style="background:var(--primary); color:white; border:none; padding:10px 30px; cursor:pointer; font-weight:bold; border-radius:4px;">开始检索</button>
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
            if(labelEl) labelEl.innerText = "本期监测周期：" + label;
        }
        window.onload = () => { 
            const select = document.getElementById('dateSelect');
            if(select) changeDate(select.value);
        };
        
        function doSearch() {
            const d = document.getElementById('f-date').value, c = document.getElementById('f-co').value;
            const filtered = rawData.filter(it => (d === 'all' || it['日期'] == d) && (c === 'all' || it['公司'] == c));
            const resDiv = document.getElementById('results');
            resDiv.innerHTML = filtered.length ? '' : '<p style="text-align:center; padding:50px; color:#999;">未检索到相关情报</p>';
            
            filtered.forEach(it => {
                const card = document.createElement('div');
                card.className = 'card';
                card.onclick = () => card.classList.toggle('open');
                card.innerHTML = `
                    <div class="tag-group">
                        <span class="tag tag-important">${it['话题']}</span>
                        <span class="tag">日期：${it['日期']}</span>
                        <span class="tag">公司/模型：${it['公司']}</span>
                    </div>
                    <span class="title-row">${it['标题']}</span>
                    <div class="content-box">
                        ${it['核心内容']}
                        <div class="footer">
                            <span>来源: ${it['来源']}</span>
                            <a href="${it['链接']}" class="link-btn" target="_blank" onclick="event.stopPropagation();">阅读原文 →</a>
                        </div>
                    </div>`;
                resDiv.appendChild(card);
            });
        }
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
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("CNAME", "w") as f:
        f.write(MY_DOMAIN)

if __name__ == "__main__":
    main()
