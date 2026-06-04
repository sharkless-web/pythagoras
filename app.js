const SERVER_URL = "http://127.0.0.1:8000";

// 전역 변수
let selectedImageFile = null,
    loadedImage = null,
    cropRect = null,
    dragStart = null;
let extractedGraphData = [],
    extractedPoints = [],
    csvData = [],
    mixCandidates = [],
    chartInstance = null,
    voices = [];

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

document.getElementById("waveSelect").addEventListener("change", () => {
    if (extractedGraphData.length > 0) prepareGraphAudio();
});

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

// TTS 설명 읽기
function readGraphDescription() {
    stopAllAudio();
    const msg = new SpeechSynthesisUtterance(document.getElementById("graphSummary").innerText);
    msg.lang = "ko-KR";
    msg.rate = 1.05;
    
    const ko = voices.find(v => v.lang.includes("ko"));
    if (ko) msg.voice = ko;
    
    window.speechSynthesis.speak(msg);
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

// ==========================================
// CSV 개발 및 검증용 기능
// ==========================================
document.getElementById("csvInput").addEventListener("change", e => {
    const file = e.target.files[0];
    if (!file) return;
    
    Papa.parse(file, {
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true,
        complete: r => processCSV(r.data)
    });
});

function processCSV(rows) {
    if (!rows.length) return alert("CSV 데이터가 없습니다.");
    
    const columns = Object.keys(rows[0]);
    const keys = ["time", "date", "index", "year", "month", "day", "시간", "날짜", "연도"];
    
    let labels = rows.map((_, i) => i + 1);
    let dataColumns = [...columns];
    
    if (keys.some(k => columns[0].toLowerCase().includes(k))) {
        labels = rows.map(row => row[columns[0]]);
        dataColumns = columns.slice(1);
    }
    
    csvData = dataColumns.map(column => {
        const raw = rows.map(row => Number(row[column])).filter(Number.isFinite);
        if (!raw.length) return null;
        
        const min = Math.min(...raw);
        const max = Math.max(...raw);
        const scaled = raw.map(v => max !== min ? (v - min) / (max - min) : .5);
        
        return { name: column, raw, scaled, min, max };
    }).filter(Boolean);
    
    drawCsvChart(labels, csvData);
    renderCsvResults();
}

function drawCsvChart(labels, datasets) {
    const el = document.getElementById("lineChart");
    if (chartInstance) chartInstance.destroy();
    
    chartInstance = new Chart(el, {
        type: "line",
        data: {
            labels,
            datasets: datasets.map((d, i) => ({
                label: d.name,
                data: d.scaled,
                borderColor: `hsl(${i * 97 % 360}, 72%, 42%)`,
                borderWidth: 2,
                pointRadius: 2,
                tension: .15
            }))
        },
        options: {
            responsive: true,
            scales: {
                y: { min: 0, max: 1, ticks: { display: false } }
            }
        }
    });
}

function renderCsvResults() {
    const container = document.getElementById("csvResults");
    container.innerHTML = "";
    document.getElementById("mixPanel").hidden = csvData.length === 0;
    
    csvData.forEach((d, i) => {
        const card = document.createElement("article");
        card.className = "data-card";
        card.innerHTML = `
            <div>
                <h3>${d.name}</h3>
                <p>원본 최소 ${d.min.toFixed(2)}, 원본 최대 ${d.max.toFixed(2)}</p>
            </div>
            <div class="card-actions">
                <label><input type="checkbox" id="mixCheck_${i}"> 믹싱 포함</label>
                <button class="btn-secondary" type="button" id="csvPlay_${i}">재생</button>
                <audio id="csvAudio_${i}" controls></audio>
            </div>
        `;
        container.appendChild(card);
        
        document.getElementById(`csvPlay_${i}`).addEventListener("click", async () => {
            const blob = await requestAudio(d.scaled, "sine");
            const audio = document.getElementById(`csvAudio_${i}`);
            audio.src = URL.createObjectURL(blob);
            playAudio(`csvAudio_${i}`);
        });
        
        document.getElementById(`mixCheck_${i}`).addEventListener("change", updateMixCandidates);
    });
    updateMixCandidates();
}

function updateMixCandidates() {
    mixCandidates = csvData.filter((_, i) => {
        const c = document.getElementById(`mixCheck_${i}`);
        return c && c.checked;
    });
    
    document.getElementById("mixListText").innerText = mixCandidates.length 
        ? `선택된 데이터: ${mixCandidates.map(i => i.name).join(", ")}` 
        : "선택된 데이터가 없습니다.";
}

document.getElementById("mixBtn").addEventListener("click", async () => {
    if (!mixCandidates.length) return alert("믹싱할 데이터를 선택해 주세요.");
    
    const payload = {
        data_list: mixCandidates.map(i => i.scaled),
        max_freq: Number(document.getElementById("freqSlider").value),
        waveform_list: mixCandidates.map(() => "sine")
    };
    
    const res = await fetch(`${SERVER_URL}/mix-data`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    
    const blob = await res.blob();
    const audio = document.getElementById("mixAudio");
    audio.src = URL.createObjectURL(blob);
    playAudio("mixAudio");
});

// 단축키 설정
document.addEventListener("keydown", e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "Escape") stopAllAudio();
    if (e.key.toLowerCase() === "i") document.getElementById("imageInput").click();
    
    if (e.key.toLowerCase() === "a" && !document.getElementById("analyzeImageBtn").disabled) {
        analyzeImage();
    }
    
    if (e.key === " " && !document.getElementById("playGraphAudioBtn").disabled) {
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