import os
import json
import gspread
import feedparser
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, timezone

# --- 配置区 ---
SHEET_ID = "1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8"
TAB_NAME = "Long List"  # 指定写入这个 Tab
BEIJING = timezone(timedelta(hours=8))

ENTITY_KEYWORDS = {
    "OpenAI": ["OpenAI", "GPT-4", "GPT-5", "Sora", "o1", "SearchGPT"],
    "Anthropic": ["Anthropic", "Claude"],
    "Google": ["Google", "Gemini", "DeepMind"],
    "Meta": ["Meta", "Llama"],
    "Microsoft": ["Microsoft", "微软", "Copilot"],
    "阿里巴巴": ["阿里巴巴", "阿里", "通义", "Qwen", "千问", "蚂蚁集团", "蚂蚁阿福", "支付宝"],
    "字节跳动": ["字节跳动", "豆包", "Doubao"],
    "百度": ["百度", "文心", "Ernie"],
    "腾讯": ["腾讯", "混元", "Hunyuan"],
    "Kimi": ["Kimi", "月之暗面", "Moonshot"],
    "智谱AI": ["智谱", "ChatGLM", "GLM-4"],
    "DeepSeek": ["DeepSeek"],
    "科大讯飞": ["科大讯飞", "讯飞", "星火"],
    "商汤": ["商汤", "SenseTime", "日日新"],
    "可灵": ["可灵", "Kling", "快手AI"],
    "OpenClaw": ["OpenClaw"],
    "Minimax": ["Minimax", "海螺AI"]
}

SOURCES = {
    "量子位": "https://rsshub.app/wechat/mp/msig/QbitAI",
    "DeepSeek": "https://rsshub.app/wechat/mp/msig/deepseek_ai",
    "Kimi智能助手": "https://rsshub.app/wechat/mp/msig/MoonshotAI",
    "智谱AI": "https://rsshub.app/wechat/mp/msig/ZhipuAI",
    "机器之心": "https://rsshub.app/wechat/mp/msig/almosthuman2014",
    "新智元": "https://rsshub.app/wechat/mp/msig/AI_era",
    "通义大模型": "https://rsshub.app/wechat/mp/msig/Qwen-AI",
    "晚点LatePost": "https://rsshub.app/wechat/mp/msig/postlate",
    "虎嗅": "https://rsshub.app/wechat/mp/msig/huxiu_com",
    "36氪": "https://rsshub.app/wechat/mp/msig/wow36kr",
    "OpenAI News": "https://rsshub.app/openai/news",
    "Anthropic News": "https://rsshub.app/anthropic/news",
    "Google AI Blog": "https://rsshub.app/google/blog/ai"
}

def extract_entity(title):
    for entity, keywords in ENTITY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title.lower():
                return entity
    return "通用/其他"

def get_time_window():
    now = datetime.now(BEIJING)
    today_17pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
    if now >= today_17pm:
        end_time = today_17pm
        start_time = end_time - timedelta(days=1)
    else:
        end_time = today_17pm - timedelta(days=1)
        start_time = end_time - timedelta(days=1)
    return start_time, end_time, now

def fetch_data(start_t, end_t):
    news_list = []
    for name, url in SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed'): continue
                pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc).astimezone(BEIJING)
                if start_t <= pub_time < end_t:
                    entity = extract_entity(entry.title)
                    news_list.append({
                        "title": entry.title,
                        "entity": entity,
                        "link": entry.link,
                        "raw_time": pub_time
                    })
        except Exception:
            print(f"❌ {name} 访问异常")
    return news_list

def write_to_sheets(news_data, run_date):
    if not news_data:
        print("📭 无新数据。")
        return
    creds_dict = json.loads(os.environ['GCP_SA_JSON'])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    try:
        # 核心改动：通过名字打开特定的 Tab
        sheet = client.open_by_key(SHEET_ID).worksheet(TAB_NAME)
        
        # C列查重 (链接列)
        existing_links = sheet.col_values(3)
        
        rows_to_add = []
        news_data.sort(key=lambda x: x["raw_time"])
        date_str = run_date.strftime("%Y-%m-%d") 
        
        for item in news_data:
            if item["link"] not in existing_links:
                # 写入顺序：标题 | 实体 | 链接 | 日期
                rows_to_add.append([item["title"], item["entity"], item["link"], date_str])
        
        if rows_to_add:
            sheet.append_rows(rows_to_add)
            print(f"🚀 成功向 {TAB_NAME} 写入 {len(rows_to_add)} 条记录。")
        else:
            print("数据已存在。")
    except Exception as e:
        print(f"🔴 错误: {e}")

if __name__ == "__main__":
    start_t, end_t, run_t = get_time_window()
    data = fetch_data(start_t, end_t)
    write_to_sheets(data, run_t)
