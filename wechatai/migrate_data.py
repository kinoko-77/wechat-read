import pymysql
import pandas as pd

print("开始迁移数据...")

# 1. 连接本地 MySQL
local_conn = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='2413462600mq.',
    database='wechat_rss',
    charset='utf8mb4'
)

# 2. 连接 TiDB Cloud
tidb_conn = pymysql.connect(
    host='gateway01.ap-southeast-1.prod.aws.tidbcloud.com',
    port=4000,
    user='4UQMmu8pBXHpYPX.root',
    password='ErrvTvIZ1l1WdQ90',
    database='test',
    charset='utf8mb4',
    ssl={'ssl': True}
)

# 3. 读取本地数据
df = pd.read_sql("SELECT * FROM articles", local_conn)
print(f"📊 从本地读取到 {len(df)} 条数据")

# 4. 重建TiDB表（包含所有列）
with tidb_conn.cursor() as cursor:
    # 删除旧表
    cursor.execute("DROP TABLE IF EXISTS articles")

    # 创建新表（匹配你的本地结构）
    cursor.execute("""
                   CREATE TABLE articles
                   (
                       id           INT AUTO_INCREMENT PRIMARY KEY,
                       category     VARCHAR(100),
                       title        VARCHAR(500),
                       link         VARCHAR(1000),
                       author       VARCHAR(100),
                       publish_date DATE,
                       summary      TEXT,
                       raw_content  TEXT
                   )
                   """)
    print("✅ 已创建新表结构")

# 5. 插入数据
with tidb_conn.cursor() as cursor:
    for _, row in df.iterrows():
        sql = """INSERT INTO articles
                     (category, title, link, author, publish_date, summary, raw_content)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql, (
            row.get('category', ''),
            row.get('title', ''),
            row.get('link', ''),
            row.get('author', ''),
            row.get('publish_date', None),
            row.get('summary', ''),
            row.get('raw_content', '')
        ))

    tidb_conn.commit()
    print(f"✅ 成功导入 {len(df)} 条数据")

# 验证
verify_df = pd.read_sql("SELECT COUNT(*) as count FROM articles", tidb_conn)
print(f"🔍 TiDB 中现有 {verify_df['count'].iloc[0]} 条数据")

local_conn.close()
tidb_conn.close()
print("✅ 迁移完成！")
