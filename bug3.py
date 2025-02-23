async def generate_nanj_thread(query, titles):
    """ Gemini API を使って、なんJのスレッド形式の会話を生成 """
    model = genai.GenerativeModel("gemini-pro")

    prompt = f"""
    【スレッド形式のなんJ議論】
    以下は、「{query}」に関する最新の医学論文から得られた情報をもとにした、なんJ風のスレッドです。

    --- 取得した論文タイトル ---
    {', '.join(titles)}

    --- スレッド開始 ---
    """

    print(f"🟢 Gemini API に送信するプロンプト:\n{prompt}")

    response = model.generate_content(prompt)

    print(f"🟢 Gemini API レスポンス:\n{response.text}")

    if not response or not response.text:
        return ["エラー: Gemini API のレスポンスが無効です。"]

    return response.text.split("\n")
