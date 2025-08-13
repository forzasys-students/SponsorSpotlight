class Dashboard {
    constructor(fileHash, fileType) {
        this.fileHash = fileHash;
        this.fileType = fileType;
        this.logoStats = {};
        this.videoMetadata = {};
        this.charts = {};
    }

    async init() {
        try {
            await this.loadData();
                    this.initializeOverview();
        this.initializeDetailed();
        this.initializeInsights();
        this.setupEventListeners();
        this.setupAgentInterface();
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
    }

    initializeOverview() {
        this.updateKeyMetrics();
        this.renderTopPerformers();
        this.renderExposureChart();
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

            // Compute highest overall coverage (fallback to present coverage if overall not available)
            const coverageScore = (logo) => {
                const s = this.logoStats[logo] || {};
                const overall = Number(s.coverage_avg_overall);
                const present = Number(s.coverage_avg_present);
                if (!isNaN(overall) && overall > 0) return overall;
                if (!isNaN(present) && present > 0) return present;
                return 0;
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

    renderExposureChart() {
        const ctx = document.getElementById('exposureChart').getContext('2d');
        const logos = Object.keys(this.logoStats)
            .sort((a, b) => {
                if (this.fileType === 'video') {
                    return (this.logoStats[b].percentage || 0) - (this.logoStats[a].percentage || 0);
                }
                return this.logoStats[b].detections - this.logoStats[a].detections;
            })
            .slice(0, 10);

        const data = logos.map(logo => 
            this.fileType === 'video' ? 
            (this.logoStats[logo].percentage || 0) : 
            this.logoStats[logo].detections
        );

        const colors = [
            '#58a6ff', '#3fb950', '#ff7b72', '#a5a5ff', '#ffab70',
            '#f85149', '#fd8c73', '#79c0ff', '#7ee787', '#ffa657'
        ];

        this.charts.exposure = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: logos,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label;
                                const value = context.parsed;
                                const suffix = this.fileType === 'video' ? '%' : ' detections';
                                return `${label}: ${value}${suffix}`;
                            }
                        }
                    }
                }
            }
        });
    }



    initializeDetailed() {
        this.renderDetailedTable();
        this.setupTableFiltering();
    }

    renderDetailedTable() {
        const tbody = document.getElementById('detailedTableBody');
        const logos = Object.keys(this.logoStats);

        tbody.innerHTML = logos.map(logo => {
            const logoData = this.logoStats[logo];
            
            let row = `
                <tr>
                    <td><strong>${logo}</strong></td>
                    <td>${logoData.detections}</td>
            `;

            if (this.fileType === 'video') {
                const avgPerFrame = logoData.frames > 0 ? 
                    (logoData.detections / logoData.frames).toFixed(2) : '0.00';
                const avgCoverage = (logoData.coverage_avg_present || 0).toFixed(2);
                const maxCoverage = (logoData.coverage_max || 0).toFixed(2);
                
                row += `
                    <td>${logoData.frames || 0}</td>
                    <td>${(logoData.time || 0).toFixed(1)}</td>
                    <td>${(logoData.percentage || 0).toFixed(1)}%</td>
                    <td>${avgPerFrame}</td>
                    <td>${avgCoverage}%</td>
                    <td>${maxCoverage}%</td>
                `;
            }

            row += `</tr>`;

            return row;
        }).join('');
    }

    calculatePerformance(logoData) {
        let score = 0;
        
        if (this.fileType === 'video') {
            const percentage = logoData.percentage || 0;
            if (percentage >= 10) score = 4;
            else if (percentage >= 5) score = 3;
            else if (percentage >= 1) score = 2;
            else score = 1;
        } else {
            const detections = logoData.detections;
            if (detections >= 10) score = 4;
            else if (detections >= 5) score = 3;
            else if (detections >= 2) score = 2;
            else score = 1;
        }

        const performances = {
            4: { class: 'excellent', label: 'Excellent' },
            3: { class: 'good', label: 'Good' },
            2: { class: 'average', label: 'Average' },
            1: { class: 'poor', label: 'Poor' }
        };

        return performances[score];
    }

    setupTableFiltering() {
        const searchInput = document.getElementById('searchFilter');
        const sortBy = document.getElementById('sortBy');
        const sortOrder = document.getElementById('sortOrder');

        const filterAndSort = () => {
            const searchTerm = searchInput.value.toLowerCase();
            let filteredLogos = Object.keys(this.logoStats)
                .filter(logo => logo.toLowerCase().includes(searchTerm));

            const sortField = sortBy.value;
            const isDesc = sortOrder.value === 'desc';

            filteredLogos.sort((a, b) => {
                let aVal, bVal;
                const dataA = this.logoStats[a];
                const dataB = this.logoStats[b];
                
                switch(sortField) {
                    case 'name':
                        return isDesc ? b.localeCompare(a) : a.localeCompare(b);
                    case 'detections':
                        return isDesc ? dataB.detections - dataA.detections : dataA.detections - dataB.detections;
                    case 'time':
                        return isDesc ? (dataB.time || 0) - (dataA.time || 0) : (dataA.time || 0) - (dataB.time || 0);
                    case 'percentage':
                        return isDesc ? (dataB.percentage || 0) - (dataA.percentage || 0) : (dataA.percentage || 0) - (dataB.percentage || 0);
                    case 'frames':
                        return isDesc ? (dataB.frames || 0) - (dataA.frames || 0) : (dataA.frames || 0) - (dataB.frames || 0);
                    case 'coverage':
                        return isDesc ? (dataB.coverage_avg_present || 0) - (dataA.coverage_avg_present || 0)
                                      : (dataA.coverage_avg_present || 0) - (dataB.coverage_avg_present || 0);
                    case 'max_coverage':
                        return isDesc ? (dataB.coverage_max || 0) - (dataA.coverage_max || 0)
                                      : (dataA.coverage_max || 0) - (dataB.coverage_max || 0);
                    default:
                        return 0;
                }
            });

            this.updateTableWithFilteredData(filteredLogos);
        };

        searchInput.addEventListener('input', filterAndSort);
        sortBy.addEventListener('change', filterAndSort);
        sortOrder.addEventListener('change', filterAndSort);
    }

    updateTableWithFilteredData(logos) {
        const tbody = document.getElementById('detailedTableBody');
        
        tbody.innerHTML = logos.map(logo => {
            const logoData = this.logoStats[logo];
            
            let row = `
                <tr>
                    <td><strong>${logo}</strong></td>
                    <td>${logoData.detections}</td>
            `;

            if (this.fileType === 'video') {
                const avgPerFrame = logoData.frames > 0 ? 
                    (logoData.detections / logoData.frames).toFixed(2) : '0.00';
                const avgCoverage = (logoData.coverage_avg_present || 0).toFixed(2);
                const maxCoverage = (logoData.coverage_max || 0).toFixed(2);
                
                row += `
                    <td>${logoData.frames || 0}</td>
                    <td>${(logoData.time || 0).toFixed(1)}</td>
                    <td>${(logoData.percentage || 0).toFixed(1)}%</td>
                    <td>${avgPerFrame}</td>
                    <td>${avgCoverage}%</td>
                    <td>${maxCoverage}%</td>
                `;
            }

            row += `</tr>`;

            return row;
        }).join('');
    }

    initializeInsights() {
        this.generateInsights();
        this.renderPerformanceChart();
        if (this.fileType === 'video') {
            this.renderEngagementChart();
        }
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

    renderPerformanceChart() {
        const ctx = document.getElementById('performanceChart').getContext('2d');
        const logos = Object.keys(this.logoStats).slice(0, 8);
        if (logos.length === 0) return;

        const performanceData = logos.map(logo => {
            const logoData = this.logoStats[logo];
            return this.fileType === 'video' ? (logoData.percentage || 0) : logoData.detections;
        });

        this.charts.performance = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: logos,
                datasets: [{
                    label: this.fileType === 'video' ? 'Exposure %' : 'Detections',
                    data: performanceData,
                    fill: true,
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgb(54, 162, 235)',
                    pointBackgroundColor: 'rgb(54, 162, 235)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(54, 162, 235)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                elements: {
                    line: {
                        borderWidth: 3
                    }
                }
            }
        });
    }

    renderEngagementChart() {
        if (this.fileType !== 'video') return;

        const ctx = document.getElementById('engagementChart').getContext('2d');
        const logos = Object.keys(this.logoStats).slice(0, 10);
        if (logos.length === 0) return;

        const engagementData = logos.map(logo => {
            const logoData = this.logoStats[logo];
            const frames = logoData.frames || 0;
            const detections = logoData.detections || 0;
            return frames > 0 ? (detections / frames) * 100 : 0;
        });

        this.charts.engagement = new Chart(ctx, {
            type: 'line',
            data: {
                labels: logos,
                datasets: [{
                    label: 'Engagement Rate (%)',
                    data: engagementData,
                    fill: false,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Engagement Rate (%)'
                        }
                    }
                }
            }
        });
    }

    setupEventListeners() {
        // Chart type toggle
        const chartTypeInputs = document.querySelectorAll('input[name="chartType"]');
        chartTypeInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                if (this.charts.exposure) {
                    this.charts.exposure.destroy();
                }
                
                const chartType = e.target.id === 'pieChart' ? 'pie' : 'bar';
                this.updateExposureChartType(chartType);
            });
        });
    }

    updateExposureChartType(type) {
        const ctx = document.getElementById('exposureChart').getContext('2d');
        const logos = Object.keys(this.logoStats)
            .sort((a, b) => {
                if (this.fileType === 'video') {
                    return (this.logoStats[b].percentage || 0) - (this.logoStats[a].percentage || 0);
                }
                return this.logoStats[b].detections - this.logoStats[a].detections;
            })
            .slice(0, 10);

        const data = logos.map(logo => 
            this.fileType === 'video' ? 
            (this.logoStats[logo].percentage || 0) : 
            this.logoStats[logo].detections
        );

        const colors = [
            '#58a6ff', '#3fb950', '#ff7b72', '#a5a5ff', '#ffab70',
            '#f85149', '#fd8c73', '#79c0ff', '#7ee787', '#ffa657'
        ];

        const config = {
            type: type,
            data: {
                labels: logos,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: type === 'pie' ? '#fff' : colors
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: type === 'pie' ? 'bottom' : 'top',
                        display: type === 'pie'
                    }
                }
            }
        };

        if (type === 'bar') {
            config.options.scales = {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: this.fileType === 'video' ? 'Exposure (%)' : 'Detections'
                    }
                }
            };
        }

        this.charts.exposure = new Chart(ctx, config);
    }

    setupAgentInterface() {
        const queryInput = document.getElementById('agent-query-input');
        const queryButton = document.getElementById('agent-query-button');
        const responseContainer = document.getElementById('agent-response-container');
        const loadingSpinner = document.getElementById('agent-loading');
        const responseElement = document.getElementById('agent-response');
        const loadingText = loadingSpinner.querySelector('p');
        const suggestionsContainer = document.getElementById('agent-suggestions');
        const refreshSuggestionsBtn = document.getElementById('agent-refresh-suggestions');
        const videoContainer = document.getElementById('agent-video-container');

        const pollTaskStatus = (taskId) => {
            const interval = setInterval(() => {
                fetch(`/api/agent_task_status/${taskId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status !== 'not_found') {
                            loadingText.textContent = data.message;
                        }

                        if (data.is_complete) {
                            clearInterval(interval);
                            loadingSpinner.style.display = 'none';
                            responseElement.style.display = 'block';
                            this.renderAgentResponseUI(data.result, responseElement, videoContainer);
                        }
                    })
                    .catch(error => {
                        clearInterval(interval);
                        loadingSpinner.style.display = 'none';
                        responseElement.style.display = 'block';
                        responseElement.innerHTML = `<div class="alert alert-danger">Error polling task status: ${error}</div>`;
                    });
            }, 2000); // Poll every 2 seconds
        };

        queryButton.addEventListener('click', () => {
            const query = queryInput.value.trim();
            if (!query) return;

            responseContainer.style.display = 'block';
            loadingSpinner.style.display = 'block';
            responseElement.style.display = 'none';
            loadingText.textContent = "Sending request to agent...";

            fetch(`/api/agent_query/${this.fileHash}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            })
            .then(response => response.json())
            .then(data => {
                if (data.task_id) {
                    // This is an async task, start polling
                    pollTaskStatus(data.task_id);
                } else {
                    // This was a sync task (like analysis)
                    loadingSpinner.style.display = 'none';
                    responseElement.style.display = 'block';
                    this.renderAgentResponseUI(data.response, responseElement, videoContainer);
                }
            })
            .catch(error => {
                loadingSpinner.style.display = 'none';
                responseElement.style.display = 'block';
                responseElement.innerHTML = `<div class="alert alert-danger">An error occurred: ${error}</div>`;
            });
        });

        const baseSuggestions = () => {
            const brands = Object.keys(this.logoStats).slice(0, 6);
            const top = brands[0] || 'top brand';
            const second = brands[1] || 'another brand';
            const third = brands[2] || 'third brand';
            const videoSpecific = this.fileType === 'video';
            const suggestions = [
                `Analyze the video and summarize key insights`,
                `Which are the top 3 brands by exposure percentage?`,
                `Find the best 10-second clip featuring ${top}`,
                videoSpecific ? `Create a 5-second clip with ${top}` : null,
                videoSpecific ? `Create a 4-second clip with ${second}` : null,
                videoSpecific ? `Generate a caption to share a clip of ${third}` : null,
                `Compare ${top} vs ${second} exposure`,
                `List brands with less than 1% exposure`
            ].filter(Boolean);
            return suggestions;
        };

        const suggestionTemplates = () => ([
            { icon: 'bi-robot', hint: 'AI analysis', text: 'Analyze the video and summarize key insights' },
            { icon: 'bi-trophy', hint: 'Top performers', text: 'Which are the top 3 brands by exposure percentage?' },
            { icon: 'bi-film', hint: 'Clip (10s)', text: `Find the best 10-second clip featuring ${Object.keys(this.logoStats)[0] || 'top brand'}` },
            this.fileType === 'video' ? { icon: 'bi-scissors', hint: 'Clip (5s)', text: `Create a 5-second clip with ${Object.keys(this.logoStats)[0] || 'top brand'}` } : null,
            this.fileType === 'video' ? { icon: 'bi-scissors', hint: 'Clip (4s)', text: `Create a 4-second clip with ${Object.keys(this.logoStats)[1] || 'another brand'}` } : null,
            this.fileType === 'video' ? { icon: 'bi-hash', hint: 'Social caption', text: `Generate a caption to share a clip of ${Object.keys(this.logoStats)[2] || 'third brand'}` } : null,
            { icon: 'bi-bar-chart', hint: 'Compare', text: `Compare ${(Object.keys(this.logoStats)[0] || 'Brand A')} vs ${(Object.keys(this.logoStats)[1] || 'Brand B')} exposure` },
            { icon: 'bi-filter', hint: 'Low exposure', text: 'List brands with less than 1% exposure' },
        ].filter(Boolean));

        const renderSuggestions = () => {
            if (!suggestionsContainer) return;
            const items = suggestionTemplates();
            suggestionsContainer.innerHTML = items.map(({ icon, hint, text }) => `
                <div class="suggestion-item d-flex align-items-start">
                    <div class="suggestion-icon me-2"><i class="bi ${icon}"></i></div>
                    <div class="flex-grow-1">
                        <div class="suggestion-title">${text}</div>
                        <div class="suggestion-hint">${hint}</div>
                    </div>
                </div>
            `).join('');
            Array.from(suggestionsContainer.querySelectorAll('.suggestion-item')).forEach(item => {
                item.addEventListener('click', () => {
                    const title = item.querySelector('.suggestion-title')?.textContent || '';
                    queryInput.value = title;
                    queryInput.focus();
                });
            });
        };

        renderSuggestions();
        if (refreshSuggestionsBtn) {
            refreshSuggestionsBtn.addEventListener('click', renderSuggestions);
        }

        // Quick action: create clip from rank table
        document.addEventListener('click', (e) => {
            const btn = e.target?.closest('[data-action="suggest-clip"]');
            if (!btn) return;
            const brand = btn.getAttribute('data-brand');
            if (!brand) return;
            queryInput.value = `Create a 5-second clip with ${brand}`;
            queryButton.click();
        });
    }

    renderAgentResponseUI(markdown, responseEl, videoContainer) {
        const rawUrl = this.extractMp4Url(markdown);
        const url = this.normalizeStaticUrl(rawUrl);

        let cleanedMarkdown = markdown;
        if (rawUrl) {
            const lines = markdown.split(/\n+/);
            cleanedMarkdown = lines.filter(l => !l.includes('.mp4')).join('\n');
        }
        // Detect embedded RANK_JSON for structured rendering (tolerant to single quotes)
        const rankJson = this.parseRankJson(cleanedMarkdown);
        // Remove the RANK_JSON line from prose before rendering markdown
        const proseWithoutRank = cleanedMarkdown
            .split(/\n+/)
            .filter(line => !/^\s*RANK_JSON:\s*/.test(line))
            .join('\n');
        const contentHtml = this.simpleMarkdownToHtml(proseWithoutRank || '');

        if (url) {
            const rankTableHtml = rankJson ? this.renderRankTable(rankJson) : '';
            responseEl.innerHTML = `
                <div class="agent-result-card card">
                    <div class="card-header d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-check-circle-fill text-success me-2"></i>
                            <strong>Clip created</strong>
                        </div>
                        <div class="d-flex gap-2">
                            <a class="btn btn-sm btn-outline-primary" href="${url}" target="_blank" rel="noopener">Open clip</a>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="text-muted small mb-2">${contentHtml}</div>
                        ${rankTableHtml}
                        <code class="small text-secondary">${url}</code>
                    </div>
                </div>
            `;
            this.renderInlineVideoIfAny(url, videoContainer, true);
        } else {
            const rankTableHtml = rankJson ? this.renderRankTable(rankJson) : '';
            responseEl.innerHTML = `
                <div class="agent-result-card card">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-robot me-2"></i>
                        <strong>Agent response</strong>
                    </div>
                    <div class="card-body">
                        ${contentHtml}
                        ${rankTableHtml}
                    </div>
                </div>
            `;
            if (videoContainer) {
                videoContainer.style.display = 'none';
                videoContainer.innerHTML = '';
            }
        }
    }

    parseRankJson(markdown) {
        if (!markdown) return null;
        const match = markdown.match(/RANK_JSON:\s*({[\s\S]*?})\s*$/m);
        if (!match) return null;
        const blob = match[1];
        // Try strict JSON first
        try { return JSON.parse(blob); } catch (_) {}
        // Normalize single quotes and trailing commas then retry
        try {
            let normalized = blob.replace(/'/g, '"');
            normalized = normalized.replace(/,(\s*[}\]])/g, '$1');
            return JSON.parse(normalized);
        } catch (_) {
            return null;
        }
    }

    renderRankTable(rankJson) {
        const items = Array.isArray(rankJson.items) ? rankJson.items : [];
        if (!items.length) return '';
        const metric = rankJson.metric || '';
        const dir = rankJson.direction || 'desc';
        const header = `Top ${items.length} by ${metric} (${dir})`;
        return `
            <div class="table-responsive mt-2">
                <table class="table table-sm align-middle mb-2">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Brand</th>
                            <th>${metric}</th>
                            <th class="text-end">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map((it, idx) => `
                            <tr>
                                <td>${idx + 1}</td>
                                <td>${it.brand}</td>
                                <td>${it.formatted_value ?? it.value}</td>
                                <td class="text-end">
                                    ${this.fileType === 'video' ? `<button type="button" class="btn btn-sm btn-outline-secondary" data-action="suggest-clip" data-brand="${it.brand}">Create 5s clip</button>` : ''}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    extractMp4Url(markdown) {
        if (!markdown) return null;
        // Common markdown and HTML link patterns
        let m = markdown.match(/\(([^)]+\.mp4)\)/i) || markdown.match(/href=["']([^"']+\.mp4)["']/i);
        if (m && m[1]) return m[1];
        // Backticked code path `...mp4`
        m = markdown.match(/`([^`]+\.mp4)`/i);
        if (m && m[1]) return m[1];
        // Direct static served path anywhere in the text
        m = markdown.match(/(\/static\/results\/[\S]+?\.mp4)/i);
        if (m && m[1]) return m[1];
        // Fallback: any token ending with .mp4
        m = markdown.match(/([\S]+?\.mp4)/i);
        return m ? m[1] : null;
    }

    normalizeStaticUrl(rawUrl) {
        if (!rawUrl) return null;
        const marker = '/static/results/';
        const pos = rawUrl.indexOf(marker);
        if (pos === -1) return null;
        let url = rawUrl.slice(pos);
        if (!url.startsWith('/')) url = '/' + url;
        return url;
    }

    renderInlineVideoIfAny(sourceOrMarkdown, container, isUrl = false) {
        try {
            if (!container || !sourceOrMarkdown) return;
            let url = null;
            if (isUrl) {
                url = sourceOrMarkdown;
            } else {
                const raw = this.extractMp4Url(sourceOrMarkdown);
                url = this.normalizeStaticUrl(raw);
            }
            if (!url) return;

            // Build a video player
            const videoHtml = `
                <div class="card">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-play-circle me-2"></i>
                        <strong>Generated clip preview</strong>
                    </div>
                    <div class="card-body">
                        <video controls preload="metadata" style="width: 100%; max-height: 420px; border-radius: 4px;">
                            <source src="${url}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                    </div>
                </div>
            `;
            container.innerHTML = videoHtml;
            container.style.display = 'block';
            // Ensure suggestions column visually aligns with new height while preserving scroll when shorter
            const leftCol = document.getElementById('agent-left-col');
            const suggHeader = document.getElementById('agent-suggestions-header');
            const suggList = document.getElementById('agent-suggestions');
            if (leftCol && suggList) {
                const leftHeight = leftCol.getBoundingClientRect().height;
                const headerHeight = (suggHeader?.getBoundingClientRect().height || 0);
                // Add a small padding offset
                const target = Math.max(280, leftHeight - headerHeight - 24);
                suggList.style.maxHeight = `${target}px`;
                suggList.style.overflowY = 'auto';
            }
        } catch (_) {
            // no-op
        }
    }

    simpleMarkdownToHtml(markdown) {
        // Basic markdown conversion for demonstration purposes.
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return markdown
            .replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
            .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*)\*/gim, '<em>$1</em>')
            .replace(/^- (.*$)/gim, '<li>$1</li>')
            .replace(/^\* (.*$)/gim, '<li>$1</li>')
            .replace(/(\n\s*-\s*.*)+/gim, (match) => `<ul>${match.replace(/^\s*-\s*/gm, '<li>')}</ul>`)
            .replace(/(\n\s*\*\s*.*)+/gim, (match) => `<ul>${match.replace(/^\s*\*\s*/gm, '<li>')}</ul>`)
            .replace(/\n$/gim, '<br />');
    }

    showError(message) {
        console.error(message);
        // You could add a toast notification here
    }
}