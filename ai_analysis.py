from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

print("API KEY:", os.getenv("OPENAI_API_KEY"))


# 初始化 client（會自動讀環境變數）
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_project(budget, cost, profit):
    return "（AI 未啟用）成本分析功能暫時使用規則判斷"
'''
    prompt = f"""
    你是一位建築成本分析師。

    專案資訊：
    預算：{budget}
    成本：{cost}
    利潤：{profit}

    請用一句專業且簡潔的話，分析該專案狀況並給出建議。我這只是一個測試用例，所以簡潔就行。
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是專業建築成本顧問"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"AI 分析失敗：{str(e)}"
'''