const DATA_URL = "./products.json";
const MAX_RESULTS = 3;

const questions = [
  {
    id: "type",
    title: "なにをお探しですか？",
    answers: ["コーヒー豆", "ドリップバッグ", "定期便", "ワークショップ"],
  },
  {
    id: "purpose",
    title: "どんな目的で選びますか？",
    answers: ["自宅", "ギフト", "初めて", "いつもと違うもの"],
  },
  {
    id: "mood",
    title: "どんな出会いがいいですか？",
    answers: ["定番人気", "ちょっと個性的", "季節限定", "おまかせ"],
  },
  {
    id: "taste",
    title: "どんな味が好きですか？",
    answers: ["すっきり", "コク", "甘み", "苦味", "フルーティ"],
  },
  {
    id: "acid",
    title: "酸味は？",
    answers: ["好き", "普通", "苦手"],
  },
  {
    id: "drink",
    title: "飲み方",
    answers: ["ブラック", "ミルク", "アイス", "どれでも"],
  },
  {
    id: "caffeine",
    title: "カフェインは気にしますか？",
    answers: ["気にしない", "デカフェがいい", "夜にも飲みたい", "半分くらい控えたい"],
  },
  {
    id: "roast",
    title: "焙煎度",
    answers: ["おまかせ", "浅煎り", "中煎り", "中深煎り", "深煎り"],
  },
];

const roastLabels = new Map([
  ["Light", "1: LIGHT ROAST"],
  ["Cinnamon", "2: CINNAMON ROAST"],
  ["Medium", "3: MEDIUM ROAST"],
  ["High", "4: HIGH ROAST"],
  ["City", "5: CITY ROAST"],
  ["Full City", "6: FULLCITY ROAST"],
  ["French", "7: FRENCH ROAST"],
  ["Italian", "8: ITALIAN ROAST"],
]);

const roastLevels = new Map([
  ["Light", 1],
  ["Cinnamon", 2],
  ["Medium", 3],
  ["High", 4],
  ["City", 5],
  ["Full City", 6],
  ["French", 7],
  ["Italian", 8],
]);

const roastGroups = new Map([
  ["浅煎り", [1, 2]],
  ["中煎り", [3, 4]],
  ["中深煎り", [5, 6]],
  ["深煎り", [7, 8]],
]);

const state = {
  products: [],
  currentStep: 0,
  answers: {},
};

const elements = {
  home: document.querySelector(".hero"),
  startButton: document.querySelector("#start-button"),
  quizPanel: document.querySelector("#quiz-panel"),
  stepLabel: document.querySelector("#step-label"),
  progressBar: document.querySelector("#progress-bar"),
  questionTitle: document.querySelector("#question-title"),
  answerGrid: document.querySelector("#answer-grid"),
  backButton: document.querySelector("#back-button"),
  loadingPanel: document.querySelector("#loading-panel"),
  resultsPanel: document.querySelector("#results-panel"),
  resultList: document.querySelector("#result-list"),
  restartButton: document.querySelector("#restart-button"),
  errorPanel: document.querySelector("#error-panel"),
  retryButton: document.querySelector("#retry-button"),
};

/**
 * Loads product data from the JSON master file.
 * @returns {Promise<Array<object>>}
 */
async function loadProducts() {
  const response = await fetch(DATA_URL, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`products.json could not be loaded: ${response.status}`);
  }

  const data = await response.json();
  return Array.isArray(data) ? data : data.products;
}

/**
 * Keeps products that can currently be recommended.
 * @param {Array<object>} products
 * @returns {Array<object>}
 */
function getRecommendableProducts(products) {
  return products.filter((product) => product.recommend_enabled && product.available);
}

/**
 * Scores one product for the user's answers.
 * @param {object} product
 * @param {Record<string, string>} answers
 * @returns {{ score: number, reasons: string[] }}
 */
function scoreProduct(product, answers) {
  let score = 0;
  const reasons = [];
  const tags = product.flavor_tags ?? [];
  const recommendedFor = product.recommended_for ?? [];
  const isDripBag = productMatches(product, "ドリップバッグ");
  const isBean = !isDripBag && !product.workshop && !product.subscription;

  if (answers.type === "コーヒー豆") {
    score += isBean ? 60 : -40;
  }
  if (answers.type === "ドリップバッグ") {
    score += isDripBag ? 85 : -45;
    addReason(reasons, isDripBag ? "手軽に楽しめるドリップバッグを優先しました。" : "");
  }
  if (answers.type === "定期便") {
    score += product.subscription ? 90 : -45;
    addReason(reasons, product.subscription ? "定期便として続けやすい商品を優先しました。" : "");
  }
  if (answers.type === "ワークショップ") {
    score += product.workshop ? 95 : -55;
    addReason(reasons, product.workshop ? "コーヒーを体験しながら学べるワークショップです。" : "");
  }

  if (answers.mood === "定番人気") {
    score += salesScore(product) * 0.18;
    score += product.priority ? product.priority * 0.06 : 0;
    addReason(reasons, "定番人気と選びやすさを加味しました。");
  }
  if (answers.mood === "ちょっと個性的") {
    score += tags.some((tag) => ["⭐️個性派・スペシャル", "華やか", "果実感"].includes(tag)) ? 14 : 0;
  }
  if (answers.mood === "季節限定") {
    score += product.seasonal ? 32 : -6;
    addReason(reasons, product.seasonal ? "季節限定の商品を優先しました。" : "");
  }

  if (answers.taste === "すっきり") {
    score += scoreByLowValue(product.body_level, 4);
    score += scoreByHighValue(product.acid_level, 2);
    if (tags.includes("すっきり")) score += 3;
  }

  if (answers.taste === "コク") {
    score += scoreByHighValue(product.body_level, 5);
    if (tags.includes("コク")) score += 3;
  }

  if (answers.taste === "甘み") {
    score += scoreByHighValue(product.sweetness_level, 5);
    if (tags.includes("甘み")) score += 3;
  }

  if (answers.taste === "苦味") {
    score += scoreByHighValue(product.bitter_level, 5);
    if (tags.includes("苦味")) score += 3;
  }

  if (answers.taste === "フルーティ") {
    score += scoreByHighValue(product.acid_level, 3);
    score += scoreByHighValue(product.sweetness_level, 3);
    if (tags.includes("果実感") || tags.includes("華やか")) score += 8;
  }

  if (answers.acid === "好き") {
    score += scoreByHighValue(product.acid_level, 5);
    addReason(reasons, "酸味のある味わいが好みに合いそうです。");
  }

  if (answers.acid === "普通") {
    score += scoreByMiddleValue(product.acid_level, 3);
    addReason(reasons, "酸味と飲みやすさのバランスを見て選びました。");
  }

  if (answers.acid === "苦手") {
    score += scoreByLowValue(product.acid_level, 5);
    if (recommendedFor.includes("酸味苦手")) score += 4;
    addReason(reasons, "酸味が穏やかな豆を優先しています。");
  }

  if (answers.drink === "ブラック") {
    score += recommendedFor.includes("ブラック") ? 5 : 0;
    score += scoreByHighValue(product.sweetness_level, 2);
    addReason(reasons, "ブラックで香りや甘みを楽しみやすい豆です。");
  }

  if (answers.drink === "ミルク") {
    score += scoreByHighValue(product.body_level, 5);
    score += recommendedFor.includes("ミルク") ? 5 : 0;
    addReason(reasons, "ミルクと合わせても味がぼやけにくい豆です。");
  }

  if (answers.drink === "アイス") {
    score += isDarkRoast(product.roast) ? 6 : 0;
    score += scoreByHighValue(product.bitter_level, 3);
    addReason(reasons, "アイスでも輪郭が出やすい味わいです。");
  }

  if (answers.drink === "どれでも") {
    score += 2;
  }

  if (answers.caffeine === "デカフェがいい") {
    score += product.decaf ? 55 : -35;
    addReason(reasons, product.decaf ? "デカフェ希望を優先しました。" : "");
  }

  if (answers.caffeine === "夜にも飲みたい") {
    score += product.decaf ? 35 : 0;
    score += productMatches(product, "夜") ? 18 : 0;
    addReason(reasons, product.decaf || productMatches(product, "夜") ? "夜にも選びやすいカフェイン控えめの商品です。" : "");
  }

  if (answers.caffeine === "半分くらい控えたい") {
    score += productMatches(product, "デカフェ比率 50") ? 38 : 0;
    score += productMatches(product, "デカフェ比率 30") ? 24 : 0;
    score += product.decaf ? 10 : 0;
  }

  if (answers.roast !== "おまかせ") {
    score += roastMatches(product.roast, answers.roast) ? 10 : 0;
  } else {
    score += 2;
  }

  if (answers.purpose) {
    score += recommendedFor.includes(answers.purpose) ? 5 : 0;
    if (answers.purpose === "いつもと違うもの") {
      score += product.seasonal ? 10 : 0;
      score += tags.includes("⭐️個性派・スペシャル") ? 12 : 0;
    }
    if (answers.purpose === "ギフト" && isDripBag) score += 12;
  }

  score += priorityScore(product);

  return { score, reasons: reasons.filter(Boolean) };
}

/**
 * Builds ranked recommendation results.
 * @param {Array<object>} products
 * @param {Record<string, string>} answers
 * @returns {Array<object>}
 */
function recommendProducts(products, answers) {
  return getEligibleProducts(getRecommendableProducts(products), answers)
    .map((product) => {
      const result = scoreProduct(product, answers);
      return { ...product, score: result.score, reasons: result.reasons };
    })
    .sort(compareProducts)
    .slice(0, MAX_RESULTS);
}

/**
 * Narrows products to the roast family selected by the user.
 * @param {Array<object>} products
 * @param {Record<string, string>} answers
 * @returns {Array<object>}
 */
function getEligibleProducts(products, answers) {
  if (answers.type === "ドリップバッグ") {
    const dripBagProducts = products.filter((product) => productMatches(product, "ドリップバッグ"));
    return filterByRoast(dripBagProducts.length > 0 ? dripBagProducts : products, answers);
  }

  const caffeineMatchedProducts = decafOnlySelected(answers)
    ? products.filter((product) => product.decaf)
    : products;

  return filterByRoast(caffeineMatchedProducts, answers);
}

/**
 * Narrows products to the selected roast family.
 * @param {Array<object>} products
 * @param {Record<string, string>} answers
 * @returns {Array<object>}
 */
function filterByRoast(products, answers) {
  if (!answers.roast || answers.roast === "おまかせ") {
    return products;
  }

  const roastMatchedProducts = products.filter((product) => roastMatches(product.roast, answers.roast));
  return roastMatchedProducts.length > 0 ? roastMatchedProducts : products;
}

/**
 * Returns whether the user explicitly selected decaf.
 * @param {Record<string, string>} answers
 * @returns {boolean}
 */
function decafOnlySelected(answers) {
  return answers.caffeine === "デカフェがいい" && answers.type !== "ドリップバッグ";
}

/**
 * Sorts recommendations by diagnosis fit, shop priority, and sales signal.
 * @param {object} a
 * @param {object} b
 * @returns {number}
 */
function compareProducts(a, b) {
  return (
    b.score - a.score
    || (b.priority ?? 0) - (a.priority ?? 0)
    || salesScore(b) - salesScore(a)
    || salesRank(a) - salesRank(b)
    || a.name.localeCompare(b.name, "ja")
  );
}

/**
 * Checks whether a product has a keyword in searchable display fields.
 * @param {object} product
 * @param {string} keyword
 * @returns {boolean}
 */
function productMatches(product, keyword) {
  return [product.name, product.category, product.description, ...(product.flavor_tags ?? []), ...(product.recommended_for ?? [])]
    .filter(Boolean)
    .some((value) => String(value).includes(keyword));
}

/**
 * Converts store priority into a modest score bonus.
 * @param {object} product
 * @returns {number}
 */
function priorityScore(product) {
  return Number.isFinite(product.priority) ? product.priority * 0.04 : 0;
}

/**
 * Returns a normalized sales score.
 * @param {object} product
 * @returns {number}
 */
function salesScore(product) {
  return Number.isFinite(product.sales_score) ? product.sales_score : 0;
}

/**
 * Returns sales rank, with unrated items sorted after ranked items.
 * @param {object} product
 * @returns {number}
 */
function salesRank(product) {
  return Number.isFinite(product.sales_rank) ? product.sales_rank : Number.MAX_SAFE_INTEGER;
}

/**
 * Converts a high numeric attribute into score.
 * @param {number | null} value
 * @param {number} weight
 * @returns {number}
 */
function scoreByHighValue(value, weight) {
  return Number.isFinite(value) ? value * weight : 0;
}

/**
 * Converts a low numeric attribute into score.
 * @param {number | null} value
 * @param {number} weight
 * @returns {number}
 */
function scoreByLowValue(value, weight) {
  return Number.isFinite(value) ? (5 - value) * weight : 0;
}

/**
 * Scores values close to a preferred middle point.
 * @param {number | null} value
 * @param {number} target
 * @returns {number}
 */
function scoreByMiddleValue(value, target) {
  return Number.isFinite(value) ? Math.max(0, 5 - Math.abs(value - target) * 2) : 0;
}

/**
 * Adds a recommendation reason once.
 * @param {string[]} reasons
 * @param {string} reason
 */
function addReason(reasons, reason) {
  if (reason && !reasons.includes(reason)) {
    reasons.push(reason);
  }
}

/**
 * Checks whether the roast is generally dark.
 * @param {string} roast
 * @returns {boolean}
 */
function isDarkRoast(roast) {
  return roastLevel(roast) >= 6;
}

/**
 * Checks whether a product roast matches the selected roast family.
 * @param {string} roast
 * @param {string} answer
 * @returns {boolean}
 */
function roastMatches(roast, answer) {
  const allowedLevels = roastGroups.get(answer);
  return allowedLevels ? allowedLevels.includes(roastLevel(roast)) : false;
}

/**
 * Returns a roast level from 1 to 8.
 * @param {string} roast
 * @returns {number}
 */
function roastLevel(roast) {
  return roastLevels.get(roast) ?? 5;
}

/**
 * Shows one screen and hides the rest.
 * @param {HTMLElement} screen
 */
function showScreen(screen) {
  [elements.home, elements.quizPanel, elements.loadingPanel, elements.resultsPanel, elements.errorPanel].forEach((element) => {
    element.classList.toggle("is-hidden", element !== screen);
  });
}

function renderQuestion() {
  const question = questions[state.currentStep];
  elements.stepLabel.textContent = `質問 ${state.currentStep + 1} / ${questions.length}`;
  elements.progressBar.style.width = `${((state.currentStep + 1) / questions.length) * 100}%`;
  elements.questionTitle.textContent = question.title;
  elements.backButton.classList.toggle("is-hidden", state.currentStep === 0);
  elements.answerGrid.replaceChildren(
    ...question.answers.map((answer) => {
      const button = document.createElement("button");
      button.className = "answer-button";
      button.type = "button";
      button.textContent = answer;
      button.addEventListener("click", () => selectAnswer(question.id, answer));
      return button;
    }),
  );
}

/**
 * Stores an answer and moves to the next step or result.
 * @param {string} questionId
 * @param {string} answer
 */
function selectAnswer(questionId, answer) {
  state.answers[questionId] = answer;

  if (state.currentStep < questions.length - 1) {
    state.currentStep += 1;
    renderQuestion();
    return;
  }

  showLoadingThenResults();
}

function startQuiz() {
  state.currentStep = 0;
  state.answers = {};
  renderQuestion();
  showScreen(elements.quizPanel);
}

function goBack() {
  if (state.currentStep === 0) return;
  state.currentStep -= 1;
  renderQuestion();
}

function showLoadingThenResults() {
  showScreen(elements.loadingPanel);
  window.setTimeout(() => {
    renderResults(recommendProducts(state.products, state.answers));
    showScreen(elements.resultsPanel);
  }, 650);
}

/**
 * Renders recommendation cards.
 * @param {Array<object>} results
 */
function renderResults(results) {
  if (results.length === 0) {
    elements.resultList.replaceChildren(createEmptyResult());
    return;
  }

  elements.resultList.replaceChildren(
    ...results.map((product, index) => createResultCard(product, index + 1)),
  );
}

/**
 * Creates one result card.
 * @param {object} product
 * @param {number} rank
 * @returns {HTMLElement}
 */
function createResultCard(product, rank) {
  const card = document.createElement("article");
  card.className = "result-card";

  const image = document.createElement("img");
  image.className = "product-image";
  image.src = product.image_url;
  image.alt = product.name;
  image.loading = "lazy";

  const body = document.createElement("div");
  body.className = "product-body";

  const badge = document.createElement("span");
  badge.className = "rank";
  badge.textContent = `第${rank}位`;

  const title = document.createElement("h3");
  title.textContent = product.name;

  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = `${product.category} / ${roastLabels.get(product.roast) ?? product.roast}`;

  const description = document.createElement("p");
  description.className = "description";
  description.textContent = truncateText(product.description, 118);

  const reason = document.createElement("p");
  reason.className = "reason";
  reason.textContent = product.reasons?.[0] ?? "回答に近い味わいと用途から選びました。";

  const tags = document.createElement("ul");
  tags.className = "tags";
  for (const tag of product.flavor_tags ?? []) {
    const item = document.createElement("li");
    item.textContent = tag;
    tags.append(item);
  }

  const link = document.createElement("a");
  link.className = "product-link";
  link.href = product.square_url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "商品を見る";

  body.append(badge, title, meta, description, reason, tags, link);
  card.append(image, body);
  return card;
}

/**
 * Truncates long product copy for compact result cards.
 * @param {string} text
 * @param {number} maxLength
 * @returns {string}
 */
function truncateText(text, maxLength) {
  if (!text || text.length <= maxLength) {
    return text ?? "";
  }
  return `${text.slice(0, maxLength).trim()}...`;
}

/**
 * Creates a fallback result when no product can be recommended.
 * @returns {HTMLElement}
 */
function createEmptyResult() {
  const panel = document.createElement("div");
  panel.className = "panel";
  const title = document.createElement("h2");
  title.textContent = "おすすめ対象の商品がありません";
  const text = document.createElement("p");
  text.textContent = "販売状況を確認してから、もう一度お試しください。";
  panel.append(title, text);
  return panel;
}

async function initialize() {
  try {
    state.products = await loadProducts();
    elements.startButton.disabled = false;
    showScreen(elements.home);
  } catch (error) {
    console.error(error);
    showScreen(elements.errorPanel);
  }
}

elements.startButton.addEventListener("click", startQuiz);
elements.backButton.addEventListener("click", goBack);
elements.restartButton.addEventListener("click", startQuiz);
elements.retryButton.addEventListener("click", initialize);

initialize();
