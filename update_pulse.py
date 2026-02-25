import os
import json
import gspread
import feedparser
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, timezone

# --- 配置区 ---
# 1. 目标 Excel 的 ID
SHEET_ID = "1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8"

# 2. 设置时区 (北京时间 GMT+8)
BEIJING = timezone(timedelta(hours=8))

# 3. 数据源清单 (微信公众号建议使用 RSSHub 转换)
# 格式为 "显示名称": "RSS地址"
SOURCES = {
    "量子位": "https://rsshub.app/wechat/mp/msig/QbitAI",
    "DeepSeek": "https://rsshub.app/wechat/mp/msig/deepseek_ai",
    "Kimi智能助手": "https://rsshub.app/wechat/mp/msig/MoonshotAI",
    "智谱AI": "https://rsshub.app/wechat/mp/msig/ZhipuAI",
    "机器之心": "https://rsshub.app/wechat/mp/msig/almosthuman2014",
    "新智元": "https://rsshub.app/wechat/mp/msig/AI_era",
    "通义大模型": "https://rsshub.app/wechat/mp/msig/Qwen-AI",
    "OpenAI News": "https://rsshub.app/openai/news",
    "Anthropic": "https://rsshub.app/anthropic/news",
    "Google AI Blog": "https://rsshub.app/google/blog/ai",
    # 您可以在此继续添加其他公众号或官网链接...
}

def get_time_window():
    """动态获取 24 小时时间窗口：最近的一个 17:00 周期"""
    now = datetime.now(BEIJING)
    today_17pm = now.replace(hour=17, minute=0, second=0, microsecond=0)

    if now >= today_17pm:
        # 正常执行情况：当前过了17点，取 [昨天17点, 今天17点]
        end_time = today_17pm
        start_time = end_time - timedelta(days=1)
    else:
        # 手动提前运行情况：当前未到17点，取 [前天17点, 昨天17点]
        end_time = today_17pm - timedelta(days=1)
        start_time = end_time - timedelta(days=1)

    print(f"--- 运行报告 ---")
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"抓取窗口: {start_time.strftime('%Y-%m-%d %H:%M')} -> {end_time.strftime('%Y-%m-%d %H:%M')}")
    return start_time, end_time

def fetch_data(start_t, end_t):
    """从所有源抓取符合时间窗口的数据"""
    news_list = []
    for name, url in SOURCES.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                # 解析发布时间 (RSS标准通常为UTC)
                if not hasattr(entry, 'published_parsed'): continue
                
                pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc).astimezone(BEIJING)
                
                # 核心过滤逻辑：只取窗口期内的数据
                if start_t <= pub_time < end_t:
                    news_list.append({
                        "date": pub_time.strftime("%Y-%m-%d %H:%M"),
                        "source": name,
                        "title": entry.title,
                        "link": entry.link
                    })
                    count += 1
            print(f"✅ {name}: 发现 {count} 篇新动态")
        except Exception as e:
            print(f"❌ {name} 抓取失败: {e}")
    return news_list

def write_to_sheets(news_data):
    """将数据写入 Google Sheets"""
    if not news_data:
        print("📭 窗口期内无新数据，停止写入。")
        return

    # 从 GitHub Secrets 获取凭据
    creds_dict = json.loads(os.environ['GCP_SA_JSON'])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        # 查重逻辑：读取现有第4列（链接列）
        existing_links = sheet.col_values(4)
        
        rows_to_add = []
        for item in news_data:
            if item["link"] not in existing_links:
                rows_to_add.append([item["date"], item["source"], item["title"], item["link"]])
        
        if rows_to_add:
            # 排序：按发布时间从旧到新，这样新文章在最下面
            rows_to_add.sort(key=lambda x: x[0])
            sheet.append_rows(rows_to_add)
            print(f"🚀 成功向 Excel 写入 {len(rows_to_add)} 条新记录！")
        else:
            print("查重完成：所有数据已存在，无需写入。")
            
    except Exception as e:
        print(f"🔴 写入 Excel 出错: {e}")

if __name__ == "__main__":
    start_time, end_time = get_time_window()
    news_results = fetch_data(start_time, end_time)
    write_to_sheets(news_results)
