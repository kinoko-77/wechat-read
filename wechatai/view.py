import streamlit as st
import pymysql
import pandas as pd
import time

st.set_page_config(page_title="储能内参 AI 版", layout="wide")

# ========== 数据库配置 ==========
DB_CONFIG = {
    'host': 'gateway01.ap-southeast-1.prod.aws.tidbcloud.com',
    'port': 4000,
    'user': '4UQMmu8pBXHpYPX.root',
    'password': 'ErrvTvIZ1l1WdQ90',
    'database': 'test',
    'charset': 'utf8mb4',
    'ssl': {'ssl': True},
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 30,
    'read_timeout': 30,
    'write_timeout': 30
}


# ========== 数据库连接函数 ==========
def get_connection(max_retries=3):
    """带重试的连接，给 TiDB 冷启动时间"""
    for i in range(max_retries):
        try:
            conn = pymysql.connect(**DB_CONFIG)
            return conn
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(3)
                continue
            raise e


# ========== 获取数据（带缓存）==========
@st.cache_data(ttl=600)  # 10 分钟缓存
def get_data():
    try:
        with st.spinner('🔄 正在连接数据库...'):
            conn = get_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                           SELECT id, category, title, summary, publish_date, link
                           FROM articles
                           ORDER BY publish_date DESC
                           """)
            rows = cursor.fetchall()

        conn.close()

        if rows:
            df = pd.DataFrame(rows)
            df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
            return df
        return pd.DataFrame(columns=['id', 'category', 'title', 'summary', 'publish_date', 'link'])

    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        st.info("💡 请刷新页面重试")
        return pd.DataFrame()


# ========== 更新分类 ==========
def update_category(article_id, new_category):
    try:
        article_id = int(float(article_id))

        with st.spinner('🔄 正在更新...'):
            conn = get_connection()
            with conn.cursor() as cursor:
                sql = "UPDATE articles SET category = %s WHERE id = %s"
                cursor.execute(sql, (new_category, article_id))
            conn.commit()
            conn.close()

        get_data.clear()
        return True
    except Exception as e:
        st.error(f"更新失败: {e}")
        return False


# ========== 页面内容 ==========
st.title("⚡ 储能行业公众号 AI 自动简报")

# 分类选项
CATEGORIES = ["技术研发与突破", "政策法规与市场交易", "工程项目与并网实践",
              "企业动向与产业经济", "基础知识与科普解读", "安全事件与事故处理", "其他"]

# 获取数据
df = get_data()

# 空数据保护
if df.empty:
    st.warning("⚠️ 数据库中没有数据，请刷新页面重试")
    st.stop()

# 侧边栏筛选
st.sidebar.header("筛选选项")
selected_cat = st.sidebar.multiselect("选择分类", options=df['category'].unique(), default=df['category'].unique())

# 手动修改开关
enable_edit = st.sidebar.checkbox("启用手动修改分类")

# 统计信息
filtered_df = df[df['category'].isin(selected_cat)]
st.sidebar.markdown("---")
st.sidebar.write(f"**总计文章数:** {len(df)}")
st.sidebar.write(f"**筛选后文章数:** {len(filtered_df)}")

# 文章展示
for idx, (_, row) in enumerate(filtered_df.iterrows()):
    unique_key = f"{idx}_{int(row['id'])}"

    with st.container():
        st.markdown(f"### {row['title']}")
        st.caption(f"📅 {row['publish_date']} | 🏷️ {row['category']}")
        st.success(f"**AI 摘要：** {row['summary']}")
        st.markdown(f"[🔗 点击阅读原文]({row['link']})")

        if enable_edit:
            st.markdown("---")
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                new_category = st.selectbox(
                    "修改分类:",
                    options=CATEGORIES,
                    index=CATEGORIES.index(row['category']) if row['category'] in CATEGORIES else 0,
                    key=f"select_{unique_key}"
                )

            with col2:
                if st.button("更新", key=f"update_{unique_key}"):
                    if new_category != row['category']:
                        if update_category(row['id'], new_category):
                            st.success("✅ 分类更新成功！")
                            st.rerun()
                        else:
                            st.error("❌ 更新失败！")
                    else:
                        st.info("分类未改变")

            with col3:
                st.caption(f"ID: {int(row['id'])}")

        st.divider()
