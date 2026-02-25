import os
import json
import gspread
import feedparser
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 1. 认证设置
def get_gspread_client():
    # 从 GitHub Secrets 读取环境变量
    creds_dict = json.loads(os.environ['GCP_SA_JSON'])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 2. 抓取逻辑 (以 RSSHub 为例抓取公众号)
def fetch_news():
    # 这里建议把你的公众号列表存成一个 list
    sources = {
        "DeepSeek": "https://rsshub.app/wechat/mp/msig/DeepSeek",
        "量子位智库": "https://rsshub.app/wechat/mp/msig/QbitAI",
        "OpenAI": "https://rsshub.app/openai/news"
    }
    
    news_items = []
    for name, url in sources.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # 每次取最新3条
            news_items.append([
                datetime.now().strftime("%Y-%m-%d"), 
                name, 
                entry.title, 
                entry.link
            ])
    return news_items

def main():
    client = get_gspread_client()
    # 填入你接收数据的那个 Excel ID
    sheet = client.open_by_key("1CgheqoqcKn-klAJCS8fWRdyP1ybBlG8ReqPLsqkFpl8").sheet1
    
    # 获取已有链接去重
    existing_links = sheet.col_values(4) 
    
    data = fetch_news()
    new_rows = [item for item in data if item[3] not in existing_links]
    
    if new_rows:
        sheet.append_rows(new_rows)
        print(f"成功更新 {len(new_rows)} 条情报")
    else:
        print("今日暂无更新")

if __name__ == "__main__":
    main()
