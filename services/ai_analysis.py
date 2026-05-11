from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()



# OPENAI
# 初始化 client（會自動讀環境變數）
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#
# def generate_ai_report(prompt):
#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content":"你是一個建築成本管理專家"},
#                 {"role": "user", "content": prompt}
#             ]
#         )
#         return response.choices[0].message.content

#     except Exception as e:
#         return f"AI 分析失敗: {str(e)}"




# DEEPSEEK
print("API KEY:", os.getenv("DEEPSEEK_API_KEY"))

# # 初始化 client（會自動讀環境變數）
client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")

def generate_ai_report(prompt):
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content":"你是一個建築成本管理專家"},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"AI 分析失敗: {str(e)}"