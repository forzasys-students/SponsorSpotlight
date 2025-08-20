class Dashboard {
    constructor(fileHash, fileType) {
        this.fileHash = fileHash;
        this.fileType = fileType;
        this.logoStats = {};
        this.videoMetadata = {};
        this.charts = {};
        this.chartMeta = {};
        this.currentChartType = 'pie';
    }
    
    getVideoPlayerUrl(startTime, endTime, logo) {
        // Create a URL that points back to the results page with timestamp parameters and logo
        const logoPart = logo ? `&logo=${encodeURIComponent(logo)}` : '';
        return `/results/${this.fileHash}?t=${startTime}&end=${endTime}${logoPart}`;
    }

    async init() {
        try {
            await this.loadData();
            this.initializeOverview();
            
            this.detailedViewManager = new DetailedViewManager(this);
            this.detailedViewManager.init();

            this.initializeInsights();
            this.setupEventListeners();
            
            this.agentInterface = new AgentInterface(this);
            this.agentInterface.init();
        } catch (error) {
            console.error('Failed to initialize dashboard:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    async loadData() {
        const response = await fetch(`/api/stats/${this.fileHash}`);
        if (!response.ok) {
            throw new Error('Failed to fetch data');
        }
        const data = await response.json();
        this.logoStats = data.logo_stats || {};
        this.videoMetadata = data.video_metadata || {};
        // Preload per-frame series if video for segment filtering
        if (this.fileType === 'video') {
            try {
                const covResp = await fetch(`/api/coverage_per_frame/${this.fileHash}`);
                if (covResp.ok) {
                    this.coveragePerFrame = await covResp.json();
                }
            } catch {}
            try {
                const promResp = await fetch(`/api/prominence_per_frame/${this.fileHash}`);
                if (promResp.ok) {
                    this.prominencePerFrame = await promResp.json();
                }
            } catch {}
            try {
                const tlResp = await fetch(`/api/timeline_stats/${this.fileHash}`);
                if (tlResp.ok) {
                    this.timelineStats = await tlResp.json();
                }
            } catch {}
        }
    }

    initializeOverview() {
        this.updateKeyMetrics();
        this.renderTopPerformers();
        this.chartManager = new ChartManager(this);
        this.chartManager.init();
    }

    updateKeyMetrics() {
        const logos = Object.keys(this.logoStats);
        const totalDetections = logos.reduce((sum, logo) => sum + this.logoStats[logo].detections, 0);
        const uniqueLogos = logos.length;
        
        let totalExposure = 0;
        let topLogo = '-';
        let topCoverageLogo = '-';
        let topCoverageValue = 0;
        
        if (this.fileType === 'video') {
            totalExposure = logos.reduce((sum, logo) => sum + (this.logoStats[logo].time || 0), 0);
            topLogo = logos.sort((a, b) => (this.logoStats[b].percentage || 0) - (this.logoStats[a].percentage || 0))[0] || '-';

            // Compute highest coverage consistently with charts: use coverage_avg_present only
            const coverageScore = (logo) => {
                const s = this.logoStats[logo] || {};
                const present = Number(s.coverage_avg_present);
                return !isNaN(present) && present > 0 ? present : 0;
            };
            if (logos.length > 0) {
                topCoverageLogo = logos.slice().sort((a, b) => coverageScore(b) - coverageScore(a))[0] || '-';
                topCoverageValue = coverageScore(topCoverageLogo) || 0;
            }
        } else {
            topLogo = logos.sort((a, b) => this.logoStats[b].detections - this.logoStats[a].detections)[0] || '-';
        }

        document.getElementById('total-detections').textContent = totalDetections.toLocaleString();
        document.getElementById('unique-logos').textContent = uniqueLogos;
        document.getElementById('total-exposure').textContent = this.fileType === 'video' ? 
            `${totalExposure.toFixed(1)}s` : 'N/A';
        document.getElementById('top-logo').textContent = topLogo.length > 15 ? 
            topLogo.substring(0, 15) + '...' : topLogo;

        // Update Top Coverage card if present
        const topCoverageEl = document.getElementById('top-coverage');
        if (topCoverageEl && this.fileType === 'video') {
            const safeName = (typeof topCoverageLogo === 'string' && topCoverageLogo.length) ? topCoverageLogo : '-';
            const name = safeName.length > 15 ? safeName.substring(0, 15) + '...' : safeName;
            const value = isNaN(topCoverageValue) ? 0 : topCoverageValue;
            topCoverageEl.textContent = `${name}`;
        }

        // Update second row of metrics cards
        this.updateSecondRowMetrics();
    }

    updateSecondRowMetrics() {
        const logos = Object.keys(this.logoStats);
        if (logos.length === 0) return;

        // Top Prominence
        const topProminenceLogo = logos.sort((a, b) => {
            const aProminence = this.logoStats[a].prominence_avg_present || 0;
            const bProminence = this.logoStats[b].prominence_avg_present || 0;
            return bProminence - aProminence;
        })[0];
        const topProminenceEl = document.getElementById('top-prominence');
        if (topProminenceEl) {
            const name = topProminenceLogo.length > 15 ? topProminenceLogo.substring(0, 15) + '...' : topProminenceLogo;
            topProminenceEl.textContent = name;
        }

        // Top Share of Voice
        const topShareVoiceLogo = logos.sort((a, b) => {
            const aShareVoice = this.logoStats[a].share_of_voice_avg_present || 0;
            const bShareVoice = this.logoStats[b].share_of_voice_avg_present || 0;
            return bShareVoice - aShareVoice;
        })[0];
        const topShareVoiceEl = document.getElementById('top-share-voice');
        if (topShareVoiceEl) {
            const name = topShareVoiceLogo.length > 15 ? topShareVoiceLogo.substring(0, 15) + '...' : topShareVoiceLogo;
            topShareVoiceEl.textContent = name;
        }

        // Top Solo Time
        const topSoloTimeLogo = logos.sort((a, b) => {
            const aSoloTime = this.logoStats[a].share_of_voice_solo_percentage || 0;
            const bSoloTime = this.logoStats[b].share_of_voice_solo_percentage || 0;
            return bSoloTime - aSoloTime;
        })[0];
        const topSoloTimeEl = document.getElementById('top-solo-time');
        if (topSoloTimeEl) {
            const name = topSoloTimeLogo.length > 15 ? topSoloTimeLogo.substring(0, 15) + '...' : topSoloTimeLogo;
            topSoloTimeEl.textContent = name;
        }

        // Top Detection
        const topDetectionLogo = logos.sort((a, b) => {
            const aDetections = this.logoStats[a].detections || 0;
            const bDetections = this.logoStats[b].detections || 0;
            return bDetections - aDetections;
        })[0];
        const topDetectionEl = document.getElementById('top-detection');
        if (topDetectionEl) {
            const name = topDetectionLogo.length > 15 ? topDetectionLogo.substring(0, 15) + '...' : topDetectionLogo;
            topDetectionEl.textContent = name;
        }

        // Top Time
        const topTimeLogo = logos.sort((a, b) => {
            const aTime = this.logoStats[a].time || 0;
            const bTime = this.logoStats[b].time || 0;
            return bTime - aTime;
        })[0];
        const topTimeEl = document.getElementById('top-time');
        if (topTimeEl) {
            const name = topTimeLogo.length > 15 ? topTimeLogo.substring(0, 15) + '...' : topTimeLogo;
            topTimeEl.textContent = name;
        }
    }

    renderTopPerformers() {
        const container = document.getElementById('top-performers-list');
        const logos = Object.keys(this.logoStats)
            .sort((a, b) => {
                if (this.fileType === 'video') {
                    return (this.logoStats[b].percentage || 0) - (this.logoStats[a].percentage || 0);
                }
                return this.logoStats[b].detections - this.logoStats[a].detections;
            })
            .slice(0, 5);

        container.innerHTML = logos.map((logo, index) => {
            const value = this.fileType === 'video' ? 
                `${(this.logoStats[logo].percentage || 0).toFixed(1)}%` : 
                `${this.logoStats[logo].detections} detections`;
            
            return `
                <div class="top-performer rank-${index + 1}">
                    <span class="performer-rank">#${index + 1}</span>
                    <span class="performer-name">${logo}</span>
                    <span class="performer-value">${value}</span>
                </div>
            `;
        }).join('');
    }

    initializeInsights() {
        this.generateInsights();
    }

    generateInsights() {
        const container = document.getElementById('insights-list');
        const logos = Object.keys(this.logoStats);
        if (logos.length === 0) return;
        
        const insights = [];

        if (logos.length > 20) {
            insights.push({
                type: 'info',
                title: 'High Logo Diversity',
                description: `Detected ${logos.length} unique logos, indicating high brand diversity.`
            });
        }

        if (this.fileType === 'video') {
            const topLogo = logos.sort((a, b) => (this.logoStats[b].percentage || 0) - (this.logoStats[a].percentage || 0))[0];
            const topPercentage = this.logoStats[topLogo]?.percentage || 0;
            
            if (topPercentage > 15) {
                insights.push({
                    type: 'success',
                    title: 'Dominant Brand Presence',
                    description: `${topLogo} has exceptional visibility with ${topPercentage.toFixed(1)}% exposure time.`
                });
            }

            const averageExposure = logos.reduce((sum, logo) => sum + (this.logoStats[logo].percentage || 0), 0) / logos.length;
            if (averageExposure < 2 && logos.length > 0) {
                insights.push({
                    type: 'warning',
                    title: 'Low Average Exposure',
                    description: `Average logo exposure is ${averageExposure.toFixed(1)}%. Consider optimizing placement.`
                });
            }
        }

        const totalDetections = logos.reduce((sum, logo) => sum + this.logoStats[logo].detections, 0);
        const avgDetections = logos.length > 0 ? totalDetections / logos.length : 0;
        
        if (avgDetections > 5) {
            insights.push({
                type: 'success',
                title: 'High Detection Rate',
                description: `Average of ${avgDetections.toFixed(1)} detections per logo indicates good visibility.`
            });
        }

        container.innerHTML = insights.map(insight => `
            <div class="insight-item ${insight.type}">
                <div class="insight-title">${insight.title}</div>
                <p class="insight-description">${insight.description}</p>
            </div>
        `).join('');
    }

    setupEventListeners() {
        // Initialize generic metric explainers
        this.initMetricExplainers();
    }

    setupSegmentFiltering() {
        const btn = document.getElementById('runSegmentFilter');
        const out = document.getElementById('segmentResults');
        const logoSelect = document.getElementById('segFilterLogo');
        const maxCovHint = document.getElementById('maxCoverageHint');
        const maxPromHint = document.getElementById('maxProminenceHint');
        if (!btn || !out || !logoSelect) return;

        // Populate logo dropdown
        const logos = Object.keys(this.logoStats).sort();
        logos.forEach(logo => {
            const option = document.createElement('option');
            option.value = logo;
            option.textContent = logo;
            logoSelect.appendChild(option);
        });

        // Update max hints when logo changes
        const updateHints = () => {
            const selectedLogo = logoSelect.value;
            if (selectedLogo && this.logoStats[selectedLogo]) {
                const stats = this.logoStats[selectedLogo];
                maxCovHint.textContent = `max: ${(stats.coverage_avg_present || 0).toFixed(2)}%`;
                maxPromHint.textContent = `max: ${(stats.prominence_avg_present || 0).toFixed(1)}`;
            } else {
                // Show global maxes
                const maxCov = Math.max(...Object.values(this.logoStats).map(s => s.coverage_avg_present || 0));
                const maxProm = Math.max(...Object.values(this.logoStats).map(s => s.prominence_avg_present || 0));
                maxCovHint.textContent = `max: ${maxCov.toFixed(2)}%`;
                maxPromHint.textContent = `max: ${maxProm.toFixed(1)}`;
            }
        };

        logoSelect.addEventListener('change', updateHints);
        updateHints(); // Initial load

        const fps = Number(this.videoMetadata.fps) || 25;
        const toTime = (frame) => (frame / fps).toFixed(2);

        btn.addEventListener('click', () => {
            const logoQ = (logoSelect.value || '').trim().toLowerCase();
            const minCov = Number(document.getElementById('segMinCoverage')?.value) || 0;
            const minProm = Number(document.getElementById('segMinProminence')?.value) || 0;
            //  merge small gaps, drop very short segments
            const mergeGapSec = 1; // seconds
            const minDurationSec = 1.0; // seconds

            const covData = (this.coveragePerFrame && this.coveragePerFrame.per_logo) || {};
            const promData = (this.prominencePerFrame && this.prominencePerFrame.per_logo) || {};
            const logos = Object.keys(this.logoStats).filter(l => !logoQ || l.toLowerCase().includes(logoQ));
            if (logos.length === 0) {
                out.innerHTML = '<div class="alert alert-warning">No logos match your query.</div>';
                return;
            }

            const rawSegments = [];
            logos.forEach(logo => {
                const covSeries = covData[logo] || [];
                const promSeries = promData[logo] || [];
                const presentFrames = (this.timelineStats && this.timelineStats[logo]) || [];
                // Convert presence list to a Set for O(1)
                const presentSet = new Set(presentFrames);

                let start = null;
                const flush = (endFrame) => {
                    if (start !== null) {
                        rawSegments.push({ logo, start, end: endFrame });
                        start = null;
                    }
                };

                // Iterate by frame index based on whichever series is longest
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

            // Merge nearby segments and filter by min duration
            const merged = [];
            const framesToSec = (frames) => frames / fps;
            rawSegments.sort((a,b) => a.start - b.start);
            rawSegments.forEach(seg => {
                if (merged.length === 0) { merged.push({...seg}); return; }
                const last = merged[merged.length - 1];
                const gapFrames = seg.start - (last.end + 1);
                const gapSec = framesToSec(Math.max(0, gapFrames));
                if (seg.logo === last.logo && gapSec <= mergeGapSec) {
                    // merge
                    if (seg.end > last.end) last.end = seg.end;
                } else {
                    merged.push({...seg});
                }
            });

            const results = merged.filter(seg => framesToSec(seg.end - seg.start + 1) >= minDurationSec);

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
                                <a href="${this.getVideoPlayerUrl(toTime(r.start), toTime(r.end), r.logo)}" class="btn btn-sm btn-primary">
                                    <i class="bi bi-play-fill"></i> Watch Segment
                                </a>
                            </div>
                        </div>
                    `).join('')}
                </div>
                ${results.length > 50 ? `<div class="mt-2 text-muted">Showing first 50 of ${results.length} segments</div>` : ''}
            `;

            // Links will open in same tab by default (no target="_blank")
        });
    }

    showError(message) {
        console.error(message);
        // You could add a toast notification here
    }

    initMetricExplainers() {
        try {
            const modal = document.getElementById('explainer-modal');
            const modalTitle = modal?.querySelector('#explainer-modal-title');
            const modalMedia = modal?.querySelector('.explainer-modal-media');
            const modalCopy = modal?.querySelector('.explainer-modal-copy');
            const explainers = document.querySelectorAll('.metric-explainer');
            if (!explainers.length) return;

            explainers.forEach(explainer => {
                const trigger = explainer.querySelector('.info-trigger');
                const popoverId = trigger?.getAttribute('aria-controls');
                const popover = popoverId ? document.getElementById(popoverId) : null;
                const video = popover?.querySelector('video.explain-vid') || null;
                const copy = popover?.querySelector('.copy');
                const learnMore = popover?.querySelector('.learn-more');
                const title = explainer.getAttribute('data-explainer-title') || trigger?.getAttribute('title') || '';
                if (!trigger || !popover) return;

                let closeTimer;
                const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                const show = () => {
                    clearTimeout(closeTimer);
                    popover.hidden = false;
                    trigger.setAttribute('aria-expanded', 'true');
                    if (video && !prefersReduced) {
                        if (video.preload !== 'auto') video.preload = 'auto';
                        video.play().catch(() => {});
                    }
                };
                const hide = () => {
                    closeTimer = setTimeout(() => {
                        popover.hidden = true;
                        trigger.setAttribute('aria-expanded', 'false');
                        if (video) { video.pause(); video.currentTime = 0; }
                    }, 150);
                };

                trigger.addEventListener('mouseenter', show);
                trigger.addEventListener('mouseleave', hide);
                popover.addEventListener('mouseenter', () => { clearTimeout(closeTimer); });
                popover.addEventListener('mouseleave', hide);
                trigger.addEventListener('focus', show);
                trigger.addEventListener('blur', hide);

                trigger.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (window.matchMedia('(hover: none)').matches) {
                        openModal();
                    } else {
                        if (popover.hidden) show(); else hide();
                    }
                });

                learnMore?.addEventListener('click', (e) => { e.preventDefault(); openModal(); });

                function openModal() {
                    if (!modal) return;
                    // Set title
                    if (modalTitle) modalTitle.textContent = title;
                    // Build media
                    if (modalMedia) {
                        const media = video ? video.cloneNode(true) : (popover?.querySelector('img.explain-img')?.cloneNode(true) || null);
                        modalMedia.innerHTML = '';
                        if (media) {
                            if (media.tagName.toLowerCase() === 'video') {
                                media.removeAttribute('loop');
                                media.setAttribute('controls', '');
                                media.setAttribute('preload', 'metadata');
                                media.style.width = '100%';
                                media.style.height = 'auto';
                            } else if (media.tagName.toLowerCase() === 'img') {
                                media.style.width = '100%';
                                media.style.height = 'auto';
                            }
                            modalMedia.appendChild(media);
                            if (media.tagName.toLowerCase() === 'video') {
                                media.play?.().catch(() => {});
                            }
                        }
                    }
                    // Copy text
                    if (modalCopy) {
                        const text = copy?.textContent || '';
                        modalCopy.textContent = text;
                    }
                    modal.hidden = false;
                }
                function closeModal() {
                    if (!modal) return;
                    const mv = modal.querySelector('video.explain-vid');
                    mv?.pause?.();
                    modal.hidden = true;
                }

                modal?.querySelector('.close-modal')?.addEventListener('click', () => closeModal());
                modal?.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

                // Lazy load when section is visible
                const section = explainer;
                if ('IntersectionObserver' in window && video) {
                    const io = new IntersectionObserver((entries) => {
                        entries.forEach((entry) => {
                            if (entry.isIntersecting) {
                                if (video.preload !== 'metadata') video.preload = 'metadata';
                                io.disconnect();
                            }
                        });
                    }, { rootMargin: '200px' });
                    io.observe(section);
                }
            });
        } catch (_) { /* no-op */ }
    }
}