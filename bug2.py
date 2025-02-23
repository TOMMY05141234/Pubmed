async def fetch_article_titles(article_ids):
    """ PubMed API から論文のタイトルを取得 """
    if not article_ids:
        print("❌ 論文 ID が見つかりませんでした")
        return []

    fetch_params = {"db": "pubmed", "id": ",".join(article_ids), "retmode": "xml"}

    async with httpx.AsyncClient() as client:
        fetch_response = await client.get(PUBMED_FETCH_URL, params=fetch_params)

    print(f"PubMed API タイトル取得レスポンス: {fetch_response.status_code}")

    if fetch_response.status_code != 200:
        return []

    root = ET.fromstring(fetch_response.text)
    titles = []
    for article in root.findall(".//PubmedArticle"):
        title_elem = article.find(".//ArticleTitle")
        if title_elem is not None:
            titles.append(title_elem.text)

    print(f"取得した論文タイトル: {titles}")  # デバッグ用

    return titles
