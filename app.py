from flask import Flask, render_template, request, redirect
import sqlite3
import requests
from openai import OpenAI

app = Flask(__name__)

API_KEY = 'ce4dbc323698321bdf4b81d9f3de4073'
OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY'  # OpenAI APIキーを設定

client = OpenAI(api_key=OPENAI_API_KEY)


def get_weather(city):
    try:
        url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ja'
        response = requests.get(url)
        data = response.json()
        if data.get("cod") != 200:
            return {'error': '天気情報の取得に失敗しました'}
        return {
            'location': data['name'],
            'description': data['weather'][0]['description'],
            'temperature': data['main']['temp'],
            'humidity': data['main']['humidity'],
            'icon': data['weather'][0]['icon']
        }
    except:
        return {'error': 'API通信エラー'}


def get_game_data_wikipedia():
    game_titles = [
        "原神", "エルデンリング", "大乱闘スマッシュブラザーズ",
        "ゼルダの伝説", "スプラトゥーン", "ポケットモンスター",
        "フォートナイト", "あつまれ どうぶつの森"
    ]
    url = "https://ja.wikipedia.org/w/api.php"
    games = []

    for title in game_titles:
        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts|pageimages",
            "exintro": True,
            "explaintext": True,
            "redirects": 1,
            "pithumbsize": 300
        }
        try:
            response = requests.get(url, params=params)
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                games.append({
                    "name": page.get("title"),
                    "summary": page.get("extract"),
                    "url": f"https://ja.wikipedia.org/?curid={page_id}",
                    "thumbnail": page.get("thumbnail", {}).get("source", None)
                })
        except Exception as e:
            print(f"Wikipedia APIエラー({title}):", e)

    return games


def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            title TEXT,
            url TEXT
        )
    ''')

    try:
        c.execute("ALTER TABLE articles ADD COLUMN description TEXT")
        conn.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise

    c.execute("SELECT COUNT(*) FROM articles")
    if c.fetchone()[0] == 0:
        sample_data = [
            ("ゲーム", "PS5ニュース", "https://example.com/game", "最新のPS5情報です"),
            ("ファッション", "夏トレンド", "https://example.com/fashion", "2025年夏の流行紹介"),
            ("天気", "週間天気", "https://example.com/weather", "今週の天気予報"),
            ("車", "最新EV", "https://example.com/car", "最新電気自動車のレビュー"),
            ("芸能人", "有名人ニュース", "https://example.com/celebrity", "話題の芸能ニュース")
        ]
        c.executemany(
            "INSERT INTO articles (category, title, url, description) VALUES (?, ?, ?, ?)",
            sample_data
        )
        conn.commit()

    conn.close()


@app.route('/')
def index():
    categories = ['ゲーム', 'ファッション', '天気', '車', '芸能人']
    return render_template('index.html', categories=categories)


@app.route('/delete_article/<int:article_id>', methods=['POST'])
def delete_article(article_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # 削除する記事のカテゴリを取得
    c.execute("SELECT category FROM articles WHERE id=?", (article_id,))
    row = c.fetchone()
    category = row[0] if row else ''

    # 記事を削除
    c.execute("DELETE FROM articles WHERE id=?", (article_id,))
    conn.commit()
    conn.close()

    # 削除後にカテゴリページにリダイレクト
    if category:
        return redirect(f'/category/{category}')
    return redirect('/')


@app.route('/category/<category>', methods=['GET', 'POST'])
def show_category(category):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST' and category == 'ゲーム':
        game_title = request.form.get('game_title')
        game_url = request.form.get('game_url')
        game_description = request.form.get('game_description')
        if game_title and game_url and game_description:
            c.execute(
                "INSERT INTO articles (category, title, url, description) VALUES (?, ?, ?, ?)",
                (category, game_title, game_url, game_description)
            )
            conn.commit()

    c.execute("SELECT id, title, url, description FROM articles WHERE category=?", (category,))
    articles = c.fetchall()
    conn.close()

    weather_data = None
    game_data = None
    fashion_text = None
    city = request.args.get('city', 'MIYAZAKI')

    if category == '天気':
        weather_data = get_weather(city)
    if category == 'ゲーム':
        game_data = get_game_data_wikipedia()
    if category == 'ファッション':
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "2025年夏のファッショントレンドを日本語で簡単に教えて"}]
        )
        fashion_text = response.choices[0].message.content

    return render_template(
        'category.html',
        category=category,
        articles=articles,
        weather=weather_data,
        games=game_data,
        city=city,
        fashion=fashion_text
    )


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
