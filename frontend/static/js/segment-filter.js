class SegmentFilter {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.init();
    }

    init() {
        const btn = document.getElementById('runSegmentFilter');
        if (!btn) return;

        this.setupSegmentFiltering();
    }

    setupSegmentFiltering() {
        const btn = document.getElementById('runSegmentFilter');
        const out = document.getElementById('segmentResults');
        const logoSelect = document.getElementById('segFilterLogo');
        const maxCovHint = document.getElementById('maxCoverageHint');
        const maxPromHint = document.getElementById('maxProminenceHint');
        if (!btn || !out || !logoSelect) return;

        // Populate logo dropdown
        const logos = Object.keys(this.dashboard.logoStats).sort();
        logos.forEach(logo => {
            const option = document.createElement('option');
            option.value = logo;
            option.textContent = logo;
            logoSelect.appendChild(option);
        });

        // Update max hints when logo changes
        const updateHints = () => {
            const selectedLogo = logoSelect.value;
            if (selectedLogo && this.dashboard.logoStats[selectedLogo]) {
                const stats = this.dashboard.logoStats[selectedLogo];
                maxCovHint.textContent = `max: ${(stats.coverage_avg_present || 0).toFixed(2)}%`;
                maxPromHint.textContent = `max: ${(stats.prominence_avg_present || 0).toFixed(1)}`;
            } else {
                // Show global maxes
                const maxCov = Math.max(...Object.values(this.dashboard.logoStats).map(s => s.coverage_avg_present || 0));
                const maxProm = Math.max(...Object.values(this.dashboard.logoStats).map(s => s.prominence_avg_present || 0));
                maxCovHint.textContent = `max: ${maxCov.toFixed(2)}%`;
                maxPromHint.textContent = `max: ${maxProm.toFixed(1)}`;
            }
        };

        logoSelect.addEventListener('change', updateHints);
        updateHints(); // Initial load

        const fps = Number(this.dashboard.videoMetadata.fps) || 25;
        const toTime = (frame) => (frame / fps).toFixed(2);

        btn.addEventListener('click', () => {
            const logoQ = (logoSelect.value || '').trim().toLowerCase();
            const minCov = Number(document.getElementById('segMinCoverage')?.value) || 0;
            const minProm = Number(document.getElementById('segMinProminence')?.value) || 0;
            const mergeGapSec = 1; // seconds
            const minDurationSec = 1.0; // seconds

            const covData = (this.dashboard.coveragePerFrame && this.dashboard.coveragePerFrame.per_logo) || {};
            const promData = (this.dashboard.prominencePerFrame && this.dashboard.prominencePerFrame.per_logo) || {};
            const logos = Object.keys(this.dashboard.logoStats).filter(l => !logoQ || l.toLowerCase().includes(logoQ));
            if (logos.length === 0) {
                out.innerHTML = '<div class="alert alert-warning">No logos match your query.</div>';
                return;
            }

            const rawSegments = this.findRawSegments(logos, covData, promData, minCov, minProm);
            const results = this.mergeAndFilterSegments(rawSegments, fps, mergeGapSec, minDurationSec);
            this.renderSegmentResults(results, toTime);
        });
    }

    findRawSegments(logos, covData, promData, minCov, minProm) {
        const rawSegments = [];
        logos.forEach(logo => {
            const covSeries = covData[logo] || [];
            const promSeries = promData[logo] || [];
            const presentFrames = (this.dashboard.timelineStats && this.dashboard.timelineStats[logo]) || [];
            const presentSet = new Set(presentFrames);

            let start = null;
            const flush = (endFrame) => {
                if (start !== null) {
                    rawSegments.push({ logo, start, end: endFrame });
                    start = null;
                }
            };

            const maxLen = Math.max(covSeries.length, promSeries.length);
            for (let f = 0; f < maxLen; f++) {
                const isPresent = presentSet.size === 0 ? true : presentSet.has(f + 1);
                const covOk = (covSeries[f] || 0) >= minCov;
                const promOk = (promSeries[f] || 0) >= minProm;
                if (isPresent && covOk && promOk) {
                    if (start === null) start = f;
                } else {
                    flush(f - 1);
                }
            }
            flush(maxLen - 1);
        });
        return rawSegments;
    }
    
    mergeAndFilterSegments(rawSegments, fps, mergeGapSec, minDurationSec) {
        const merged = [];
        const framesToSec = (frames) => frames / fps;
        rawSegments.sort((a,b) => a.start - b.start);
        
        rawSegments.forEach(seg => {
            if (merged.length === 0) {
                merged.push({...seg});
                return;
            }
            const last = merged[merged.length - 1];
            const gapFrames = seg.start - (last.end + 1);
            const gapSec = framesToSec(Math.max(0, gapFrames));
            if (seg.logo === last.logo && gapSec <= mergeGapSec) {
                if (seg.end > last.end) last.end = seg.end;
            } else {
                merged.push({...seg});
            }
        });

        return merged.filter(seg => framesToSec(seg.end - seg.start + 1) >= minDurationSec);
    }

    renderSegmentResults(results, toTime) {
        const out = document.getElementById('segmentResults');
        if (results.length === 0) {
            out.innerHTML = '<div class="alert alert-info">No segments found for the given conditions.</div>';
            return;
        }

        out.innerHTML = `
            <div class="list-group">
                ${results.slice(0, 50).map(r => `
                    <div class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${r.logo}</strong>
                            <span class="text-muted ms-2">${toTime(r.start)}s - ${toTime(r.end)}s</span>
                        </div>
                        <div>
                            <code class="me-2">frames ${r.start} - ${r.end}</code>
                            <a href="${this.dashboard.getVideoPlayerUrl(toTime(r.start), toTime(r.end), r.logo)}" class="btn btn-sm btn-primary">
                                <i class="bi bi-play-fill"></i> Watch Segment
                            </a>
                        </div>
                    </div>
                `).join('')}
            </div>
            ${results.length > 50 ? `<div class="mt-2 text-muted">Showing first 50 of ${results.length} segments</div>` : ''}
        `;
    }
}
