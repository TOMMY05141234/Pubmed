import asyncio
import httpx
import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
import os
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

app = Flask(__name__)

# キャッシュを無効化
cache = Cache(app, config={'CACHE_TYPE': 'null'})

# PubMed API のエンドポイント
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/"

async def fetch_recent_articles(query):
    """ 過去5年以内の論文を検索し、最大10件を取得 """
    current_year = datetime.now().year
    start_year = current_year - 5  # 過去5年

    params = {
        "db": "pubmed",
        "term": f"{query}[Title/Abstract] AND {start_year}:{current_year}[PDAT]",
        "retmode": "json",
        "retmax": 10,  # 最大10件まで取得
        "sort": "pub_date"  # 最新順に取得
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(PUBMED_SEARCH_URL, params=params)

    if response.status_code != 200:
        return []

    data = response.json()
    article_ids = data.get("esearchresult", {}).get("idlist", [])
    return article_ids

async def fetch_article_titles(article_ids):
    """ PubMed API から論文のタイトルとリンクを取得 """
    if not article_ids:
        return []

    fetch_params = {"db": "pubmed", "id": ",".join(article_ids), "retmode": "xml"}
    async with httpx.AsyncClient() as client:
        fetch_response = await client.get(PUBMED_FETCH_URL, params=fetch_params)

    if fetch_response.status_code != 200:
        return []

    root = ET.fromstring(fetch_response.text)
    articles = []
    for i, article in enumerate(root.findall(".//PubmedArticle")):
        title_elem = article.find(".//ArticleTitle")
        if title_elem is not None and title_elem.text:
            articles.append({
                "title": title_elem.text,
                "url": f"{PUBMED_ARTICLE_URL}{article_ids[i]}"  # 論文への直接リンク
            })

    return articles

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
    response = model.generate_content(prompt)
    if not response or not response.text:
        return "エラー: Gemini API のレスポンスが無効です。"
    return response.text

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
async def search():
    query = request.form.get("query")
    if not query:
        return render_template("index.html", error="キーワードを入力してください")

    # **日本語ワードを英語に翻訳（エラーハンドリングを追加）**
    try:
        translated_query = GoogleTranslator(source='auto', target='en').translate(query)
        query_en = translated_query if translated_query and "Error" not in translated_query else query
    except Exception as e:
        query_en = query

    # **過去5年以内の論文を検索**
    article_ids = await fetch_recent_articles(query_en)
    if not article_ids:
        return render_template("index.html", error="該当する論文が見つかりませんでした")

    # **論文タイトルとリンクを取得**
    articles = await fetch_article_titles(article_ids)
    if not articles:
        return render_template("index.html", error="論文のタイトルを取得できませんでした")

    # **Gemini API を使って、なんJスレッドを生成**
    conversation = await generate_nanj_thread(query, [article["title"] for article in articles])

    return render_template("results.html", query=query, articles=articles, conversation=conversation)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
