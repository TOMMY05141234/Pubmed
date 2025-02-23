import requests

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

params = {
    "db": "pubmed",
    "term": "Alzheimer[Title/Abstract]",  # 検索ワード
    "retmode": "json",
    "retmax": 10  # 取得する論文の最大数
}

response = requests.get(PUBMED_SEARCH_URL, params=params)

# 結果を表示
print("PubMed API レスポンス:")
print(response.json())
