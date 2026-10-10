function chartSummaryText(chart, summary, currency) {
    return `${chart.symbol}. 데이터 ${summary.count}개, ${formatTimestamp(summary.start)}부터 ${formatTimestamp(summary.end)}까지. 시작 종가 ${formatPrice(summary.start_close,currency)}, 마지막 종가 ${formatPrice(summary.end_close,currency)}. 전체 종가 ${Math.abs(summary.change_percent).toFixed(2)}퍼센트 ${summary.direction}. 최고가 ${formatPrice(summary.high,currency)}, 최저가 ${formatPrice(summary.low,currency)}. 최대 거래량 ${Intl.NumberFormat('ko-KR').format(summary.max_volume)}주, ${formatTimestamp(summary.max_volume_timestamp)}. 전체 차트의 최저·최고 종가를 음역에 대응하므로 작은 등락도 크게 들릴 수 있습니다.`;
}

document.getElementById('applyROIBtn').addEventListener('click', () => {
    if (!loadedImage) { setStatus('이미지를 먼저 선택하세요.'); return; }
    const [x,y,w,h] = ['roiX','roiY','roiWidth','roiHeight'].map(id=>Number(document.getElementById(id).value));
    if (![x,y,w,h].every(Number.isInteger) || x<0 || y<0 || w<1 || h<1 || x+w>loadedImage.width || y+h>loadedImage.height) { setStatus('원본 이미지 안에 들어오는 정수 영역을 입력하세요.'); return; }
    const scale=Number(canvas.dataset.scale); cropRect={x:x*scale,y:y*scale,width:w*scale,height:h*scale}; drawImageCanvas();
    setStatus(`분석 영역 X ${x}, Y ${y}, 너비 ${w}, 높이 ${h} 적용. 분석 버튼을 누르세요.`);
});
// Accessible combobox: focus stays in input while active descendant identifies selection.
const searchInput = document.getElementById('stockSearch');
const searchList = document.getElementById('searchResults');
let searchItems = [], searchIndex = -1, searchGeneration = 0;
function closeSearch() {
    searchList.hidden = true; searchInput.setAttribute('aria-expanded','false');
    searchInput.removeAttribute('aria-activedescendant'); searchIndex = -1;
}
function highlightSearch(index) {
    searchIndex = Math.max(0, Math.min(searchItems.length - 1,index));
    [...searchList.children].forEach((el,i)=>el.setAttribute('aria-selected',String(i===searchIndex)));
    if (searchItems.length) searchInput.setAttribute('aria-activedescendant',`search-option-${searchIndex}`);
}
function selectStock(index) {
    const item = searchItems[index]; if (!item) return;
    searchInput.value = item.symbol;
    document.getElementById('selectedStock').textContent = `선택 종목: ${item.name} (${item.symbol})`;
    closeSearch(); searchInput.focus();
}
async function searchStocks() {
    const generation = ++searchGeneration;
    try {
        const response = await fetch(`${SERVER_URL}/stock-search?q=${encodeURIComponent(searchInput.value.trim())}`);
        if (!response.ok) throw Error('검색 연결 실패');
        const data = await response.json();
        if (generation !== searchGeneration) return;
        searchItems = data.results;
        searchList.replaceChildren(); searchIndex = -1;
        searchItems.forEach((item,i)=>{
            const option=document.createElement('li'); option.id=`search-option-${i}`;
            option.role='option'; option.setAttribute('aria-selected','false');
            option.textContent=`${item.name} (${item.symbol})`;
            option.addEventListener('mousedown',e=>e.preventDefault());
            option.addEventListener('click',()=>selectStock(i)); searchList.append(option);
        });
        searchList.hidden = !searchItems.length;
        searchInput.setAttribute('aria-expanded',String(!!searchItems.length));
        searchInput.removeAttribute('aria-activedescendant');
        announce(searchItems.length ? `${searchItems.length}개 검색 결과. 방향키로 선택하세요.` : '등록된 검색 결과가 없습니다. 종목 코드를 직접 입력할 수 있습니다.');
    } catch (_) { announce('검색 결과를 불러오지 못했습니다. 종목 코드를 입력할 수 있습니다.'); closeSearch(); }
}
searchInput.addEventListener('input',searchStocks);
searchInput.addEventListener('keydown', async e=>{
    if (e.key==='ArrowDown' || e.key==='ArrowUp') {
        e.preventDefault();
        if(searchList.hidden) await searchStocks();
        if(searchItems.length) highlightSearch(searchIndex + (e.key==='ArrowDown'?1:-1));
    } else if(e.key==='Enter' && !searchList.hidden && searchIndex>=0) { e.preventDefault(); selectStock(searchIndex); }
    else if(e.key==='Escape') closeSearch();
    else if(e.key==='Tab') { searchGeneration++; closeSearch(); }
});
searchInput.addEventListener('blur',()=>{ searchGeneration++; closeSearch(); });
function updatePeriods() {
    const interval=document.getElementById('stockInterval').value;
    const daily=interval==='1d';
    const period=document.getElementById('stockCount'); const previous=period.value;
    period.replaceChildren();
    const counts=['5m','15m','60m'].includes(interval)?[10,20,30]:[30,60,120,200];
    const label=daily?'거래일':`${interval.replace('m','분')}봉`;
    for(const n of counts) period.add(new Option(`최근 ${n}개 ${label}`,String(n)));
    period.value=counts.includes(Number(previous))?previous:String(counts[0]);
}
document.getElementById('stockInterval').addEventListener('change',updatePeriods);
updatePeriods();
