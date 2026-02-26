import feedparser
import requests
from bs4 import BeautifulSoup
import pymysql
from openai import OpenAI
import datetime
import time
import json
import os

# ================= 关键配置区 =================
# 1. AI 配置 (已改为本地 Ollama)
client = OpenAI(
    api_key="ollama",
    base_url="http://localhost:11434/v1"
)
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:7b")

# 2. 数据库配置 - 改成 TiDB Cloud
DB_CONFIG = {
    'host': 'gateway01.ap-southeast-1.prod.aws.tidbcloud.com',
    'port': 4000,
    'user': '4UQMmu8pBXHpYPX.root',
    'password': 'ErrvTvIZ1l1WdQ90',
    'database': 'test',
    'charset': 'utf8mb4',
    'ssl': {'ssl': True}
}

# 3. 订阅源列表
RSS_LIST = [
    "http://localhost:4000/feeds/MP_WXS_3216386757.rss",
    "http://localhost:4000/feeds/MP_WXS_3582669377.rss",
    "http://localhost:4000/feeds/MP_WXS_3072073807.rss",
    "http://localhost:4000/feeds/MP_WXS_3509014347.rss",
    "http://localhost:4000/feeds/MP_WXS_2398020661.rss",
    "http://localhost:4000/feeds/MP_WXS_3964424679.rss",
    "http://localhost:4000/feeds/MP_WXS_3274687166.rss",
    "http://localhost:4000/feeds/MP_WXS_3229412976.rss",
    "http://localhost:4000/feeds/MP_WXS_3252128862.rss",
    "http://localhost:4000/feeds/MP_WXS_3219231991.rss",
    "http://localhost:4000/feeds/MP_WXS_3276902399.rss",
    "http://localhost:4000/feeds/MP_WXS_3935938222.rss",
    "http://localhost:4000/feeds/MP_WXS_3198215923.rss"
]

CATEGORIES = ["技术研发与突破", "政策法规与市场交易", "工程项目与并网实践", "企业动向与产业经济", "基础知识与科普解读",
              "安全事件与事故处理", "其他"]


# ============================================

def get_full_text_from_wechat(url):
    """【跳转抓取】直接去微信官网抓正文"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        content = soup.find('div', id='js_content')
        return content.get_text(strip=True) if content else ""
    except:
        return ""


def generate_simple_summary(title, content):
    """生成简单摘要（不调用AI，提高速度）"""
    clean_content = content.replace('\n', ' ').replace('\r', ' ')
    if len(clean_content) > 200:
        return clean_content[:200] + "..."
    return clean_content if clean_content else "点击查看原文"


def generate_summary_only(title, content):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "你是一个文章摘要助手，只输出纯文本摘要"},
                      {"role": "user", "content": f"为以下文章生成3句话摘要：\n标题：{title}\n内容：{content[:800]}"}],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  ❌ AI 摘要生成失败: {e}")
        return "点击查看原文"


def call_ai_for_classification_and_summary(title, content):
    try:
        content_preview = content[:500] if len(content) > 500 else content

        prompt = f"""作为储能行业资深研究员，请将以下文章归类到以下类别之一：{CATEGORIES}

判断依据：
- 技术研发与突破：包含储能技术研发、创新、专利、实验进展等内容
- 政策法规与市场交易：**专指电力行业**的政策文件、市场机制、交易规则、电价政策、并网管理等内容
- 企业动向与产业经济：包含储能企业排名、产量数据、财务信息、市场分析等内容  
- 工程项目与并网实践：包含储能项目建设、并网运行、工程实施等内容
- 基础知识与科普解读：包含储能技术原理、入门教程、科普知识等内容
- 安全事件与事故处理：包含储能安全事故、应急处理、风险管控等内容

文章标题：{title}
文章开头内容：{content_preview}

请严格按照以下JSON格式返回：
{{"category": "分类名称", "summary": "3句摘要"}}"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一个只输出JSON并严格遵守预设分类名的机器人"},
                {"role": "user", "content": prompt}
            ],
            response_format={'type': 'json_object'}
        )

        raw_response = response.choices[0].message.content
        print(f"    🤖 AI原始响应: {raw_response}")

        res = json.loads(raw_response)
        ai_category = res.get('category', '其他').strip()
        if ai_category not in CATEGORIES:
            print(f"    ⚠️ AI返回无效分类: '{ai_category}'，归为其他")
            ai_category = "其他"
        return res.get('summary', '点击查看原文').strip(), ai_category
    except Exception as e:
        print(f"  ❌ AI 调用失败: {e}")
        return "AI分析失败", "其他"


def analyze_article(title, content):
    print(f"  🤖 正在分析文章: {title[:20]}...")

    title_clean = title.replace(" ", "").lower()
    summary = "点击查看原文"

    print(f"    🔍 清洗后标题: {title_clean}")

    safety_keywords = ["事故", "爆燃", "爆炸", "火灾", "伤亡", "安全", "隐患", "整改", "通报"]
    if any(k in title_clean for k in safety_keywords):
        category = "安全事件与事故处理"
        summary = generate_simple_summary(title, content)
        print(f"    🚨 安全事件命中: {category}")
        return summary, category

    company_keywords = ["盈利", "财报", "上市", "并购", "排名", "top", "产量", "销量", "动态", "市场份额"]
    if any(k in title_clean for k in company_keywords):
        category = "企业动向与产业经济"
        summary = generate_simple_summary(title, content)
        print(f"    💼 企业动向命中: {category}")
        return summary, category

    science_keywords = ["科普", "入门", "教程", "教学", "学习", "方法", "技巧", "详解", "原理", "图解", "解决办法",
                        "总结", "常见问题"]
    if any(k in title_clean for k in science_keywords):
        category = "基础知识与科普解读"
        summary = generate_simple_summary(title, content)
        print(f"    📚 科普类命中: {category}")
        return summary, category

    policy_keywords = ["政策", "法规", "标准", "补贴", "管理办法", "电价", "市场交易"]
    if any(k in title_clean for k in policy_keywords):
        category = "政策法规与市场交易"
        summary = generate_simple_summary(title, content)
        print(f"    📋 政策法规命中: {category}")
        return summary, category

    tech_keywords = ["研发", "技术", "突破", "创新", "专利", "最新进展"]
    if any(k in title_clean for k in tech_keywords):
        category = "技术研发与突破"
        summary = generate_simple_summary(title, content)
        print(f"    🔬 技术研发命中: {category}")
        return summary, category

    project_keywords = ["项目", "工程", "建设", "并网", "mw", "gw", "储能电站", "示范"]
    if any(k in title_clean for k in project_keywords):
        category = "工程项目与并网实践"
        summary = generate_simple_summary(title, content)
        print(f"    🏗️ 工程项目命中: {category}")
        return summary, category

    print(f"    🤔 关键词未命中，调用AI进行深度分析...")
    summary, category = call_ai_for_classification_and_summary(title, content)

    if category in CATEGORIES and category != "分类名称":
        print(f"    🤖 采用AI分类: {category}")
    else:
        category = "其他"
        print(f"    ⚠️ AI分类无效或未识别，归为其他")

    return summary, category


def article_exists_in_db(title):
    """检查文章是否已存在于 TiDB 数据库中"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            sql = "SELECT COUNT(*) FROM articles WHERE title = %s"
            cursor.execute(sql, (title,))
            result = cursor.fetchone()
            return result[0] > 0
    except Exception as e:
        print(f"  ❌ 数据库查询失败: {e}")
        return False
    finally:
        if conn:
            conn.close()


def save_to_db(data):
    """保存单条文章数据到 TiDB Cloud"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            sql = """INSERT INTO articles
                         (title, link, author, publish_date, summary, category, raw_content)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, data)
        conn.commit()
        print(f"  ✅ [入库成功]: {data[0][:20]}...")
    except Exception as e:
        print(f"  ❌ 数据库保存失败: {e}")
    finally:
        if conn:
            conn.close()


def run():
    print(f"--- 🚀 TiDB Cloud AI 自动化采集启动: {datetime.datetime.now()} ---")

    total_directories = len(RSS_LIST)
    total_processed_articles = 0
    skipped_articles = 0

    print("  📥 采用增量更新模式，保留历史数据")

    for index, rss_url in enumerate(RSS_LIST, 1):
        print(f"\n📡 读取目录 [{index}/{total_directories}]: {rss_url}")

        directory_article_count = 0
        directory_skipped_count = 0

        try:
            feed = feedparser.parse(rss_url)

            for entry in feed.entries:
                print(f"📖 检查: {entry.title}")

                if article_exists_in_db(entry.title):
                    print(f"  ⏭️  文章已存在，跳过")
                    directory_skipped_count += 1
                    skipped_articles += 1
                    continue

                text_only = get_full_text_from_wechat(entry.link)
                if len(text_only) < 100:
                    print(f"  ⚠️ 无法获取正文，跳过")
                    continue

                summary, category = analyze_article(entry.title, text_only)

                save_to_db((
                    entry.title,
                    entry.link,
                    "公众号",
                    datetime.datetime.now(),
                    summary,
                    category,
                    text_only
                ))

                directory_article_count += 1
                total_processed_articles += 1

            print(f"  📊 该目录处理: {directory_article_count} 篇新增, {directory_skipped_count} 篇跳过")

        except Exception as e:
            print(f"  ❌ 读取目录失败: {e}")
            continue

    print(f"\n--- ✨ 任务全部完成 ---")
    print(f"📊 统计信息:")
    print(f"   • 总目录数: {total_directories}")
    print(f"   • 本次新增文章数: {total_processed_articles}")
    print(f"   • 跳过重复文章数: {skipped_articles}")
    print(f"   • 平均每目录新增: {total_processed_articles / total_directories:.1f} 篇")


if __name__ == "__main__":
    run()
