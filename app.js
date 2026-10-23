const isSeparateLocalFrontend = ["127.0.0.1", "localhost"].includes(window.location.hostname)
    && window.location.port === "5500";
const SERVER_URL = isSeparateLocalFrontend ? "http://127.0.0.1:8001" : window.location.origin;

// 전역 변수
let selectedImageFile = null,
    loadedImage = null,
    cropRect = null,
    dragStart = null;
let extractedGraphData = [],
    extractedPoints = [],
    stockData = [],
    stockCandles = [],
    currentStockPayload = null,
    stockVolumes = [],
    voices = [],
    stockChartInstance = null;
const rankingNameBySymbol = new Map();
const rankingSymbolByName = new Map();
const rankingFilters = { type: "MARKET_TRADING_AMOUNT", marketCountry: "KR", duration: "realtime" };
let rankingRequestId = 0, dataRequestId = 0;
let lastStockRequest = null, stockRefreshInProgress = false;
const INTERVAL_LABELS = { "1m": "1분봉", "5m": "5분봉", "15m": "15분봉", "60m": "60분봉", "1d": "일봉" };

let activeSeries = null,
    playbackSpeed = 1,
    spatialAudioUrl = null,
    pendingSeekIndex = null,
    speechRequestId = 0;

const BASE_PLAYBACK_SECONDS = 8;
const SPEED_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];

// DOM 요소
const canvas = document.getElementById("imageCanvas"),
      ctx = canvas.getContext("2d"),
      canvasWrap = document.getElementById("canvasWrap");
const chartTypeSelect = document.getElementById("chartTypeSelect"),
      candleColorSelect = document.getElementById("candleColorSelect"),
      candleGuide = document.getElementById("candleGuide");

// 음성 설정
if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = () => {
    voices = window.speechSynthesis.getVoices();
};

// UI 이벤트 리스너
document.getElementById("contrastToggle").addEventListener("change", e => {
    document.body.classList.toggle("high-contrast", e.target.checked);
});

document.getElementById("freqSlider").addEventListener("input", e => {
    document.getElementById("freqVal").innerText = e.target.value;
});

document.getElementById("minFreqSlider").addEventListener("input", e => {
    document.getElementById("minFreqVal").innerText = e.target.value;
});

document.getElementById("minAmplitudeSlider").addEventListener("input", e => {
    document.getElementById("minAmplitudeVal").innerText = Math.round(Number(e.target.value) * 100);
});

document.getElementById("maxAmplitudeSlider").addEventListener("input", e => {
    document.getElementById("maxAmplitudeVal").innerText = Math.round(Number(e.target.value) * 100);
});

document.getElementById("masterVolumeSlider").addEventListener("input", e => {
    document.getElementById("masterVolumeVal").innerText = Math.round(Number(e.target.value) * 100);
    document.getElementById("spatialAudio").volume = Number(e.target.value);
});

["minFreqSlider", "freqSlider", "minAmplitudeSlider", "maxAmplitudeSlider"].forEach(id => {
    document.getElementById(id).addEventListener("change", () => {
        if (activeSeries) rebuildActiveAudio(true).catch(error => {
            document.getElementById("playbackState").innerText = error.message;
        });
    });
});

document.getElementById("waveSelect").addEventListener("change", () => {
    if (extractedGraphData.length > 0) prepareGraphAudio();
    if (activeSeries) rebuildActiveAudio(true);
});

const STOCK_SYMBOLS = {
    "삼성전자": "005930", "005930": "005930",
    "sk하이닉스": "000660", "000660": "000660",
    "naver": "035420", "035420": "035420",
    "카카오": "035720", "035720": "035720",
    "lg화학": "051910", "051910": "051910",
    "애플": "AAPL", "aapl": "AAPL",
    "마이크로소프트": "MSFT", "msft": "MSFT",
    "엔비디아": "NVDA", "nvda": "NVDA",
    "테슬라": "TSLA", "tsla": "TSLA"
};

document.getElementById("loadStockBtn").addEventListener("click", () => loadStockData(false));
document.getElementById("refreshStockBtn").addEventListener("click", () => loadStockData(false));
document.getElementById("stockService").after(document.getElementById("marketTools"));
loadStockRankings();

document.getElementById("readStockBtn").addEventListener("click", readStockSummary);
document.getElementById("refreshRankingsBtn").addEventListener("click", loadStockRankings);
document.querySelectorAll(".market-tab").forEach(button => {
    button.addEventListener("click", () => {
        rankingFilters.marketCountry = button.dataset.market;
        setActiveRankingButtons(".market-tab", "market", rankingFilters.marketCountry);
        loadStockRankings();
    });
});
document.querySelectorAll(".ranking-tab").forEach(button => {
    button.addEventListener("click", () => {
        rankingFilters.type = button.dataset.rankingType;
        setActiveRankingButtons(".ranking-tab", "rankingType", rankingFilters.type);
        loadStockRankings();
    });
});
document.getElementById("rankingDuration").addEventListener("change", event => {
    rankingFilters.duration = event.target.value;
    loadStockRankings();
});

function setActiveRankingButtons(selector, dataKey, value) {
    document.querySelectorAll(selector).forEach(button => {
        const active = button.dataset[dataKey] === value;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
    });
}

function formatRankingMetric(item, rankingType) {
    if (rankingType.includes("TRADING_VOLUME")) {
        return `거래량 ${new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 }).format(item.trading_volume)}주`;
    }
    return `거래대금 ${new Intl.NumberFormat("ko-KR", {
        style: "currency", currency: item.currency, notation: "compact", maximumFractionDigits: 1
    }).format(item.trading_amount)}`;
}

function renderStockRankings(payload) {
    const list = document.getElementById("rankingList");
    const suggestions = document.getElementById("stockSuggestions");
    list.replaceChildren();
    suggestions.querySelectorAll("option[data-ranking]").forEach(option => option.remove());
    payload.rankings.forEach(item => {
        rankingNameBySymbol.set(item.symbol, { name: item.name, currency: item.currency });
        rankingSymbolByName.set(item.name.toLowerCase(), item.symbol);
        const option = document.createElement("option");
        option.value = item.name;
        option.label = item.symbol;
        option.dataset.ranking = "true";
        suggestions.appendChild(option);

        const row = document.createElement("li");
        const button = document.createElement("button");
        const sign = item.change_percent > 0 ? "+" : "";
        const changeText = `${sign}${item.change_percent.toFixed(2)}%`;
        button.type = "button";
        button.className = "ranking-item";
        button.dataset.symbol = item.symbol;
        button.setAttribute("aria-label", `${item.rank}위 ${item.name}, 현재가 ${formatPrice(item.last_price, item.currency)}, 등락률 ${changeText}, ${formatRankingMetric(item, payload.type)}. 차트 조회`);

        const rank = document.createElement("strong");
        rank.className = "ranking-rank";
        rank.innerText = `${item.rank}위`;
        const identity = document.createElement("span");
        identity.className = "ranking-identity";
        const name = document.createElement("strong");
        name.innerText = item.name;
        const symbol = document.createElement("small");
        symbol.innerText = item.symbol;
        identity.append(name, symbol);
        const priceText = document.createElement("strong");
        priceText.className = "ranking-price";
        priceText.innerText = formatPrice(item.last_price, item.currency);
        const change = document.createElement("strong");
        change.className = `ranking-change ${item.change_percent > 0 ? "up" : item.change_percent < 0 ? "down" : ""}`;
        change.innerText = changeText;
        const metric = document.createElement("span");
        metric.className = "ranking-metric";
        metric.innerText = formatRankingMetric(item, payload.type);
        button.append(rank, identity, priceText, change, metric);
        button.addEventListener("click", async () => {
            list.querySelectorAll(".ranking-item").forEach(other => other.removeAttribute("aria-current"));
            button.setAttribute("aria-current", "true");
            document.getElementById("stockSearch").value = item.symbol;
            document.getElementById("rankingStatus").innerText = `${item.name} 종목을 선택했습니다. 차트를 불러오는 중입니다.`;
            await loadStockData(false);
            if (currentStockPayload?.symbol === item.symbol) {
                document.getElementById("stockResults").scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
        button.addEventListener("keydown", event => {
            const buttons = [...list.querySelectorAll(".ranking-item")];
            const index = buttons.indexOf(button);
            let targetIndex = null;
            if (event.key === "ArrowDown") targetIndex = Math.min(buttons.length - 1, index + 1);
            if (event.key === "ArrowUp") targetIndex = Math.max(0, index - 1);
            if (event.key === "Home") targetIndex = 0;
            if (event.key === "End") targetIndex = buttons.length - 1;
            if (targetIndex !== null) {
                event.preventDefault();
                event.stopPropagation();
                buttons[targetIndex].focus();
            }
        });
        row.appendChild(button);
        list.appendChild(row);
    });
}

async function loadStockRankings() {
    const durationSelect = document.getElementById("rankingDuration");
    const status = document.getElementById("rankingStatus");
    const browser = document.querySelector(".ranking-browser");
    const refreshButton = document.getElementById("refreshRankingsBtn");
    const requestId = ++rankingRequestId;
    const type = rankingFilters.type;
    const marketCountry = rankingFilters.marketCountry;
    let duration = rankingFilters.duration;
    let durationNotice = "";
    if (["TOP_GAINERS", "TOP_LOSERS"].includes(type) && duration === "realtime") {
        duration = "1d";
        rankingFilters.duration = duration;
        durationSelect.value = "1d";
        durationNotice = "급등락 순위는 실시간 산정을 지원하지 않아 1일 기준으로 변경했습니다. ";
    }
    document.getElementById("rankingMetricHeading").innerText = type.includes("TRADING_VOLUME") ? "거래량" : "거래대금";
    status.innerText = `${durationNotice}종목 순위를 불러오는 중입니다.`;
    browser.setAttribute("aria-busy", "true");
    refreshButton.disabled = true;
    try {
        const params = new URLSearchParams({ type, market_country: marketCountry, duration, count: "10" });
        const response = await fetch(`${SERVER_URL}/stock-rankings?${params}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "종목 순위를 불러오지 못했습니다.");
        if (requestId !== rankingRequestId) return;
        renderStockRankings(payload);
        const rankedAt = payload.ranked_at ? formatTimestamp(payload.ranked_at) : "집계 시각 없음";
        status.innerText = payload.rankings.length
            ? `${durationNotice}${rankedAt} 기준 상위 ${payload.rankings.length}개 종목입니다.`
            : `${durationNotice}현재 조건에 집계된 종목이 없습니다.`;
    } catch (error) {
        if (requestId !== rankingRequestId) return;
        document.getElementById("rankingList").replaceChildren();
        const reason = error instanceof TypeError ? "서버에 연결할 수 없습니다." : error.message;
        status.innerText = `순위를 불러오지 못했습니다. ${reason} 종목명이나 코드를 직접 입력할 수도 있습니다.`;
    } finally {
        if (requestId === rankingRequestId) {
            browser.setAttribute("aria-busy", "false");
            refreshButton.disabled = false;
        }
    }
}

async function loadStockData(demo = false, background = false) {
    if (background && (!lastStockRequest || stockRefreshInProgress || !document.getElementById('spatialAudio').paused)) return;
    if (background) stockRefreshInProgress = true;
    const requestId = ++dataRequestId;
    const oldPosition = background ? chartNavigator.currentIndex : 0;
    if (!background) {
    stopAllAudio();
    audioRequestId++; audioReady = false; activeSeries = null; currentStockPayload = null;
    setPlayerControlsDisabled(true);
    document.getElementById('positionSlider').disabled = true;
    document.getElementById('stockResults').hidden = true;
    document.getElementById('stockSummary').textContent = '차트를 불러오는 중입니다.';
    document.getElementById('stockTimestamp').textContent = '';
    document.getElementById('currentPointDetail').textContent = '차트 로딩 후 현재 봉을 탐색할 수 있습니다.';
    document.getElementById('currentPosition').textContent = '위치 정보 없음';
    document.getElementById('activeSeriesLabel').textContent = '차트 로딩 중';
    }

    const query = document.getElementById("stockSearch").value.trim();
    const symbol = background ? lastStockRequest.symbol : STOCK_SYMBOLS[query.toLowerCase()] || STOCK_SYMBOLS[query] || rankingSymbolByName.get(query.toLowerCase()) || query.toUpperCase();
    const interval = background ? lastStockRequest.interval : document.getElementById("stockInterval").value;
    const count = background ? lastStockRequest.count : Number(document.getElementById("stockCount").value);
    const status = document.getElementById("stockStatus");
    const button = document.getElementById("loadStockBtn");
    if (!symbol) {
        status.innerText = "종목명이나 종목 코드를 입력하세요.";
        document.getElementById("stockSummary").textContent = "종목을 선택하세요.";
        document.getElementById("activeSeriesLabel").textContent = "종목을 선택하고 차트를 불러오세요.";
        document.getElementById("stockSearch").focus();
        return;
    }
    if (!background) {
        status.innerText = demo ? "샘플 데이터를 준비하는 중입니다." : "토스증권에서 실시간 데이터를 불러오는 중입니다.";
        button.disabled = true;
    }

    try {
        const params = new URLSearchParams({ symbol, interval, count: String(count), demo: String(demo) });
        const response = await fetch(`${SERVER_URL}/stock-candles?${params}`);
        const payload = await response.json();
        if (requestId !== dataRequestId) return;
        if (!response.ok) throw new Error(payload.detail || "주식 데이터를 불러오지 못했습니다.");
        if (background && currentStockPayload) {
            const previous = currentStockPayload.candles.at(-1);
            const latest = payload.candles.at(-1);
            if (previous?.timestamp === latest?.timestamp && previous?.close === latest?.close && previous?.volume === latest?.volume) {
                document.getElementById('stockRefreshStatus').textContent = `마지막 확인 ${new Date().toLocaleTimeString('ko-KR')}. 새 봉 없음. 최근 봉 ${formatTimestamp(latest.timestamp, payload.interval === '1d')}.`;
                return;
            }
            stopAllAudio();
        }
        const rankingMetadata = rankingNameBySymbol.get(payload.symbol);
        if (rankingMetadata) {
            payload.name = rankingMetadata.name;
            payload.currency = rankingMetadata.currency;
        }
        currentStockPayload = payload;
        stockData = payload.close_prices || [];
        stockCandles = payload.candles || [];
        stockVolumes = payload.volumes || stockCandles.map(candle => candle.volume);
        renderStockSummary(payload);
        document.getElementById("stockResults").hidden = false;
        const source = document.getElementById("stockSource");
        source.innerText = payload.source === "tossinvest" ? "토스증권 실데이터" : "샘플 체험 데이터";
        source.className = `source-badge ${payload.source === "tossinvest" ? "live" : "demo"}`;
        const firstCandle = stockCandles[0], lastCandle = stockCandles[stockCandles.length - 1];
        const largest = stockCandles.reduce((a,b) => Number(a.volume) > Number(b.volume) ? a : b);
        const change = (lastCandle.close / firstCandle.close - 1) * 100;
        document.getElementById("stockSummary").textContent = chartSummaryText({symbol:payload.name, timeframe:payload.interval}, {
            count:stockCandles.length, start:firstCandle.timestamp, end:lastCandle.timestamp,
            start_close:firstCandle.close, end_close:lastCandle.close, change_percent:change,
            high:Math.max(...stockCandles.map(c=>c.high)), low:Math.min(...stockCandles.map(c=>c.low)),
            max_volume:largest.volume, max_volume_timestamp:largest.timestamp,
            direction:change>0?'상승':change<0?'하락':'동일'
        }, payload.currency);
        try { renderStockChart(stockCandles, payload.name, payload.currency); } catch (_) { announce("시각 차트 표시 실패. 음향과 탐색은 사용할 수 있습니다."); }
        await prepareStockAudio();
        if (background) seekToIndex(Math.min(oldPosition, stockCandles.length - 1), false);
        else document.getElementById("playPauseBtn").focus();
        const derived = ['5m','15m','60m'].includes(interval) ? ' (실제 1분봉 합산)' : '';
        status.innerText = `${payload.name}, ${INTERVAL_LABELS[interval]}${derived} ${stockData.length}개를 불러왔습니다. 공간음향을 재생할 수 있습니다.`;
        document.getElementById('stockRefreshStatus').textContent = `${payload.source === 'tossinvest' ? '실데이터' : '샘플'} 마지막 확인 ${new Date().toLocaleTimeString('ko-KR')}. 최근 봉 ${formatTimestamp(payload.metrics.latest_timestamp, payload.interval === '1d')}. 실데이터는 1분마다 자동 확인합니다.`;
        lastStockRequest = {symbol, interval, count};
        document.getElementById('refreshStockBtn').disabled = false;
        document.getElementById("selectedStock").textContent = `선택 종목: ${payload.name} (${payload.symbol})`;
    } catch (error) {
        if (requestId !== dataRequestId) return;
        if (background) {
            document.getElementById('stockRefreshStatus').textContent = `자동 갱신 실패: ${error.message}. 이전 차트는 유지됩니다.`;
            console.error('[Chart refresh]', error);
            return;
        }
        stopAllAudio();
        activeSeries = null; audioReady = false; audioRequestId++;
        document.getElementById("spatialAudio").removeAttribute("src");
        document.getElementById("positionSlider").disabled = true;
        setPlayerControlsDisabled(true);
        currentStockPayload = null;
        document.getElementById('stockSummary').textContent = '차트를 불러오지 못했습니다.';
        document.getElementById('activeSeriesLabel').textContent = '차트를 다시 불러오세요.';
        stockData = [];
        stockCandles = [];
        stockVolumes = [];
        document.getElementById("stockResults").hidden = true;
        const source = document.getElementById("stockSource");
        source.innerText = "실데이터 연결 실패";
        source.className = "source-badge error";
        const reason = error instanceof TypeError
            ? "서버에 연결할 수 없습니다. 서버가 켜져 있는지 확인하세요."
            : error.message;
        status.innerText = `차트를 불러오지 못했습니다. ${reason}`;
        console.error("[Chart load]", error.message);
        document.getElementById("loadStockBtn").focus();
    } finally {
        if (!background) button.disabled = false;
        if (background) stockRefreshInProgress = false;

    }
}

function formatPrice(value, currency) {
    return new Intl.NumberFormat("ko-KR", {
        style: "currency", currency, maximumFractionDigits: currency === "KRW" ? 0 : 2
    }).format(value);
}

function renderStockSummary(payload) {
    const { metrics, currency } = payload;
    const sign = metrics.change > 0 ? "+" : "";
    document.getElementById("stockName").innerText = `${payload.name} (${payload.symbol})`;
    document.getElementById("metricLatest").innerText = formatPrice(metrics.latest, currency);
    document.getElementById("metricChange").innerText = `${sign}${formatPrice(metrics.change, currency)} (${sign}${metrics.change_percent.toFixed(2)}%)`;
    document.getElementById("metricChange").className = metrics.change > 0 ? "up" : metrics.change < 0 ? "down" : "";
    document.getElementById("metricHigh").innerText = formatPrice(metrics.high, currency);
    document.getElementById("metricLow").innerText = formatPrice(metrics.low, currency);
    document.getElementById("stockTimestamp").innerText = `최근 봉 시각: ${formatTimestamp(metrics.latest_timestamp, payload.interval === '1d')}`;
}

// Dates are written with Korean units ("2026년 10월 23일 오후 5시 47분") so that speech
// engines and screen readers announce them as dates. The compact "2026. 10. 23. 오후 5:47"
// form was read as a run of unrelated numbers.
function formatTimestamp(value, dateOnly = false) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    const day = `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`;
    if (dateOnly) return day;
    const hours = date.getHours(), minutes = date.getMinutes();
    const period = hours < 12 ? "오전" : "오후";
    const hour12 = hours % 12 || 12;
    return `${day} ${period} ${hour12}시${minutes ? ` ${minutes}분` : ""}`;
}

function readStockSummary() {
    if (!currentStockPayload) return;
    const percentage = currentStockPayload.metrics.change_percent;
    const text = `${currentStockPayload.name} ${INTERVAL_LABELS[currentStockPayload.interval]} 차트입니다. 전체 ${stockCandles.length}개의 봉이 있으며, 조회 기간 동안 종가가 ${Math.abs(percentage).toFixed(2)}퍼센트 ${percentage > 0 ? '상승' : percentage < 0 ? '하락' : '변동 없이 유지'}했습니다. 마지막 종가 ${formatPrice(currentStockPayload.metrics.latest, currentStockPayload.currency)}입니다.`;
    speakText(text);
}

function calculateMovingAverage(candles, period) {
    return candles.map((candle, index) => {
        if (index < period - 1) return { x: new Date(candle.timestamp).getTime(), y: null };
        const window = candles.slice(index - period + 1, index + 1);
        const average = window.reduce((sum, item) => sum + Number(item.close), 0) / period;
        return { x: new Date(candle.timestamp).getTime(), y: average };
    });
}

function renderStockChart(candles, name, currency) {
    if (typeof Chart === "undefined") return;
    if (stockChartInstance) stockChartInstance.destroy();
    const upColor = "#ef4444";
    const downColor = "#2563eb";
    const unchangedColor = "#64748b";
    const candleData = candles.map(candle => ({
        x: new Date(candle.timestamp).getTime(),
        o: Number(candle.open),
        h: Number(candle.high),
        l: Number(candle.low),
        c: Number(candle.close)
    }));
    const volumeData = candles.map(candle => ({
        x: new Date(candle.timestamp).getTime(),
        y: Number(candle.volume) || 0
    }));
    const volumeColors = candles.map(candle => Number(candle.close) > Number(candle.open)
        ? upColor : Number(candle.close) < Number(candle.open) ? downColor : unchangedColor);
    stockChartInstance = new Chart(document.getElementById("stockChart"), {
        type: "candlestick",
        data: {
            datasets: [
                {
                    type: "candlestick",
                    label: `${name} 캔들`,
                    data: candleData,
                    yAxisID: "priceAxis",
                    backgroundColors: { up: upColor, down: downColor, unchanged: unchangedColor },
                    borderColors: { up: upColor, down: downColor, unchanged: unchangedColor },
                    order: 2
                },
                {
                    type: "line",
                    label: "5봉 이동평균",
                    data: calculateMovingAverage(candles, 5),
                    yAxisID: "priceAxis",
                    borderColor: "#10b981",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: .18,
                    spanGaps: false,
                    order: 1
                },
                {
                    type: "line",
                    label: "20봉 이동평균",
                    data: calculateMovingAverage(candles, 20),
                    yAxisID: "priceAxis",
                    borderColor: "#f59e0b",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: .18,
                    spanGaps: false,
                    order: 1
                },
                {
                    type: "bar",
                    label: "거래량",
                    data: volumeData,
                    yAxisID: "volumeAxis",
                    backgroundColor: volumeColors,
                    borderWidth: 0,
                    barPercentage: .82,
                    categoryPercentage: .92,
                    order: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true, position: "top", align: "start" },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const raw = context.raw || {};
                            if (context.dataset.type === "candlestick") {
                                return [
                                    `시가 ${formatPrice(raw.o, currency)}`,
                                    `고가 ${formatPrice(raw.h, currency)}`,
                                    `저가 ${formatPrice(raw.l, currency)}`,
                                    `종가 ${formatPrice(raw.c, currency)}`
                                ];
                            }
                            if (context.dataset.label === "거래량") {
                                return `거래량 ${new Intl.NumberFormat("ko-KR").format(raw.y)}`;
                            }
                            return `${context.dataset.label} ${formatPrice(raw.y, currency)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: "timeseries",
                    offset: true,
                    time: { tooltipFormat: "yyyy. LL. dd. HH:mm" },
                    ticks: { source: "auto", maxRotation: 0, autoSkip: true },
                    grid: { color: "rgba(148, 163, 184, .18)" }
                },
                priceAxis: {
                    type: "linear",
                    position: "right",
                    stack: "stock",
                    stackWeight: 3,
                    title: { display: true, text: "가격 · Pitch" },
                    grid: { color: "rgba(148, 163, 184, .24)" }
                },
                volumeAxis: {
                    type: "linear",
                    position: "right",
                    stack: "stock",
                    stackWeight: 1,
                    beginAtZero: true,
                    title: { display: true, text: "거래량 · Volume" },
                    grid: { color: "rgba(148, 163, 184, .14)" },
                    ticks: {
                        callback(value) {
                            return Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 }).format(value);
                        }
                    }
                }
            }
        }
    });
}

async function prepareStockAudio() {
    if (!stockData.length) return;
    const usableVolumes = stockVolumes.length === stockData.length && stockVolumes.every(value => value != null && Number.isFinite(Number(value)))
        ? stockVolumes.map(Number) : null;
    await activateSeries({
        label: `${currentStockPayload.name} 종가와 거래량`,
        source: "stock",
        timeframe: currentStockPayload.interval,
        timestamps: stockCandles.map(candle => candle.timestamp),
        prices: stockData.map(Number),
        volumes: usableVolumes,
        candles: currentStockPayload.chart?.candles || stockCandles,
        priceLabel: "종가",
        volumeLabel: "거래량",
        currency: currentStockPayload.currency
    });
}

function setStatus(text) {
    document.getElementById("imageStatus").innerText = text;
}

function updateChartTypeUI() {
    const type = chartTypeSelect.value;
    const isCandle = type === "candlestick";
    candleColorSelect.disabled = !isCandle;
    candleGuide.hidden = !isCandle;
}

chartTypeSelect.addEventListener("change", updateChartTypeUI);
updateChartTypeUI();

// 이미지 업로드 처리
document.getElementById("imageInput").addEventListener("change", e => {
    const file = e.target.files[0];
    if (!file) return;
    
    selectedImageFile = file;
    const image = new Image();
    
    image.onload = () => {
        loadedImage = image;
        document.getElementById("roiWidth").value = image.width;
        document.getElementById("roiHeight").value = image.height;
        cropRect = null;
        extractedPoints = [];
        extractedGraphData = [];
        
        fitCanvasToImage(image);
        canvasWrap.hidden = false;
        renderDebugImage(null);
        drawImageCanvas();
        
        document.getElementById("analyzeImageBtn").disabled = false;
        setStatus("이미지가 업로드되었습니다. 결과가 이상하면 숫자 입력으로 가격 차트 영역을 조절하여 다시 분석하세요.");
    };
    image.src = URL.createObjectURL(file);
});

// 캔버스 크기 조정
function fitCanvasToImage(image) {
    const maxWidth = Math.min(900, document.querySelector(".panel").clientWidth - 48);
    const scale = Math.min(1, maxWidth / image.width);
    
    canvas.width = Math.round(image.width * scale);
    canvas.height = Math.round(image.height * scale);
    canvas.dataset.scale = scale;
}

// 캔버스 그리기 (이미지, 추출된 선, 크롭 영역)
function drawImageCanvas() {
    if (!loadedImage) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(loadedImage, 0, 0, canvas.width, canvas.height);
    
    if (extractedPoints.length > 1) {
        const scale = Number(canvas.dataset.scale || 1);
        ctx.save();
        ctx.lineWidth = 3;
        ctx.strokeStyle = "#d92828";
        ctx.beginPath();
        
        extractedPoints.forEach((p, i) => {
            const x = p.pixel_x * scale;
            const y = p.pixel_y * scale;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        
        ctx.stroke();
        ctx.restore();
    }
    
    if (cropRect) {
        ctx.save();
        ctx.strokeStyle = "#005fcc";
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 5]);
        ctx.strokeRect(cropRect.x, cropRect.y, cropRect.width, cropRect.height);
        ctx.fillStyle = "rgba(0,95,204,.08)";
        ctx.fillRect(cropRect.x, cropRect.y, cropRect.width, cropRect.height);
        ctx.restore();
    }
}

// 마우스 드래그 이벤트 (영역 선택)
function canvasPosition(e) {
    const r = canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
}

canvas.addEventListener("mousedown", e => {
    if (loadedImage) dragStart = canvasPosition(e);
});

canvas.addEventListener("mousemove", e => {
    if (!dragStart) return;
    const p = canvasPosition(e);
    cropRect = normalizeRect(dragStart.x, dragStart.y, p.x - dragStart.x, p.y - dragStart.y);
    drawImageCanvas();
});

canvas.addEventListener("mouseup", () => dragStart = null);
canvas.addEventListener("mouseleave", () => dragStart = null);

document.getElementById("resetSelectionBtn").addEventListener("click", () => {
    cropRect = null;
    extractedPoints = [];
    drawImageCanvas();
    setStatus("그래프 영역 선택을 초기화했습니다. 전체 이미지를 분석합니다.");
});

function normalizeRect(x, y, w, h) {
    const l = Math.max(0, Math.min(x, x + w));
    const t = Math.max(0, Math.min(y, y + h));
    const r = Math.min(canvas.width, Math.max(x, x + w));
    const b = Math.min(canvas.height, Math.max(y, y + h));
    return { x: l, y: t, width: r - l, height: b - t };
}

// 주요 버튼 이벤트
document.getElementById("analyzeImageBtn").addEventListener("click", analyzeImage);
document.getElementById("playGraphAudioBtn").addEventListener("click", () => playAudio("graphAudio"));
document.getElementById("readDescriptionBtn").addEventListener("click", readGraphDescription);

// 이미지 분석 메인 로직 (API 연동)
async function analyzeImage() {
    if (!selectedImageFile) return;
    
    setStatus("그래프를 분석하는 중입니다.");
    document.getElementById("analyzeImageBtn").disabled = true;
    
    const formData = new FormData();
    formData.append("image", selectedImageFile);
    formData.append("chart_type", chartTypeSelect.value);
    formData.append("color_scheme", candleColorSelect.value);
    
    const scale = Number(canvas.dataset.scale || 1);
    
    if (cropRect && cropRect.width > 0 && cropRect.height > 0) {
        formData.append("crop_x", Math.round(cropRect.x / scale));
        formData.append("crop_y", Math.round(cropRect.y / scale));
        formData.append("crop_width", Math.round(cropRect.width / scale));
        formData.append("crop_height", Math.round(cropRect.height / scale));
    }
    
    try {
        const res = await fetch(`${SERVER_URL}/analyze-graph-image`, { 
            method: "POST", 
            body: formData 
        });
        const payload = await res.json();
        
        if (!res.ok) throw new Error(payload.detail || "이미지 분석에 실패했습니다.");
        
        extractedGraphData = payload.data || [];
        extractedPoints = payload.points || [];
        
        renderDescription(payload.analysis, payload.confidence);
        renderDebugImage(payload.debug_image);
        drawImageCanvas();
        await prepareGraphAudio();
        
        document.getElementById("playGraphAudioBtn").disabled = false;
        document.getElementById("readDescriptionBtn").disabled = false;
        setStatus(statusText(payload));
        
    } catch (error) {
        renderDebugImage(null);
        setStatus(`${error.message} 결과가 불안정하면 가격 차트 영역만 키보드 영역 설정을 조절하거나 캔들 색상 설정을 변경해 주세요.`);
    } finally {
        document.getElementById("analyzeImageBtn").disabled = false;
    }
}

// 상태 텍스트 렌더링
function statusText(payload) {
    if (payload.chart_type === "candlestick") {
        const conf = payload.confidence ? Math.round(payload.confidence.score * 100) : "?";
        return `분석 완료. 예상 캔들 ${payload.expected_candles || "?"}개, 선택 ${payload.selected_candles || 0}개, fallback ${payload.fallback_recovered || 0}개, 누락 ${payload.missing_candles || 0}개, 신뢰도 ${conf}%입니다.`;
    }
    return "분석이 완료되었습니다. 빨간 선은 시스템이 추출한 그래프 흐름입니다.";
}

// 접근성 설명 렌더링
function renderDescription(analysis, confidence) {
    const summary = document.getElementById("graphSummary");
    const list = document.getElementById("descriptionList");
    
    summary.innerText = analysis ? analysis.summary : "분석 결과가 없습니다.";
    list.innerHTML = "";
    
    if (confidence) {
        const li = document.createElement("li");
        li.innerText = `분석 신뢰도: ${Math.round(confidence.score * 100)}%, 단계: ${confidence.level}`;
        list.appendChild(li);
    }
    
    (analysis?.descriptions || []).forEach(text => {
        const li = document.createElement("li");
        li.innerText = text;
        list.appendChild(li);
    });
}

function renderDebugImage(src) {
    const wrap = document.getElementById("debugWrap");
    const img = document.getElementById("debugImage");
    
    if (!wrap || !img) return;
    
    if (src) {
        img.src = src;
        wrap.hidden = false;
    } else {
        img.removeAttribute("src");
        wrap.hidden = true;
    }
}

// 오디오 준비 및 API 요청
async function prepareGraphAudio() {
    if (extractedGraphData.length === 0) return;
    const blob = await requestAudio(extractedGraphData, document.getElementById("waveSelect").value);
    const audio = document.getElementById("graphAudio");
    if (audio.src.startsWith("blob:")) URL.revokeObjectURL(audio.src);
    audio.src = URL.createObjectURL(blob);
}

async function requestAudio(data, waveform) {
    const payload = { 
        data, 
        max_freq: Number(document.getElementById("freqSlider").value), 
        waveform 
    };
    
    const res = await fetch(`${SERVER_URL}/sonify-data`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    
    if (!res.ok) throw new Error("음향 생성에 실패했습니다.");
    return await res.blob();
}

function getSpatialSettings() {
    const settings = {
        min_frequency: Number(document.getElementById("minFreqSlider").value),
        max_frequency: Number(document.getElementById("freqSlider").value),
        min_amplitude: Number(document.getElementById("minAmplitudeSlider").value),
        max_amplitude: Number(document.getElementById("maxAmplitudeSlider").value),
        duration_seconds: BASE_PLAYBACK_SECONDS / playbackSpeed,
        waveform: document.getElementById("waveSelect").value
    };
    if (settings.max_frequency <= settings.min_frequency) {
        throw new Error("최대 음높이는 최소 음높이보다 커야 합니다.");
    }
    if (settings.max_amplitude <= settings.min_amplitude) {
        throw new Error("최대 음량은 최소 음량보다 커야 합니다.");
    }
    return settings;
}

async function requestSpatialAudio(series) {
    const fullCandles = series.candles?.every(c => c.volume !== null && c.volume !== undefined);
    const settings = getSpatialSettings();
    const payload = fullCandles ? {
        symbol: series.label, timeframe: series.timeframe || 'unknown', candles: series.candles,
        start_index: playbackRange[0], end_index: playbackRange[1], ...settings
    } : { prices: series.prices, volumes: series.volumes, timestamps: series.timestamps, ...settings };
    const response = await fetch(`${SERVER_URL}/${fullCandles ? 'sonify-stock' : 'sonify-spatial'}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw Error(typeof error.detail === 'string' ? error.detail : '차트 데이터 또는 음향 설정을 확인하세요.');
    }
    return response.blob();
}

const chartNavigator = new ChartNavigator();
let playbackRange = [0, 0], audioRequestId = 0, audioReady = false, pendingPlay = false, explicitlyStopped = true, transportIntent = 0;
function announce(text) {
    const live = document.getElementById('accessibleAnnouncement');
    live.textContent = '';
    clearTimeout(announce.timer);
    announce.timer = setTimeout(() => { live.textContent = text; }, 40);
}
async function activateSeries(series) {
    if (!series?.prices.length) throw Error('데이터가 없습니다.');
    stopAllAudio();
    activeSeries = series;
    chartNavigator.reset(series.prices.length);
    playbackRange = [0, series.prices.length - 1];
    document.getElementById('rangeMode').value = 'full';
    document.getElementById('rangeStart').value = 1;
    document.getElementById('rangeEnd').value = series.prices.length;
    ['rangeStart', 'rangeEnd'].forEach(id => document.getElementById(id).max = series.prices.length);
    const slider = document.getElementById('positionSlider');
    slider.max = series.prices.length - 1; slider.value = 0; slider.disabled = false;
    document.getElementById('activeSeriesLabel').textContent = `${series.label}, ${series.prices.length}개 봉. 전체 차트 내 상대적인 음높이입니다.`;
    renderActivePoint(0);
    await rebuildActiveAudio(false);
}
async function rebuildActiveAudio(preservePosition = true, autoplay = false) {
    if (!activeSeries) return;
    const id = ++audioRequestId, intent = transportIntent;
    const focusedControl = document.activeElement;
    const audio = document.getElementById('spatialAudio');
    const index = preservePosition ? chartNavigator.currentIndex : playbackRange[0];
    audio.pause(); audioReady = false; pendingPlay = false;
    setPlayerControlsDisabled(true);
    document.getElementById('playbackState').textContent = '공간음향 생성 중';
    try {
        const blob = await requestSpatialAudio(activeSeries);
        if (id !== audioRequestId) return;
        if (spatialAudioUrl) URL.revokeObjectURL(spatialAudioUrl);
        spatialAudioUrl = URL.createObjectURL(blob);
        pendingSeekIndex = Math.max(playbackRange[0], Math.min(playbackRange[1], index));
        pendingPlay = autoplay && intent === transportIntent;
        audio.src = spatialAudioUrl;
        audio.volume = Number(document.getElementById('masterVolumeSlider').value);
        audio.load();
        audioReady = true;
        document.getElementById('playbackState').textContent = '재생 준비 완료';
        document.getElementById('rangeStatus').textContent = `${playbackRange[0] + 1}~${playbackRange[1] + 1}번째 봉. 전체 차트 기준 음높이·음량·좌우 위치를 유지합니다.`;
    } catch (error) {
        if (id !== audioRequestId) return;
        audio.removeAttribute('src');
        document.getElementById('playbackState').textContent = error.message;
        announce(error.message);
    } finally {
        if (id === audioRequestId) {
            setPlayerControlsDisabled(!audioReady);
            if (focusedControl?.tagName === 'BUTTON' && focusedControl.closest('#playerControls') && document.activeElement === document.body) focusedControl.focus();
        }
    }
}
function setPlayerControlsDisabled(disabled) {
    ['playPauseBtn','pauseBtn','restartBtn','slowerBtn','fasterBtn','stopBtn'].forEach(id => document.getElementById(id).disabled = disabled || !activeSeries);
    ['previousSegmentBtn','nextSegmentBtn','announcePositionBtn','detailBtn','applyRangeBtn','readStockBtn'].forEach(id => document.getElementById(id).disabled = !activeSeries);
}
function playSafely() {
    explicitlyStopped = false;
    document.getElementById('graphAudio').pause();
    document.getElementById('spatialAudio').play().catch(() => announce('재생 버튼을 다시 눌러주세요.'));
}
function playPauseActiveAudio() {
    if (!audioReady) return;
    cancelSpeech();
    const audio = document.getElementById('spatialAudio');
    if (audio.paused) playSafely(); else { explicitlyStopped = false; audio.pause(); }
}
function restartActiveAudio() {
    if (!activeSeries) return;
    cancelSpeech();
    playbackRange = [0, activeSeries.prices.length - 1];
    document.getElementById('rangeMode').value = 'full';
    rebuildActiveAudio(false, true);
}
function seekToIndex(index, shouldAnnounce = false) {
    if (!activeSeries) return;
    const bounded = chartNavigator.seek(index);
    const audio = document.getElementById('spatialAudio');
    explicitlyStopped = false; audio.pause();
    renderActivePoint(bounded);
    if (bounded < playbackRange[0] || bounded > playbackRange[1]) {
        playbackRange = [0, activeSeries.prices.length - 1];
        document.getElementById('rangeMode').value = 'full';
        rebuildActiveAudio(true);
    } else if (Number.isFinite(audio.duration)) {
        audio.currentTime = (bounded - playbackRange[0]) / Math.max(1, playbackRange[1] - playbackRange[0]) * audio.duration;
    } else pendingSeekIndex = bounded;
    if (shouldAnnounce) announceCurrentPosition(false, false);
}
function moveActiveSegment(direction) {
    seekToIndex(chartNavigator.currentIndex + direction * Math.max(1, Number(document.getElementById('segmentSize').value) || 10), true);
}
async function changePlaybackSpeed(direction) {
    const next = Math.max(0, Math.min(SPEED_STEPS.length - 1, SPEED_STEPS.indexOf(playbackSpeed) + direction));
    playbackSpeed = SPEED_STEPS[next];
    document.getElementById('speedState').textContent = `속도 ${playbackSpeed}배`;
    document.getElementById('speedSelect').value = String(playbackSpeed);
    await rebuildActiveAudio(true);
    speakText(`재생 속도 ${playbackSpeed}배. 음높이는 유지됩니다.`, false);
}
function formatActivePrice(value) { return activeSeries?.currency ? formatPrice(value, activeSeries.currency) : String(value); }
function pointText(index, detailed = false) {
    const c = activeSeries.candles?.[index];
    const price = activeSeries.prices[index];
    const volume = activeSeries.volumes?.[index];
    const volumeText = volume == null ? '정보 없음' : `${Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(volume)}주`;
    const date = formatTimestamp(activeSeries.timestamps?.[index] || '시각 정보 없음', activeSeries.timeframe === '1d');
    const prev = activeSeries.prices[index - 1];
    const pct = index && prev ? (price / prev - 1) * 100 : null;
    const comparison = activeSeries.timeframe === '1d' ? '이전 거래일 종가 대비' : '이전 봉 종가 대비';
    const change = pct == null ? '이전 봉 비교 정보 없음' : `${comparison} ${Math.abs(pct).toFixed(2)}퍼센트 ${pct > 0 ? '상승' : pct < 0 ? '하락' : '동일'}`;
    return `전체 ${activeSeries.prices.length}개 중 ${index + 1}번째 봉, ${date}. ${detailed && c ? `시가 ${formatActivePrice(c.open)}, 고가 ${formatActivePrice(c.high)}, 저가 ${formatActivePrice(c.low)}, ` : ''}종가 ${formatActivePrice(price)}. ${change}. 거래량 ${volumeText}.`;
}
function renderActivePoint(index) {
    if (!activeSeries) return;
    const bounded = chartNavigator.seek(index);
    const text = pointText(bounded);
    // Position is stated in words ("전체 30개 중 4번째"): "10% · 4/30" was read aloud as
    // an unexplained percentage and "삼십 분의 사".
    document.getElementById('currentPosition').textContent = `전체 ${activeSeries.prices.length}개 중 ${bounded + 1}번째`;
    document.getElementById('currentPointDetail').textContent = text;
    const slider = document.getElementById('positionSlider');
    slider.value = bounded; slider.setAttribute('aria-valuetext', text);
}
function announceCurrentPosition(detailed = false, explicit = true) {
    if (activeSeries) speakText(pointText(chartNavigator.currentIndex, detailed === true), explicit);
}
const speechController = new SpeechController(window.speechSynthesis, window.SpeechSynthesisUtterance, (text, state) => {
    const status = document.getElementById('speechStatus');
    status.textContent = text; status.dataset.state = state;
});
function cancelSpeech() { speechController.cancel(); document.getElementById('speechStatus').textContent = ''; }
function speakText(text, explicit = true) {
    announce(text);
    if (!explicit && !document.getElementById('speechToggle').checked) { cancelSpeech(); return; }
    document.querySelectorAll('audio').forEach(a => a.pause());
    speechController.speak(text);
}
const spatialAudio = document.getElementById('spatialAudio');
spatialAudio.addEventListener('loadedmetadata', () => {
    if (pendingSeekIndex !== null) {
        const index = pendingSeekIndex; pendingSeekIndex = null;
        seekToIndex(index, false);
    }
    if (pendingPlay) { pendingPlay = false; playSafely(); }
});
spatialAudio.addEventListener('play', () => {
    document.getElementById('playbackState').textContent = '재생 중';
    document.getElementById('playPauseBtn').textContent = '재생';
});
spatialAudio.addEventListener('pause', () => {
    document.getElementById('playbackState').textContent = explicitlyStopped ? '정지' : spatialAudio.ended ? '재생 완료' : '일시정지';
    document.getElementById('playPauseBtn').textContent = '재생';
});
spatialAudio.addEventListener('ended', () => {
    if (document.getElementById('repeatRange').checked) { spatialAudio.currentTime = 0; playSafely(); }
    else document.getElementById('playbackState').textContent = '재생 완료';
});
spatialAudio.addEventListener('timeupdate', () => {
    if (!audioReady || !activeSeries || !Number.isFinite(spatialAudio.duration) || spatialAudio.duration <= 0) return;
    renderActivePoint(playbackRange[0] + Math.round(spatialAudio.currentTime / spatialAudio.duration * (playbackRange[1] - playbackRange[0])));
});
async function applyPlaybackRange() {
    if (!activeSeries) return;
    try {
        if (!activeSeries.candles?.every(c => c.volume != null)) throw Error('구간 생성에는 거래량이 포함된 OHLCV가 필요합니다.');
        playbackRange = chartNavigator.range(document.getElementById('rangeMode').value, Number(document.getElementById('segmentSize').value), Number(document.getElementById('rangeStart').value), Number(document.getElementById('rangeEnd').value));
        await rebuildActiveAudio(false);
        speakText(document.getElementById('rangeStatus').textContent);
    } catch (error) { speakText(error.message); }
}
function announceSettings() {
    speakText(`음높이 ${document.getElementById('minFreqSlider').value}에서 ${document.getElementById('freqSlider').value}헤르츠. 거래량 음량 ${Math.round(Number(document.getElementById('minAmplitudeSlider').value)*100)}에서 ${Math.round(Number(document.getElementById('maxAmplitudeSlider').value)*100)}퍼센트. 전체 음량 ${document.getElementById('masterVolumeVal').textContent}퍼센트. 속도 ${playbackSpeed}배.`);
}
function readGraphDescription() { speakText(document.getElementById('graphSummary').textContent); }
function stopAllAudio() {
    cancelSpeech(); pendingPlay = false; explicitlyStopped = true; transportIntent++;
    document.querySelectorAll('audio').forEach(a => { a.pause(); if (a.src) a.currentTime = 0; });
    if (activeSeries) renderActivePoint(playbackRange[0]);
    document.getElementById('playbackState').textContent = '정지';
}
function playAudio(id) { stopAllAudio(); const a = document.getElementById(id); if (a?.src) a.play().catch(() => announce('재생 버튼을 다시 눌러주세요.')); }
const buttons = {
    playPauseBtn: () => { if (audioReady) { cancelSpeech(); playSafely(); } }, pauseBtn: () => { explicitlyStopped = false; spatialAudio.pause(); }, restartBtn: restartActiveAudio,
    previousSegmentBtn: () => moveActiveSegment(-1), nextSegmentBtn: () => moveActiveSegment(1),
    slowerBtn: () => changePlaybackSpeed(-1), fasterBtn: () => changePlaybackSpeed(1),
    announcePositionBtn: () => announceCurrentPosition(), detailBtn: () => announceCurrentPosition(true),
    stopBtn: stopAllAudio, settingsBtn: announceSettings, applyRangeBtn: applyPlaybackRange
};
Object.entries(buttons).forEach(([id, fn]) => document.getElementById(id).addEventListener('click', fn));
document.getElementById('positionSlider').addEventListener('input', e => seekToIndex(Number(e.target.value), false));
document.getElementById('positionSlider').addEventListener('change', () => announceCurrentPosition(false, false));
const SHORTCUTS = {
    ' ': ['Space: 재생·일시정지', playPauseActiveAudio],
    ArrowLeft: ['←: 이전 봉', () => seekToIndex(chartNavigator.currentIndex - 1, true)],
    ArrowRight: ['→: 다음 봉', () => seekToIndex(chartNavigator.currentIndex + 1, true)],
    Home: ['Home: 첫 봉', () => seekToIndex(0, true)], End: ['End: 마지막 봉', () => seekToIndex(chartNavigator.length - 1, true)],
    PageUp: ['PageUp / J: 이전 구간', () => moveActiveSegment(-1)], PageDown: ['PageDown / K: 다음 구간', () => moveActiveSegment(1)],
    j: ['', () => moveActiveSegment(-1)], k: ['', () => moveActiveSegment(1)],
    r: ['R: 전체 처음부터 재생', restartActiveAudio], p: ['P: 현재 봉 요약', () => announceCurrentPosition()],
    d: ['D: 현재 봉 상세', () => announceCurrentPosition(true)], o: ['O: 전체 차트 요약', readStockSummary],
    s: ['S: 설정 안내', announceSettings],
    '[': ['[: 속도 감소', () => changePlaybackSpeed(-1)], ']': [']: 속도 증가', () => changePlaybackSpeed(1)],
    Escape: ['Escape: 모든 소리 정지', stopAllAudio],
    g: ['G: 종목 순위', () => document.getElementById('rankingHeading').focus()],
    '/': ['/: 종목 검색', () => document.getElementById('stockSearch').focus()],
    l: ['L: 입력 종목 조회', () => loadStockData(false)],
    i: ['I: 이미지 입력', () => { document.getElementById('supportTools').open = true; document.getElementById('imageInput').focus(); }],
    a: ['A: 이미지 분석', () => { if (selectedImageFile) analyzeImage(); }]
};
Object.values(SHORTCUTS).filter(([label]) => label).forEach(([label]) => { const li = document.createElement('li'); li.textContent = label; document.getElementById('shortcutHelp').append(li); });
// Spoken form of each shortcut: symbols such as "/" and "[" are skipped or misread by
// speech engines, and a bare list runs keys into the previous item's description.
// Each entry becomes one sentence that names the key in words, then its action.
const SPOKEN_SHORTCUTS = [
    ['스페이스 키', '재생과 일시정지'],
    ['왼쪽 방향키', '이전 봉'],
    ['오른쪽 방향키', '다음 봉'],
    ['홈 키', '첫 봉'],
    ['엔드 키', '마지막 봉'],
    ['페이지 업 키 또는 제이 키', '이전 구간'],
    ['페이지 다운 키 또는 케이 키', '다음 구간'],
    ['알 키', '전체 처음부터 재생'],
    ['피 키', '현재 봉 요약'],
    ['디 키', '현재 봉 상세 정보'],
    ['오 키', '전체 차트 요약'],
    ['에스 키', '현재 설정 안내'],
    ['왼쪽 대괄호 키', '속도 감소'],
    ['오른쪽 대괄호 키', '속도 증가'],
    ['이스케이프 키', '모든 소리 정지'],
    ['지 키', '종목 순위로 이동'],
    ['슬래시 키', '종목 검색으로 이동'],
    ['엘 키', '입력한 종목 조회'],
    ['아이 키', '그래프 이미지 입력'],
    ['에이 키', '그래프 이미지 분석'],
];
function spokenShortcutHelp() {
    const items = SPOKEN_SHORTCUTS.map(([key, action]) => `${key}, ${action}.`);
    return `단축키 ${items.length}개를 안내합니다. 재생기에 초점이 있을 때 동작합니다. ${items.join(' ')}`;
}
document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
    const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (key === 'Escape') { stopAllAudio(); return; }
    if (!e.target.closest('#playerControls') || e.target.closest('input,select,textarea,[contenteditable=true]')) return;
    if ((key === ' ' || key === 'Enter') && e.target.closest('button,a,summary')) return;
    const shortcut = SHORTCUTS[key];
    if (shortcut && activeSeries) { e.preventDefault(); if (!e.repeat || ['ArrowLeft','ArrowRight'].includes(key)) shortcut[1](); }
});

// ==========================================
// 🚀 오디오 트래커 (Playback Cursor) 애니메이션
// ==========================================
let trackerAnimationId = null;
const graphAudioEl = document.getElementById("graphAudio");

// 오디오 재생이 시작될 때 애니메이션 활성화
graphAudioEl.addEventListener("play", () => {
    if (extractedPoints.length === 0) return;
    
    const updateTracker = () => {
        if (graphAudioEl.paused || graphAudioEl.ended) return;
        
        // 1. 현재 오디오 진행률 계산 (duration이 아직 안 불러와졌으면 기본값 5초 사용)
        const duration = (graphAudioEl.duration && !isNaN(graphAudioEl.duration) && graphAudioEl.duration !== Infinity) ? graphAudioEl.duration : 5;
        const progress = graphAudioEl.currentTime / duration;

        // 2. 캔버스를 싹 지우고 원본 이미지와 추출된 선을 다시 그리기
        drawImageCanvas();

        // 3. 진행률(progress)에 맞춰 트래커(세로선) x좌표 계산하기
        const scale = Number(canvas.dataset.scale || 1);
        const startX = extractedPoints[0].pixel_x * scale;
        const endX = extractedPoints[extractedPoints.length - 1].pixel_x * scale;
        const currentX = startX + (endX - startX) * progress;

        // 4. 강렬한 빨간색 세로선(트래커) 그리기
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(currentX, 0); // 캔버스 맨 위
        ctx.lineTo(currentX, canvas.height); // 캔버스 맨 아래
        ctx.lineWidth = 3;
        ctx.strokeStyle = "rgba(255, 71, 87, 0.9)"; // 눈에 확 띄는 빨간색 (#ff4757)
        ctx.setLineDash([6, 4]); // 세련되게 점선으로 표현
        ctx.stroke();
        
        // 현재 x위치의 데이터 포인트(y축)에 동그라미 포인트 그려주기
        const currentY = extractedPoints[Math.min(
            Math.floor(progress * extractedPoints.length), 
            extractedPoints.length - 1
        )].pixel_y * scale;
        
        ctx.beginPath();
        ctx.arc(currentX, currentY, 6, 0, 2 * Math.PI);
        ctx.fillStyle = "#ff4757";
        ctx.fill();
        ctx.restore();

        // 다음 프레임 예약 (무한 반복)
        trackerAnimationId = requestAnimationFrame(updateTracker);
    };
    
    // 애니메이션 루프 시작!
    trackerAnimationId = requestAnimationFrame(updateTracker);
});

// 오디오가 멈추거나 끝나면 애니메이션 끄고 캔버스 원상복구
graphAudioEl.addEventListener("pause", () => {
    cancelAnimationFrame(trackerAnimationId);
    drawImageCanvas(); 
});
graphAudioEl.addEventListener("ended", () => {
    cancelAnimationFrame(trackerAnimationId);
    drawImageCanvas(); 
});

document.getElementById('speedSelect').addEventListener('change', async e => {
    playbackSpeed = Number(e.target.value);
    document.getElementById('speedState').textContent = `속도 ${playbackSpeed}배`;
    if (activeSeries) await rebuildActiveAudio(true);
});
document.getElementById('readShortcutsBtn').addEventListener('click', () => speakText(spokenShortcutHelp()));
document.getElementById('speechToggle').addEventListener('change', cancelSpeech);
setInterval(() => {
    if (document.hidden || document.getElementById('loadStockBtn').disabled) return;
    if (document.activeElement?.closest('#marketTools') === null) loadStockRankings();
    if (currentStockPayload?.source !== 'tossinvest') return;
    if (document.activeElement?.closest('#playerControls')) return;
    if (window.speechSynthesis?.speaking) return;
    loadStockData(false, true);
}, 60_000);
