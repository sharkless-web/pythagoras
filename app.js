const SERVER_URL = "http://127.0.0.1:8001";

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

let activeSeries = null,
    playbackSpeed = 1,
    spatialAudioUrl = null,
    pendingSeekIndex = null;

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
window.speechSynthesis.onvoiceschanged = () => {
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
document.getElementById("loadDemoBtn").addEventListener("click", () => loadStockData(true));
document.getElementById("readStockBtn").addEventListener("click", readStockSummary);

async function loadStockData(demo = false) {
    const query = document.getElementById("stockSearch").value.trim();
    const symbol = STOCK_SYMBOLS[query.toLowerCase()] || STOCK_SYMBOLS[query] || query.toUpperCase();
    const interval = document.getElementById("stockInterval").value;
    const count = Number(document.getElementById("stockCount").value);
    const status = document.getElementById("stockStatus");
    const button = document.getElementById("loadStockBtn");
    if (!symbol) {
        status.innerText = "종목명이나 종목 코드를 입력하세요.";
        document.getElementById("stockSearch").focus();
        return;
    }
    status.innerText = demo ? "샘플 데이터를 준비하는 중입니다." : "토스증권에서 실시간 데이터를 불러오는 중입니다.";
    button.disabled = true;
    document.getElementById("loadDemoBtn").disabled = true;
    try {
        const params = new URLSearchParams({ symbol, interval, count: String(count), demo: String(demo) });
        const response = await fetch(`${SERVER_URL}/stock-candles?${params}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "주식 데이터를 불러오지 못했습니다.");
        currentStockPayload = payload;
        stockData = payload.close_prices || [];
        stockCandles = payload.candles || [];
        stockVolumes = payload.volumes || stockCandles.map(candle => candle.volume);
        renderStockSummary(payload);
        document.getElementById("stockResults").hidden = false;
        const source = document.getElementById("stockSource");
        source.innerText = payload.source === "tossinvest" ? "토스증권 실데이터" : "샘플 체험 데이터";
        source.className = `source-badge ${payload.source === "tossinvest" ? "live" : "demo"}`;
        document.getElementById("stockSummary").innerText = payload.analysis?.summary || "흐름 설명이 없습니다.";
        renderStockChart(stockCandles, payload.name);
        await prepareStockAudio();
        status.innerText = `${payload.name}, ${stockData.length}개 봉을 불러왔습니다. 핵심 정보부터 확인하세요.`;
    } catch (error) {
        currentStockPayload = null;
        stockData = [];
        stockCandles = [];
        stockVolumes = [];
        document.getElementById("stockResults").hidden = true;
        const source = document.getElementById("stockSource");
        source.innerText = "실데이터 연결 실패";
        source.className = "source-badge error";
        status.innerText = `${error.message} 샘플로 체험하려면 '샘플로 체험' 버튼을 누르세요.`;
    } finally {
        button.disabled = false;
        document.getElementById("loadDemoBtn").disabled = false;
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
    document.getElementById("stockTimestamp").innerText = `최근 봉 시각: ${formatTimestamp(metrics.latest_timestamp)}`;
}

function formatTimestamp(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function readStockSummary() {
    if (!currentStockPayload) return;
    const text = `${document.getElementById("stockName").innerText}. 최근 종가 ${document.getElementById("metricLatest").innerText}. 조회 구간 변화 ${document.getElementById("metricChange").innerText}. ${document.getElementById("stockSummary").innerText}`;
    speakText(text);
}

function renderStockChart(candles, name) {
    if (stockChartInstance) stockChartInstance.destroy();
    stockChartInstance = new Chart(document.getElementById("stockChart"), {
        type: "line",
        data: {
            labels: candles.map(c => c.timestamp),
            datasets: [
                { label: `${name} 종가`, data: candles.map(c => c.close), borderColor: "#176b57", borderWidth: 3, pointRadius: 2, tension: .15, yAxisID: "priceAxis" },
                { type: "bar", label: "거래량", data: candles.map(c => c.volume), backgroundColor: "rgba(109, 58, 168, .24)", borderColor: "#6d3aa8", borderWidth: 1, yAxisID: "volumeAxis" }
            ]
        },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            plugins: { legend: { display: true } },
            scales: {
                priceAxis: { type: "linear", position: "left", title: { display: true, text: "종가 · Pitch" } },
                volumeAxis: { type: "linear", position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "거래량 · Volume" } }
            }
        }
    });
}

async function prepareStockAudio() {
    if (!stockData.length) return;
    const usableVolumes = stockVolumes.length === stockData.length && stockVolumes.every(value => Number.isFinite(Number(value)))
        ? stockVolumes.map(Number) : null;
    await activateSeries({
        label: `${currentStockPayload.name} 종가와 거래량`,
        source: "stock",
        timestamps: stockCandles.map(candle => candle.timestamp),
        prices: stockData.map(Number),
        volumes: usableVolumes,
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
        cropRect = null;
        extractedPoints = [];
        extractedGraphData = [];
        
        fitCanvasToImage(image);
        canvasWrap.hidden = false;
        renderDebugImage(null);
        drawImageCanvas();
        
        document.getElementById("analyzeImageBtn").disabled = false;
        setStatus("이미지가 업로드되었습니다. 결과가 이상하면 가격 차트 영역만 드래그하여 다시 분석하세요.");
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
    
    if (cropRect && cropRect.width > 10 && cropRect.height > 10) {
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
        setStatus(`${error.message} 결과가 불안정하면 가격 차트 영역만 다시 드래그하거나 캔들 색상 설정을 변경해 주세요.`);
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
    document.getElementById("graphAudio").src = URL.createObjectURL(blob);
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
    const payload = {
        prices: series.prices,
        volumes: series.volumes,
        timestamps: series.timestamps,
        ...getSpatialSettings()
    };
    const response = await fetch(`${SERVER_URL}/sonify-spatial`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "공간음향 생성에 실패했습니다.");
    }
    return response.blob();
}

async function activateSeries(series) {
    if (!series || series.prices.length < 2) throw new Error("두 개 이상의 데이터가 필요합니다.");
    activeSeries = series;
    const slider = document.getElementById("positionSlider");
    slider.max = String(series.prices.length - 1);
    slider.value = "0";
    slider.disabled = false;
    document.getElementById("activeSeriesLabel").innerText = `${series.label}, ${series.prices.length}개 시점`;
    setPlayerControlsDisabled(false);
    renderActivePoint(0);
    await rebuildActiveAudio(false);
}

async function rebuildActiveAudio(preservePosition = true) {
    if (!activeSeries) return;
    const audio = document.getElementById("spatialAudio");
    const progress = preservePosition && Number.isFinite(audio.duration) && audio.duration > 0
        ? audio.currentTime / audio.duration : 0;
    document.getElementById("playbackState").innerText = "공간음향 생성 중";
    setPlayerControlsDisabled(true);
    try {
        const blob = await requestSpatialAudio(activeSeries);
        if (spatialAudioUrl) URL.revokeObjectURL(spatialAudioUrl);
        spatialAudioUrl = URL.createObjectURL(blob);
        audio.src = spatialAudioUrl;
        audio.volume = Number(document.getElementById("masterVolumeSlider").value);
        pendingSeekIndex = Math.round(progress * (activeSeries.prices.length - 1));
        audio.load();
        document.getElementById("playbackState").innerText = "재생 준비 완료";
    } catch (error) {
        document.getElementById("playbackState").innerText = error.message;
        throw error;
    } finally {
        setPlayerControlsDisabled(false);
    }
}

function setPlayerControlsDisabled(disabled) {
    ["playPauseBtn", "restartBtn", "previousSegmentBtn", "nextSegmentBtn", "slowerBtn", "fasterBtn", "announcePositionBtn"].forEach(id => {
        document.getElementById(id).disabled = disabled || !activeSeries;
    });
}

function playPauseActiveAudio() {
    const audio = document.getElementById("spatialAudio");
    if (!audio.src) return;
    window.speechSynthesis.cancel();
    if (audio.paused) audio.play();
    else audio.pause();
}

function restartActiveAudio() {
    const audio = document.getElementById("spatialAudio");
    if (!audio.src) return;
    audio.currentTime = 0;
    document.getElementById("positionSlider").value = "0";
    renderActivePoint(0);
    audio.play();
}

function seekToIndex(index, announce = false) {
    if (!activeSeries) return;
    const bounded = Math.max(0, Math.min(activeSeries.prices.length - 1, Number(index)));
    const slider = document.getElementById("positionSlider");
    slider.value = String(bounded);
    const audio = document.getElementById("spatialAudio");
    if (Number.isFinite(audio.duration) && audio.duration > 0) {
        audio.currentTime = bounded / Math.max(1, activeSeries.prices.length - 1) * audio.duration;
    } else {
        pendingSeekIndex = bounded;
    }
    renderActivePoint(bounded);
    if (announce) announceCurrentPosition();
}

function moveActiveSegment(direction) {
    if (!activeSeries) return;
    const step = Math.max(1, Math.ceil(activeSeries.prices.length / 10));
    const current = Number(document.getElementById("positionSlider").value);
    seekToIndex(current + direction * step, true);
}

async function changePlaybackSpeed(direction) {
    const current = SPEED_STEPS.indexOf(playbackSpeed);
    const next = Math.max(0, Math.min(SPEED_STEPS.length - 1, current + direction));
    if (next === current) return;
    playbackSpeed = SPEED_STEPS[next];
    document.getElementById("speedState").innerText = `속도 ${playbackSpeed}배`;
    await rebuildActiveAudio(true);
    speakText(`재생 속도 ${playbackSpeed}배`);
}

function formatActivePrice(value) {
    if (activeSeries?.currency) return formatPrice(value, activeSeries.currency);
    return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 3 }).format(value);
}

function renderActivePoint(index) {
    if (!activeSeries) return;
    const bounded = Math.max(0, Math.min(activeSeries.prices.length - 1, Number(index)));
    const percentage = activeSeries.prices.length > 1
        ? Math.round(bounded / (activeSeries.prices.length - 1) * 100) : 100;
    const timestamp = activeSeries.timestamps?.[bounded] ?? `${bounded + 1}번째 시점`;
    const volume = activeSeries.volumes
        ? new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(activeSeries.volumes[bounded])
        : "사용하지 않음";
    document.getElementById("currentPosition").innerText = `전체의 ${percentage}% · ${bounded + 1}/${activeSeries.prices.length}`;
    document.getElementById("currentPointDetail").innerText = `${formatTimestamp(timestamp)}. ${activeSeries.priceLabel || "주 데이터"} ${formatActivePrice(activeSeries.prices[bounded])}. ${activeSeries.volumeLabel || "보조 데이터"} ${volume}.`;
}

function announceCurrentPosition() {
    if (!activeSeries) return;
    const index = Number(document.getElementById("positionSlider").value);
    const percentage = activeSeries.prices.length > 1
        ? Math.round(index / (activeSeries.prices.length - 1) * 100) : 100;
    speakText(`현재 전체의 ${percentage}퍼센트 지점입니다. ${document.getElementById("currentPointDetail").innerText} 재생 속도 ${playbackSpeed}배입니다.`);
}

function speakText(text) {
    document.querySelectorAll("audio").forEach(audio => audio.pause());
    window.speechSynthesis.cancel();
    const message = new SpeechSynthesisUtterance(text);
    message.lang = "ko-KR";
    message.rate = 1;
    const koreanVoice = voices.find(voice => voice.lang.includes("ko"));
    if (koreanVoice) message.voice = koreanVoice;
    window.speechSynthesis.speak(message);
}

const spatialAudio = document.getElementById("spatialAudio");
spatialAudio.volume = Number(document.getElementById("masterVolumeSlider").value);
spatialAudio.addEventListener("loadedmetadata", () => {
    if (pendingSeekIndex !== null) {
        seekToIndex(pendingSeekIndex, false);
        pendingSeekIndex = null;
    }
});
spatialAudio.addEventListener("play", () => {
    document.getElementById("playbackState").innerText = "재생 중";
    document.getElementById("playPauseBtn").innerText = "일시정지";
});
spatialAudio.addEventListener("pause", () => {
    document.getElementById("playbackState").innerText = spatialAudio.ended ? "재생 완료" : "일시정지";
    document.getElementById("playPauseBtn").innerText = "재생";
});
spatialAudio.addEventListener("ended", () => {
    document.getElementById("playbackState").innerText = "재생 완료";
    document.getElementById("playPauseBtn").innerText = "재생";
});
spatialAudio.addEventListener("timeupdate", () => {
    if (!activeSeries || !Number.isFinite(spatialAudio.duration) || spatialAudio.duration <= 0) return;
    const progress = Math.min(1, spatialAudio.currentTime / spatialAudio.duration);
    const index = Math.round(progress * (activeSeries.prices.length - 1));
    document.getElementById("positionSlider").value = String(index);
    renderActivePoint(index);
});

document.getElementById("playPauseBtn").addEventListener("click", playPauseActiveAudio);
document.getElementById("restartBtn").addEventListener("click", restartActiveAudio);
document.getElementById("previousSegmentBtn").addEventListener("click", () => moveActiveSegment(-1));
document.getElementById("nextSegmentBtn").addEventListener("click", () => moveActiveSegment(1));
document.getElementById("slowerBtn").addEventListener("click", () => changePlaybackSpeed(-1));
document.getElementById("fasterBtn").addEventListener("click", () => changePlaybackSpeed(1));
document.getElementById("announcePositionBtn").addEventListener("click", announceCurrentPosition);
document.getElementById("positionSlider").addEventListener("input", event => seekToIndex(Number(event.target.value), false));

// TTS 설명 읽기
function readGraphDescription() {
    speakText(document.getElementById("graphSummary").innerText);
}

function stopAllAudio() {
    window.speechSynthesis.cancel();
    document.querySelectorAll("audio").forEach(a => {
        a.pause();
        a.currentTime = 0;
    });
}

function playAudio(id) {
    stopAllAudio();
    const a = document.getElementById(id);
    if (a && a.src) a.play();
}

// 중앙 Shortcut Map. 입력 요소를 조작하는 동안에는 전역 단축키를 실행하지 않는다.
document.addEventListener("keydown", e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "Escape") stopAllAudio();
    const isTyping = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName);
    if (e.key === "/" && !isTyping) {
        e.preventDefault();
        document.getElementById("stockSearch").focus();
        document.getElementById("stockSearch").select();
        return;
    }
    if (e.key.toLowerCase() === "l" && !isTyping) {
        loadStockData(false);
        return;
    }
    if (isTyping) return;
    if (e.key === " " && activeSeries) {
        e.preventDefault();
        playPauseActiveAudio();
        return;
    }
    if (e.key === "Home" && activeSeries) {
        e.preventDefault();
        restartActiveAudio();
        return;
    }
    if (e.key.toLowerCase() === "j" && activeSeries) {
        e.preventDefault();
        moveActiveSegment(-1);
        return;
    }
    if (e.key.toLowerCase() === "k" && activeSeries) {
        e.preventDefault();
        moveActiveSegment(1);
        return;
    }
    if (e.key === "[" && activeSeries) {
        e.preventDefault();
        changePlaybackSpeed(-1);
        return;
    }
    if (e.key === "]" && activeSeries) {
        e.preventDefault();
        changePlaybackSpeed(1);
        return;
    }
    if (e.key.toLowerCase() === "p" && activeSeries) {
        e.preventDefault();
        announceCurrentPosition();
        return;
    }
    if (e.key.toLowerCase() === "i") document.getElementById("imageInput").click();
    
    if (e.key.toLowerCase() === "a" && !document.getElementById("analyzeImageBtn").disabled) {
        analyzeImage();
    }
    
    if (e.key === " " && !activeSeries && !document.getElementById("playGraphAudioBtn").disabled) {
        e.preventDefault();
        playAudio("graphAudio");
    }
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
