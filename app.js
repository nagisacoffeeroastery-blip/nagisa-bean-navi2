const DATA_URL = "./products.json";
const MAX_RESULTS = 3;

const questions = [
  {
    id: "taste",
    title: "どんな味が好きですか？",
    answers: ["すっきり", "コク", "甘み", "苦味"],
  },
  {
    id: "acid",
    title: "酸味は？",
    answers: ["好き", "普通", "苦手"],
  },
  {
    id: "drink",
    title: "飲み方",
    answers: ["ブラック", "ミルク", "アイス", "デカフェ"],
  },
  {
    id: "roast",
    title: "焙煎度",
    answers: ["浅煎り", "中煎り", "深煎り", "おまかせ"],
  },
  {
    id: "purpose",
    title: "用途",
    answers: ["自宅", "ギフト", "初めて", "いつもと違う豆"],
  },
  {
    id: "format",
    title: "探しているのはドリップバッグですか？",
    answers: ["はい", "いいえ", "どちらでも"],
  },
];

const roastLabels = new Map([
  ["Light", "浅煎り"],
  ["Medium", "中煎り"],
  ["High", "中煎り"],
  ["City", "中深煎り"],
  ["Full City", "深煎り"],
  ["French", "深煎り"],
  ["Italian", "深煎り"],
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

  if (answers.format === "はい") {
    score += isDripBag ? 80 : -40;
    addReason(reasons, isDripBag ? "手軽に楽しめるドリップバッグを優先しました。" : "");
  }

  if (answers.format === "いいえ") {
    score += isDripBag ? -25 : 6;
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

  if (answers.drink === "デカフェ") {
    score += product.decaf ? 50 : -30;
    addReason(reasons, product.decaf ? "デカフェ希望を最優先しました。" : "");
  }

  if (answers.roast !== "おまかせ") {
    score += roastMatches(product.roast, answers.roast) ? 8 : 0;
  } else {
    score += 2;
  }

  if (answers.purpose) {
    score += recommendedFor.includes(answers.purpose) ? 5 : 0;
    if (answers.purpose === "ギフト" && isDripBag) score += 12;
  }

  return { score, reasons: reasons.filter(Boolean) };
}

/**
 * Builds ranked recommendation results.
 * @param {Array<object>} products
 * @param {Record<string, string>} answers
 * @returns {Array<object>}
 */
function recommendProducts(products, answers) {
  return getRecommendableProducts(products)
    .map((product) => {
      const result = scoreProduct(product, answers);
      return { ...product, score: result.score, reasons: result.reasons };
    })
    .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, "ja"))
    .slice(0, MAX_RESULTS);
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
  return ["Full City", "French", "Italian"].includes(roast);
}

/**
 * Checks whether a product roast matches the answer label.
 * @param {string} roast
 * @param {string} answer
 * @returns {boolean}
 */
function roastMatches(roast, answer) {
  const label = roastLabels.get(roast) ?? roast;
  if (answer === "中煎り") {
    return ["中煎り", "中深煎り"].includes(label);
  }
  return label === answer;
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
