class Dashboard {
    constructor(fileHash, fileType) {
        this.fileHash = fileHash;
        this.fileType = fileType;
        this.data = {};
        this.charts = {};
    }

    async init() {
        try {
            await this.loadData();
            this.initializeOverview();
            this.initializeDetailed();
            this.initializeInsights();
            this.setupEventListeners();
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
        this.data = await response.json();
    }

    initializeOverview() {
        this.updateKeyMetrics();
        this.renderTopPerformers();
        this.renderExposureChart();
    }

    updateKeyMetrics() {
        const logos = Object.keys(this.data);
        const totalDetections = logos.reduce((sum, logo) => sum + this.data[logo].detections, 0);
        const uniqueLogos = logos.length;
        
        let totalExposure = 0;
        let topLogo = '-';
        
        if (this.fileType === 'video') {
            totalExposure = logos.reduce((sum, logo) => sum + (this.data[logo].time || 0), 0);
            topLogo = logos.reduce((a, b) => 
                (this.data[a].percentage || 0) > (this.data[b].percentage || 0) ? a : b, logos[0] || '-'
            );
        } else {
            topLogo = logos.reduce((a, b) => 
                this.data[a].detections > this.data[b].detections ? a : b, logos[0] || '-'
            );
        }

        document.getElementById('total-detections').textContent = totalDetections.toLocaleString();
        document.getElementById('unique-logos').textContent = uniqueLogos;
        document.getElementById('total-exposure').textContent = this.fileType === 'video' ? 
            `${totalExposure.toFixed(1)}s` : 'N/A';
        document.getElementById('top-logo').textContent = topLogo.length > 15 ? 
            topLogo.substring(0, 15) + '...' : topLogo;
    }

    renderTopPerformers() {
        const container = document.getElementById('top-performers-list');
        const logos = Object.keys(this.data)
            .sort((a, b) => {
                if (this.fileType === 'video') {
                    return (this.data[b].percentage || 0) - (this.data[a].percentage || 0);
                }
                return this.data[b].detections - this.data[a].detections;
            })
            .slice(0, 5);

        container.innerHTML = logos.map((logo, index) => {
            const value = this.fileType === 'video' ? 
                `${(this.data[logo].percentage || 0).toFixed(1)}%` : 
                `${this.data[logo].detections} detections`;
            
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
        const logos = Object.keys(this.data)
            .sort((a, b) => {
                if (this.fileType === 'video') {
                    return (this.data[b].percentage || 0) - (this.data[a].percentage || 0);
                }
                return this.data[b].detections - this.data[a].detections;
            })
            .slice(0, 10);

        const data = logos.map(logo => 
            this.fileType === 'video' ? 
            (this.data[logo].percentage || 0) : 
            this.data[logo].detections
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
        const logos = Object.keys(this.data);

        tbody.innerHTML = logos.map(logo => {
            const logoData = this.data[logo];
            const performance = this.calculatePerformance(logoData);
            
            let row = `
                <tr>
                    <td><strong>${logo}</strong></td>
                    <td>${logoData.detections}</td>
            `;

            if (this.fileType === 'video') {
                const avgPerFrame = logoData.frames > 0 ? 
                    (logoData.detections / logoData.frames).toFixed(2) : '0.00';
                
                row += `
                    <td>${logoData.frames || 0}</td>
                    <td>${(logoData.time || 0).toFixed(1)}</td>
                    <td>${(logoData.percentage || 0).toFixed(1)}%</td>
                    <td>${avgPerFrame}</td>
                `;
            }

            row += `
                    <td><span class="badge performance-badge performance-${performance.class}">${performance.label}</span></td>
                </tr>
            `;

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
            let filteredLogos = Object.keys(this.data)
                .filter(logo => logo.toLowerCase().includes(searchTerm));

            const sortField = sortBy.value;
            const isDesc = sortOrder.value === 'desc';

            filteredLogos.sort((a, b) => {
                let aVal, bVal;
                
                switch(sortField) {
                    case 'name':
                        aVal = a.toLowerCase();
                        bVal = b.toLowerCase();
                        break;
                    case 'detections':
                        aVal = this.data[a].detections;
                        bVal = this.data[b].detections;
                        break;
                    case 'time':
                        aVal = this.data[a].time || 0;
                        bVal = this.data[b].time || 0;
                        break;
                    case 'percentage':
                        aVal = this.data[a].percentage || 0;
                        bVal = this.data[b].percentage || 0;
                        break;
                    case 'frames':
                        aVal = this.data[a].frames || 0;
                        bVal = this.data[b].frames || 0;
                        break;
                    default:
                        return 0;
                }

                if (typeof aVal === 'string') {
                    return isDesc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
                }
                return isDesc ? bVal - aVal : aVal - bVal;
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
            const logoData = this.data[logo];
            const performance = this.calculatePerformance(logoData);
            
            let row = `
                <tr>
                    <td><strong>${logo}</strong></td>
                    <td>${logoData.detections}</td>
            `;

            if (this.fileType === 'video') {
                const avgPerFrame = logoData.frames > 0 ? 
                    (logoData.detections / logoData.frames).toFixed(2) : '0.00';
                
                row += `
                    <td>${logoData.frames || 0}</td>
                    <td>${(logoData.time || 0).toFixed(1)}</td>
                    <td>${(logoData.percentage || 0).toFixed(1)}%</td>
                    <td>${avgPerFrame}</td>
                `;
            }

            row += `
                    <td><span class="badge performance-badge performance-${performance.class}">${performance.label}</span></td>
                </tr>
            `;

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
        const logos = Object.keys(this.data);
        const insights = [];

        // Total logos insight
        if (logos.length > 20) {
            insights.push({
                type: 'info',
                title: 'High Logo Diversity',
                description: `Detected ${logos.length} unique logos, indicating high brand diversity.`
            });
        }

        // Top performer insight
        if (this.fileType === 'video') {
            const topLogo = logos.reduce((a, b) => 
                (this.data[a].percentage || 0) > (this.data[b].percentage || 0) ? a : b, logos[0]
            );
            const topPercentage = this.data[topLogo]?.percentage || 0;
            
            if (topPercentage > 15) {
                insights.push({
                    type: 'success',
                    title: 'Dominant Brand Presence',
                    description: `${topLogo} has exceptional visibility with ${topPercentage.toFixed(1)}% exposure time.`
                });
            }

            // Exposure distribution insight
            const averageExposure = logos.reduce((sum, logo) => sum + (this.data[logo].percentage || 0), 0) / logos.length;
            if (averageExposure < 2) {
                insights.push({
                    type: 'warning',
                    title: 'Low Average Exposure',
                    description: `Average logo exposure is ${averageExposure.toFixed(1)}%. Consider optimizing placement.`
                });
            }
        }

        // Detection frequency insight
        const totalDetections = logos.reduce((sum, logo) => sum + this.data[logo].detections, 0);
        const avgDetections = totalDetections / logos.length;
        
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
        const logos = Object.keys(this.data).slice(0, 8);
        
        const performanceData = logos.map(logo => {
            const logoData = this.data[logo];
            if (this.fileType === 'video') {
                return logoData.percentage || 0;
            }
            return logoData.detections;
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
        const logos = Object.keys(this.data).slice(0, 10);
        
        const engagementData = logos.map(logo => {
            const logoData = this.data[logo];
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
        const logos = Object.keys(this.data)
            .sort((a, b) => {
                if (this.fileType === 'video') {
                    return (this.data[b].percentage || 0) - (this.data[a].percentage || 0);
                }
                return this.data[b].detections - this.data[a].detections;
            })
            .slice(0, 10);

        const data = logos.map(logo => 
            this.fileType === 'video' ? 
            (this.data[logo].percentage || 0) : 
            this.data[logo].detections
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

    showError(message) {
        console.error(message);
        // You could add a toast notification here
    }
}