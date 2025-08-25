class ChartManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.charts = {};
        this.chartMeta = {};
        this.currentChartType = 'pie';
    }

    init() {
        this.registerPlugins();
        this.renderAllCharts();
        this.setupChartTypeToggle();
    }

    registerPlugins() {
        // Register datalabels plugin before rendering any charts
        if (window.ChartDataLabels && window.Chart && !window.__datalabelsRegistered) {
            try { window.Chart.register(window.ChartDataLabels); window.__datalabelsRegistered = true; } catch (_) {}
        }

        // Register leader line plugin for pie charts
        if (window.Chart && !window.__leaderLinesRegistered) {
            const leaderLinePlugin = {
                id: 'leaderLinePlugin',
                afterDatasetsDraw(chart, args, pluginOpts) {
                    const { ctx, data } = chart;
                    const meta = chart.getDatasetMeta(0);
                    if (!meta || !meta.data) return;

                    // Allow overriding in options.plugins.leaderLinePlugin
                    const lineColor = pluginOpts?.color || '#666';
                    const lineWidth = pluginOpts?.lineWidth || 1;
                    const elbow = pluginOpts?.elbow || 12;

                    // Read the datalabels offset so lines end where labels start
                    const dlOpts = chart.options?.plugins?.datalabels || {};
                    const dlOffset = (typeof dlOpts.offset === 'function')
                        ? 20
                        : (dlOpts.offset ?? 20);

                    meta.data.forEach((arc, i) => {
                        // Skip hidden/zero slices
                        if (!arc || !isFinite(arc.outerRadius) || arc.circumference === 0) return;

                        const angle = (arc.startAngle + arc.endAngle) / 2;
                        const cx = arc.x, cy = arc.y;

                        // Point at arc edge
                        const x0 = cx + Math.cos(angle) * arc.outerRadius;
                        const y0 = cy + Math.sin(angle) * arc.outerRadius;

                        // Point where datalabel starts (approximate)
                        const x1 = cx + Math.cos(angle) * (arc.outerRadius + dlOffset);
                        const y1 = cy + Math.sin(angle) * (arc.outerRadius + dlOffset);

                        // Small horizontal elbow toward label side
                        const dir = Math.cos(angle) >= 0 ? 1 : -1;
                        const x2 = x1 + dir * elbow;
                        const y2 = y1;

                        ctx.save();
                        ctx.beginPath();
                        ctx.moveTo(x0, y0);
                        ctx.lineTo(x1, y1);
                        ctx.lineTo(x2, y2);
                        ctx.strokeStyle = lineColor;
                        ctx.lineWidth = lineWidth;
                        ctx.stroke();
                        ctx.restore();
                    });
                }
            };
            Chart.register(leaderLinePlugin);
            window.__leaderLinesRegistered = true;
        }
    }

    // Lightweight pattern fallback when patternomaly is unavailable
    createPatternFallback(hexColor, patternIndex = 0) {
        const sz = 12;
        const canvas = document.createElement('canvas');
        canvas.width = sz; canvas.height = sz;
        const ctx = canvas.getContext('2d');
        // background fill in brand color
        ctx.fillStyle = hexColor;
        ctx.fillRect(0, 0, sz, sz);
        // pattern stroke
        ctx.strokeStyle = '#111';
        ctx.lineWidth = 2;
        const kind = ['dot','dash','cross','diag','zigzag','grid'][patternIndex % 6];
        if (kind === 'dot') {
            ctx.fillStyle = '#111';
            ctx.beginPath(); ctx.arc(sz/2, sz/2, 2, 0, Math.PI*2); ctx.fill();
        } else if (kind === 'dash') {
            ctx.beginPath(); ctx.moveTo(2, sz/2); ctx.lineTo(sz-2, sz/2); ctx.stroke();
        } else if (kind === 'cross') {
            ctx.beginPath(); ctx.moveTo(2, 2); ctx.lineTo(sz-2, sz-2); ctx.moveTo(sz-2, 2); ctx.lineTo(2, sz-2); ctx.stroke();
        } else if (kind === 'diag') {
            ctx.beginPath(); ctx.moveTo(0, sz-3); ctx.lineTo(sz-3, 0); ctx.stroke();
        } else if (kind === 'zigzag') {
            ctx.beginPath(); ctx.moveTo(0, sz-3); ctx.lineTo(sz/3, sz-6); ctx.lineTo((2*sz)/3, sz-0); ctx.lineTo(sz, sz-3); ctx.stroke();
        } else if (kind === 'grid') {
            ctx.beginPath(); ctx.moveTo(sz/2, 0); ctx.lineTo(sz/2, sz); ctx.moveTo(0, sz/2); ctx.lineTo(sz, sz/2); ctx.stroke();
        }
        return ctx.createPattern(canvas, 'repeat');
    }

    renderAllCharts() {
        const exposureMetric = this.dashboard.fileType === 'video' ? 'percentage' : 'detections';
        const exposureSuffix = this.dashboard.fileType === 'video' ? '%' : ' detections';
        this.chartMeta = {
            exposure: { metric: exposureMetric, suffix: exposureSuffix, title: 'Exposure Distribution' },
            detections: { metric: 'detections', suffix: ' detections', title: 'Detection Distribution' },
            prominence: { metric: 'prominence_avg_present', suffix: '', title: 'Prominence Distribution' },
            coverage: { metric: 'coverage_avg_present', suffix: '%', title: 'Coverage Distribution' },
            shareVoice: { metric: 'share_of_voice_avg_present', suffix: '%', title: 'Share of Voice Distribution' },
        };
        Object.entries(this.chartMeta).forEach(([id, m]) => {
            this.renderChart(id, m.metric, m.suffix, m.title);
        });
    }

    renderChart(chartId, metric, suffix, title, type = this.currentChartType || 'pie') {
        const canvas = document.getElementById(chartId + 'Chart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const logos = Object.keys(this.dashboard.logoStats)
            .sort((a, b) => {
                const aValue = this.dashboard.logoStats[a][metric] || 0;
                const bValue = this.dashboard.logoStats[b][metric] || 0;
                return bValue - aValue;
            })
            .slice(0, 10);

        const data = logos.map(logo => this.dashboard.logoStats[logo][metric] || 0);

        // Colorblind-safe palette (Okabe-Ito)
        const colors = [
            '#0072B2', '#E69F00', '#009E73', '#CC79A7', '#F0E442',
            '#56B4E9', '#D55E00', '#000000', '#999999', '#7F3C8D'
        ];

        const hasPattern = !!(window.patternomaly && window.patternomaly.draw);
        const patternTypes = ['dot', 'dash', 'cross', 'diamond', 'triangle', 'square'];
        const fills = logos.map((_, i) => {
            const color = colors[i % colors.length];
            if (hasPattern) {
                // Use patternomaly when present
                return window.patternomaly.draw(patternTypes[i % patternTypes.length], color);
            }
            // Fallback pattern generator
            return this.createPatternFallback(color, i);
        });

        const radarFill = hasPattern
            ? window.patternomaly.draw('dot', colors[0])
            : this.createPatternFallback(colors[0], 0);

        // Configure datalabels per chart type and only if plugin is registered
        const hasDatalabels = !!(window.ChartDataLabels && window.__datalabelsRegistered);
        const dlBase = hasDatalabels ? {
            color: '#111',
            clamp: false,        // let labels go outside chartArea
            clip: false,         // IMPORTANT: allow drawing outside
            formatter: (v) => {
                if (typeof v === 'number') {
                    if (suffix.trim() === '%') return v.toFixed(1) + suffix;
                    if (suffix.includes('detections')) return v.toString();
                    if (suffix.trim() === '') return v.toFixed(1); // For Prominence (no suffix)
                    return v.toString() + suffix; // Fallback for any other suffix
                }
                return '';
            },
            font: { weight: '600' }
        } : undefined;
        const dlByType = !hasDatalabels ? undefined : (
            type === 'bar' ? { anchor: 'end', align: 'end' } :
            type === 'pie' ? { 
                anchor: 'end', 
                align: 'end',
                offset: 24,        // push labels out a bit so the line can bend
            } :
            undefined // disable on radar for clarity
        );
        const datalabelsOptions = (dlBase && dlByType) ? { ...dlBase, ...dlByType } : undefined;

        this.charts[chartId] = new Chart(ctx, {
            type: type,
            data: {
                labels: logos,
                datasets: [{
                    label: title,
                    data: data,
                    backgroundColor: type === 'radar' ? radarFill : fills,
                    borderWidth: 2,
                    borderColor: type === 'pie' ? '#fff' : colors
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                aspectRatio: 1.5,
                layout: {
                    padding: 40
                },
                plugins: {
                    ...(datalabelsOptions ? { datalabels: datalabelsOptions } : {}),
                    ...(type === 'pie' && window.__leaderLinesRegistered ? { 
                        leaderLinePlugin: { color: '#666', lineWidth: 1, elbow: 12 } 
                    } : {}),
                    title: {
                        display: false,
                        text: title,
                        font: { size: 16, weight: 'bold' }
                    },
                    legend: {
                        position: type === 'pie' ? 'left' : 'top',
                        labels: { padding: 20, usePointStyle: true, font: { size: 12 } },
                        display: type !== 'bar'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label ?? '';
                                let val = context.raw;
                                if (val === undefined || val === null) {
                                    const p = context.parsed;
                                    if (p && typeof p === 'object') {
                                        val = (p.y !== undefined ? p.y : p.x);
                                    } else {
                                        val = p;
                                    }
                                }
                                if (typeof val === 'number' && suffix.trim() === '%') {
                                    val = val.toFixed(1);
                                }
                                return `${label}: ${val}${suffix}`;
                            }
                        }
                    }
                },
                scales: type === 'bar' ? { y: { beginAtZero: true } } : undefined
            }
        });
    }

    setupChartTypeToggle() {
        const pieRadio = document.getElementById('pieChart');
        const barRadio = document.getElementById('barChart');
        const radarRadio = document.getElementById('radarChart');

        const rebuildAll = (type) => {
            this.currentChartType = type;
            // destroy existing
            Object.values(this.charts).forEach(ch => { try { ch.destroy(); } catch(e){} });
            this.charts = {};
            // re-render
            Object.entries(this.chartMeta).forEach(([id, m]) => {
                this.renderChart(id, m.metric, m.suffix, m.title, type);
            });
        };

        pieRadio?.addEventListener('change', () => rebuildAll('pie'));
        barRadio?.addEventListener('change', () => rebuildAll('bar'));
        radarRadio?.addEventListener('change', () => rebuildAll('radar'));
    }
}
