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
                            responseElement.innerHTML = this.simpleMarkdownToHtml(data.result);
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
                    responseElement.innerHTML = this.simpleMarkdownToHtml(data.response);
                }
            })
            .catch(error => {
                loadingSpinner.style.display = 'none';
                responseElement.style.display = 'block';
                responseElement.innerHTML = `<div class="alert alert-danger">An error occurred: ${error}</div>`;
            });
        });
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