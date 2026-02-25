import streamlit as st
import pymysql
import pandas as pd

st.set_page_config(page_title="储能内参 AI 版", layout="wide")
st.title("⚡ 储能行业公众号 AI 自动简报")

# 数据库连接函数
def get_connection():
    return pymysql.connect(host='127.0.0.1', user='root', password='2413462600mq.', database='wechat_rss', charset='utf8mb4')

# 获取数据
def get_data():
    conn = get_connection()
    df = pd.read_sql("SELECT id, category, title, summary, publish_date, link FROM articles ORDER BY publish_date DESC", conn)
    conn.close()
    return df

# 更新分类
def update_category(article_id, new_category):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE articles SET category = %s WHERE id = %s"
            cursor.execute(sql, (new_category, article_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"更新失败: {e}")
        return False
    finally:
        conn.close()

# 分类选项
CATEGORIES = ["技术研发与突破", "政策法规与市场交易", "工程项目与并网实践", "企业动向与产业经济", "基础知识与科普解读", "安全事件与事故处理", "其他"]

df = get_data()

# 侧边栏筛选
st.sidebar.header("筛选选项")
selected_cat = st.sidebar.multiselect("选择分类", options=df['category'].unique(), default=df['category'].unique())

# 手动修改开关
enable_edit = st.sidebar.checkbox("启用手动修改分类")

# 页面展示
filtered_df = df[df['category'].isin(selected_cat)]

# 显示统计信息
st.sidebar.markdown("---")
st.sidebar.write(f"**总计文章数:** {len(df)}")
st.sidebar.write(f"**筛选后文章数:** {len(filtered_df)}")

# 文章展示区域
for i, row in filtered_df.iterrows():
    with st.container():
        st.markdown(f"### {row['title']}")
        st.caption(f"📅 {row['publish_date']} | 🏷️ {row['category']}")
        st.success(f"**AI 摘要：** {row['summary']}")
        st.markdown(f"[🔗 点击阅读原文]({row['link']})")
        
        # 手动修改分类功能
        if enable_edit:
            st.markdown("---")
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                # 下拉选择新的分类
                new_category = st.selectbox(
                    "修改分类:",
                    options=CATEGORIES,
                    index=CATEGORIES.index(row['category']) if row['category'] in CATEGORIES else 0,
                    key=f"select_{row['id']}"
                )
            
            with col2:
                # 更新按钮
                if st.button("更新", key=f"update_{row['id']}"):
                    if new_category != row['category']:
                        if update_category(row['id'], new_category):
                            st.success("分类更新成功！")
                            st.rerun()  # 刷新页面显示更新结果
                        else:
                            st.error("更新失败！")
                    else:
                        st.info("分类未改变")
            
            with col3:
                # 显示文章ID（便于调试）
                st.caption(f"ID: {row['id']}")
        
        st.divider()