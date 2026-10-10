/* Pure navigation state, shared by UI and node regression tests. */
class ChartNavigator {
    constructor(length = 0) { this.reset(length); }
    reset(length) { this.length = length; this.currentIndex = 0; }
    seek(index) { this.currentIndex = Math.max(0, Math.min(this.length - 1, Math.round(Number(index) || 0))); return this.currentIndex; }
    move(delta) { return this.seek(this.currentIndex + delta); }
    range(mode, count = 10, start = 1, end = this.length) {
        const n = Math.max(1, Math.floor(Number(count) || 1)), i = this.currentIndex;
        if (mode === 'current') return [i, this.length - 1];
        if (mode === 'previous') return [Math.max(0, i - n), Math.max(0, i - 1)];
        if (mode === 'next') return [Math.min(this.length - 1, i + 1), Math.min(this.length - 1, i + n)];
        if (mode === 'custom') {
            if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end > this.length || start > end) throw Error('시작·끝 봉 범위를 확인하세요.');
            return [start - 1, end - 1];
        }
        return [0, this.length - 1];
    }
}
if (typeof module !== 'undefined') module.exports = { ChartNavigator };
