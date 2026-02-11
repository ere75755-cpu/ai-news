import pandas as pd
from jinja2 import Template

# 1. 你的表格地址
SHEET_URL = "https://docs.google.com/spreadsheets/d/1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8/export?format=csv&gid=0"
COMPANY_ORDER = ['OpenAI', 'Anthropic', 'Google', 'Meta', '字节', '阿里', '腾讯', '其他']
TOPIC_ORDER = ['技术迭代', '产品动态', '商业动态', '春节活动', '数据洞察']

def main():
    df = pd.read_csv(SHEET_URL)
    
    # 排序逻辑
    def get_sort_score(row):
        c_val = row['公司'] if row['公司'] in COMPANY_ORDER else '其他'
        c_idx = COMPANY_ORDER.index(c_val)
        t_idx = TOPIC_ORDER.index(row['话题']) if row['话题'] in TOPIC_ORDER else 99
        return (c_idx, t_idx)

    df['sort_score'] = df.apply(get_sort_score, axis=1)
    df = df.sort_values(by=['日期', 'sort_score'], ascending=[False, True])
    all_dates = df['日期'].unique().tolist()

    news_data = {}
    for date in all_dates:
        day_df = df[df['日期'] == date]
        news_data[date] = {}
        for company in COMPANY_ORDER:
            comp_df = day_df[day_df['公司'] == company if company != '其他' else ~day_df['公司'].isin(COMPANY_ORDER[:-1])]
            if not comp_df.empty:
                news_data[date][company] = comp_df.to_dict('records')

    # HTML 模板
    with open("template.html", "w", encoding="utf-8") as f:
        f.write("""
        <!DOCTYPE html><html><head><meta charset="UTF-8"><title>AI News Dashboard</title>
        <style>
            body { font-family: sans-serif; background: #f4f7f6; padding: 20px; color: #333; }
            .container { max-width: 800px; margin: auto; background: #fff; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
            header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #eee; margin-bottom: 20px; }
            .day-group { display: none; }
            .day-group.active { display: block; }
            .company-title { color: #2c3e50; border-left: 5px solid #3498db; padding-left: 10px; margin: 25px 0 15px; }
            .card { border: 1px solid #eee; padding: 15px; margin-bottom: 10px; border-radius: 6px; }
            .tag { background: #eef2f7; color: #3498db; padding: 2px 8px; font-size: 12px; border-radius: 4px; font-weight: bold; }
            a { color: #3498db; text-decoration: none; font-size: 13px; }
        </select></style></head>
        <body><div class="container">
            <header><h2>AI 行业最新动态</h2>
            <select id="dateSelect" onchange="showDate(this.value)">
                {% for d in dates %}<option value="{{d}}">{{d}}</option>{% endfor %}
            </select></header>
            {% for d, cos in news.items() %}
            <div id="{{d}}" class="day-group {{ 'active' if loop.first }}">
                {% for co, items in cos.items() %}
                <h3 class="company-title">{{co}}</h3>
                {% for it in items %}<div class="card">
                    <span class="tag">{{it['话题']}}</span> <strong>{{it['标题']}}</strong>
                    <p style="font-size:14px;">{{it['核心内容']}}</p>
                    <div style="color:#999; font-size:12px;">来源：{{it['来源']}} | <a href="{{it['链接']}}" target="_blank">链接🔗</a></div>
                </div>{% endfor %}{% endfor %}
            </div>{% endfor %}
        </div>
        <script>function showDate(d){
            document.querySelectorAll('.day-group').forEach(el => el.classList.remove('active'));
            document.getElementById(d).classList.add('active');
        }</script></body></html>
        """)

    with open("template.html", "r", encoding="utf-8") as f:
        html = Template(f.read()).render(dates=all_dates, news=news_data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    main()
