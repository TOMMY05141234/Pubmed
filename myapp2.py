import asyncio
import httpx
import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
import os
import random
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_caching import Cache
from deep_translator import GoogleTranslator

# `.env` から環境変数を読み込む
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini API を設定
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__, template_folder="templates")

# キャッシュを無効化
cache = Cache(app, config={'CACHE_TYPE': 'null'})

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query")
    if not query:
        return render_template("index.html", error="キーワードを入力してください")

    try:
        translated_query = GoogleTranslator(source='auto', target='en').translate(query)
        query_en = translated_query if translated_query and "Error" not in translated_query else query
    except Exception:
        query_en = query

    article_id = asyncio.run(fetch_random_recent_article(query_en))
    if article_id is None:
        return render_template("index.html", error="該当する論文が見つかりませんでした")

    article = asyncio.run(fetch_full_text(article_id))
    if article is None:
        return render_template("index.html", error="論文の情報を取得できませんでした")

    conversation = generate_nanj_thread(query, article)

    return render_template("result.html", query=query, article=article, conversation=conversation)

# PubMed API のエンドポイント
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/"

async def fetch_random_recent_article(query):
    """ 過去3年以内の論文を検索し、ランダムに1件取得 """
    current_year = datetime.now().year
    start_year = current_year - 3

    params = {
        "db": "pubmed",
        "term": f"{query}[Title/Abstract] AND {start_year}:{current_year}[PDAT]",
        "retmode": "json",
        "retmax": 10,
        "sort": "pub_date"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(PUBMED_SEARCH_URL, params=params)

    if response.status_code != 200:
        return None

    data = response.json()
    article_ids = data.get("esearchresult", {}).get("idlist", [])
    if not article_ids:
        return None

    return random.choice(article_ids)

async def fetch_full_text(article_id):
    """ PubMed API から論文のフルテキストを取得 """
    if not article_id:
        return None

    fetch_params = {"db": "pubmed", "id": article_id, "retmode": "xml"}
    async with httpx.AsyncClient() as client:
        fetch_response = await client.get(PUBMED_FETCH_URL, params=fetch_params)

    if fetch_response.status_code != 200:
        return None

    root = ET.fromstring(fetch_response.text)
    article_elem = root.find(".//PubmedArticle")
    if not article_elem:
        return None

    title_elem = article_elem.find(".//ArticleTitle")
    abstract_elem = article_elem.find(".//AbstractText")
    full_text_url = f"https://www.tandfonline.com/doi/{article_id}"  # 仮のリンクを設定
    
    return {
        "title": title_elem.text if title_elem is not None else "タイトルなし",
        "abstract": abstract_elem.text if abstract_elem is not None else "要約なし",
        "url": f"{PUBMED_ARTICLE_URL}{article_id}",
        "full_text": full_text_url
    }

def generate_nanj_thread(query, article):
    """ Gemini API を使って、論文に基づいた適切なスレッドを生成 """
    model = genai.GenerativeModel("gemini-pro")

    theme = article['title'] if article['title'] else query
    summary = article['abstract'] if article['abstract'] else "この論文の詳細は不明です。"
    full_text = article['full_text'] if article['full_text'] else "フルテキストURLなし"

    base_prompt = f"""
    【なんJ医学スレ: {theme}の最新研究】
    --- 使用する論文 ---
    【タイトル】: {article['title']}
    【URL】: {article['url']}
    【フルテキスト】: {full_text}
    【要約】: {summary}

    **🔹 あなたの役割**
    あなたは **最新の医学論文をもとに、なんJスレッドを再現するAI** です。
    スレッドのフォーマット、議論の流れ、専門家の発言スタイルを理解し、**リアルなスレッドを生成** してください。

    **🔹 スレッドのルール**
    - **論文の内容を上から下まで議論し終わった時点でスレッドを終了する。**
    - **スレッドの流れを作る（質問→議論→ツッコミ→結論）。**
    - **議論の問題提起は必ず、なんJ民からスタートする。**
    - **各レスのキャラ設定を守る**
        - 【医師】: **論文を医学的に解説**し、治療法や臨床的な意義を説明する/**データ分析を重視**し、P値やサンプルサイズ、バイアスを議論する
        - 【薬剤師】: **薬の副作用や併用注意** について補足する
        - 【看護師】: **現場の実態を説明し、患者ケアの観点を提供**
        - 【なんJ民】: **煽り気味のレスを入れつつ、知識を得るために議論に食いつく**
    - **必ず論文のデータ（P値、サンプルサイズ、治療成功率など）を含める**
    - **「ツッコミ」や「反論」を適切に挟み、議論が単調にならないようにする**
    - **スレッドの最後で「この研究の結論」「今後の研究課題」を整理する**
    - **以下のフォーマットを参考にスレッドを作成する。日付や時間はこの生成された日時を表示する**
        【朗報】〇〇（論文のテーマ）についての最新研究が発表される

        1 風吹けば名無し 2025/02/23(日) 12:00:00.00 ID:Jank9
        なんか面白い論文出たらしいで

        2 風吹けば名無し 2025/02/23(日) 12:00:10.00 ID:RxCji
        どんな内容や？

        3 風吹けば名無し 2025/02/23(日) 12:00:15.00 ID:UYT55
        ソースあるんか？

        4 風吹けば名無し 2025/02/23(日) 12:00:20.00 ID:Dr_Science
        【医師】「〇〇に関する最新の臨床研究で、患者〇〇人を対象にしたRCT（ランダム化比較試験）が実施されました。」

        5 風吹けば名無し 2025/02/23(日) 12:00:25.00 ID:Pharma_Pro
        【薬剤師】「結果として、〇〇の治療効果が従来の治療と比較して有意に改善されたみたいやな。」

        6 風吹けば名無し 2025/02/23(日) 12:00:30.00 ID:Jank9
        え、マジ？エビデンスレベル高いんか？

        7 風吹けば名無し 2025/02/23(日) 12:00:40.00 ID:Dr_Science
        【医師】「p値が0.01未満で、信頼区間も狭いから統計的にも信頼できる。けど、サンプルサイズがちょっと少ないのが気になるな。」

        8 風吹けば名無し 2025/02/23(日) 12:00:50.00 ID:Nurse_Care
        【看護師】「でも副作用の報告もあるから、患者にはしっかり説明せなあかんね。」

        9 風吹けば名無し 2025/02/23(日) 12:01:00.00 ID:Jank9
        これって治療費どのくらいかかるんや？

        10 風吹けば名無し 2025/02/23(日) 12:01:10.00 ID:Pharma_Pro
        【薬剤師】「今のところ海外のデータやけど、日本ではまだ承認されてへんから、保険適用には時間かかりそうやな。」

        11 風吹けば名無し 2025/02/23(日) 12:01:20.00 ID:Jank9
        結局、これって実際に効果あるん？

        12 風吹けば名無し 2025/02/23(日) 12:01:30.00 ID:Dr_Science
        【医師】「理論上は効果ありそう。ただ長期のデータがまだ足りんから、これからの追跡調査が必要や。」

        13 風吹けば名無し 2025/02/23(日) 12:01:40.00 ID:Jank9
        うーん、まだ様子見か…

        14 風吹けば名無し 2025/02/23(日) 12:01:50.00 ID:Nurse_Care
        【看護師】「ただ、今の治療が効かない患者には新しい選択肢になるかもしれん。」

    """

    try:
        response = model.generate_content(base_prompt)
        if not response or not hasattr(response, "text") or not response.text:
            return "エラー: Gemini API のレスポンスが無効です。"

        return response.text.strip()
    except Exception as e:
        return f"Gemini API の呼び出しに失敗しました: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
