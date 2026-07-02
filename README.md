# Nagisa Bean Navi 2

LINE公式アカウントのリッチメニューから使う、なぎさ珈琲焙煎所の「豆診断」静的Webアプリです。

## 現在の実装範囲

- GitHub Pagesで公開できるHTML/CSS/JavaScript構成
- `products.json`を唯一のマスターデータとして読み込み
- 6問のステップ形式診断
- 回答に応じたスコアリング
- おすすめ上位3商品の表示
- Square商品ページへの導線
- スマホ、iPhone Safari、LINE内ブラウザを想定した画面設計

## ファイル構成

```txt
nagisa-bean-navi2/
  index.html
  style.css
  app.js
  products.json
  README.md
  assets/
    images/
    icons/
  crawler/
  sample_data/
  scripts/
  .github/
    workflows/
```

## ローカル確認

`products.json`を`fetch`で読み込むため、ファイルを直接開くのではなくローカルサーバーで確認します。

```bash
python3 -m http.server 8000
```

ブラウザで次を開きます。

```txt
http://localhost:8000/
```

## 品質チェック

GitHub Actionsと同じ検証をローカルで実行できます。

```bash
node --check app.js
python3 -m py_compile crawler/crawl_products.py crawler/normalize_products.py scripts/validate_products.py scripts/validate_static.py
python3 -m json.tool products.json > /tmp/products.json
python3 -m json.tool raw_products.json > /tmp/raw_products.json
python3 -m json.tool sample_data/raw_products.sample.json > /tmp/raw_products.sample.json
python3 scripts/validate_static.py
python3 scripts/validate_products.py
```

GitHubへpushまたはPull Request作成時は、`.github/workflows/lint.yml`で同じチェックが自動実行されます。

## GitHub Pages公開方法

1. GitHubにリポジトリを作成します。
2. このディレクトリをpushします。
3. GitHubの`Settings > Pages`を開きます。
4. Sourceを`Deploy from a branch`にします。
5. Branchを`main`、Folderを`/root`にします。
6. 表示された公開URLをLINEリッチメニューの「豆診断」に設定します。

## 商品追加方法

`products.json`の`products`配列へ商品オブジェクトを追加します。

必須項目:

- `id`
- `name`
- `category`
- `roast`
- `description`
- `price`
- `image_url`
- `square_url`
- `flavor_tags`
- `acid_level`
- `body_level`
- `sweetness_level`
- `bitter_level`
- `recommended_for`
- `decaf`
- `recommend_enabled`
- `available`

`recommend_enabled`が`false`の商品、または`available`が`false`の商品は診断結果から除外されます。

## JSON編集方法

味覚レベルは1から5を基準にします。

- `acid_level`: 酸味
- `body_level`: コク
- `sweetness_level`: 甘み
- `bitter_level`: 苦味

未設定の商品は後続Phaseの正規化処理で`null`とTODOを付与する想定です。現在の診断では`null`の項目は加点されません。

## Square URL更新方法

各商品の`square_url`を実際のSquareオンラインショップの商品ページURLへ変更します。

```json
"square_url": "https://example.com/square/product"
```

## 診断ロジック変更方法

`app.js`の以下の関数を編集します。

- `scoreProduct(product, answers)`
- `recommendProducts(products, answers)`
- `scoreByHighValue(value, weight)`
- `scoreByLowValue(value, weight)`
- `roastMatches(roast, answer)`

質問文や選択肢は`questions`配列で管理しています。

現在は「探しているのはドリップバッグですか？」の質問で、ドリップバッグ希望の場合にドリップバッグアソートBOXを強く優先します。

## クローラー実行方法

Squareオンラインショップの一覧ページ、カテゴリページ、または商品ページURLから初期商品データを生成します。

```txt
crawler/crawl_products.py
crawler/normalize_products.py
```

実行例:

```bash
python3 crawler/crawl_products.py "https://www.nagisa-coffee.jp/"
python3 crawler/normalize_products.py
```

`crawl_products.py`は`raw_products.json`を出力します。Square Onlineの公開ストアAPI、JSON-LD、OpenGraph、商品リンクを順に利用して取得します。

`normalize_products.py`は`raw_products.json`を`products.json`形式へ変換します。ワークショップ、送料、ギフトボックスなど診断対象外の商品は`recommend_enabled=false`にします。ドリップバッグアソートBOXは診断対象として扱います。

味覚レベル、焙煎度、タグは商品名・説明文・Squareカテゴリから初期推定します。

- `acid_level`: 1から5で推定
- `body_level`: 1から5で推定
- `sweetness_level`: 1から5で推定
- `bitter_level`: 1から5で推定
- `decaf`: 商品名、説明、タグから推定
- `recommend_enabled`: 診断対象商品は`true`、対象外商品は`false`

未レビュー項目は`todo`配列に残ります。公開前に人が確認し、味覚レベル、焙煎度、タグを整えてください。

## GitHub更新方法

```bash
git status
git add .
git commit -m "Add bean navi static diagnosis app"
git push origin main
```

## FastAPIへ移行する方法

静的版ではブラウザ内の`app.js`で診断しています。FastAPI化する場合は、次の分担に変更します。

- フロントエンド: 回答をAPIへ送信
- FastAPI: `products.json`を読み込み、診断ロジックを実行
- レスポンス: おすすめ上位3商品をJSONで返却

`scoreProduct`と`recommendProducts`の考え方をAPI側へ移植すれば、商品DBの構造は維持できます。

## NagisaConnectへ統合する方法

NagisaConnect側でも`products.json`の構造を維持します。OpenAI APIへ渡す情報として、特に次の項目を充実させます。

- `description`
- `flavor_tags`
- `recommended_for`

将来はLINE、Square、店頭QR、Instagram、音声接客から同じ商品DBと推薦ロジックを参照する構成にします。
