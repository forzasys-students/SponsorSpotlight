class DetailedViewManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
    }

    init() {
        this.renderDetailedTable();
        this.setupTableFiltering();
        this.updateReferenceInfo();
        if (this.dashboard.fileType === 'video') {
            this.segmentFilter = new SegmentFilter(this.dashboard);
        }
    }

    updateReferenceInfo() {
        const infoElement = document.getElementById('reference-info');
        if (!infoElement) return;
        
        if (this.dashboard.fileType === 'video') {
            // For videos, show duration and FPS
            const duration = this.dashboard.videoMetadata.duration || 0;
            const fps = this.dashboard.videoMetadata.fps || 0;
            const formattedDuration = this.formatDuration(duration);
            
            infoElement.innerHTML = `
                <span class="badge bg-secondary me-1">
                    <i class="bi bi-clock"></i> Duration: ${formattedDuration}
                </span>
                <span class="badge bg-secondary">
                    <i class="bi bi-film"></i> FPS: ${fps.toFixed(1)}
                </span>
            `;
        } else {
            // For images, show resolution if available
            const width = this.dashboard.videoMetadata.width || 0;
            const height = this.dashboard.videoMetadata.height || 0;
            
            if (width && height) {
                infoElement.innerHTML = `
                    <span class="badge bg-secondary">
                        <i class="bi bi-image"></i> Resolution: ${width}×${height}
                    </span>
                `;
            } else {
                infoElement.innerHTML = `
                    <span class="badge bg-secondary">
                        <i class="bi bi-image"></i> Image
                    </span>
                `;
            }
        }
    }
    
    formatDuration(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        
        if (mins >= 60) {
            const hours = Math.floor(mins / 60);
            const remainingMins = mins % 60;
            return `${hours}:${remainingMins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    renderDetailedTable() {
        const tbody = document.getElementById('detailedTableBody');
        const logos = Object.keys(this.dashboard.logoStats);
        
        tbody.innerHTML = logos.map(logo => this.getTableRowHTML(logo)).join('');

        // Initialize Bootstrap tooltips for the table headers
        this.initTooltips();
    }
    
    getTableRowHTML(logo) {
        const logoData = this.dashboard.logoStats[logo];
        
        let row = `
            <tr>
                <td><strong>${logo}</strong></td>
                <td>${logoData.detections}</td>
        `;
        
        if (this.dashboard.fileType === 'video') {
            const avgPerFrame = logoData.frames > 0 ? 
                (logoData.detections / logoData.frames).toFixed(2) : '0.00';
            const avgCoverage = (logoData.coverage_avg_present || 0).toFixed(2);
            const maxCoverage = (logoData.coverage_max || 0).toFixed(2);
            const promAvg = (logoData.prominence_avg_present || 0).toFixed(2);
            const promMax = (logoData.prominence_max || 0).toFixed(2);
            const sovAvg = (logoData.share_of_voice_avg_present || 0).toFixed(2);
            const soloPct = (logoData.share_of_voice_solo_percentage || 0).toFixed(2);
            
            row += `
                <td>${logoData.frames || 0}</td>
                <td>${(logoData.time || 0).toFixed(1)}</td>
                <td>${(logoData.percentage || 0).toFixed(1)}%</td>
                <td>${avgPerFrame}</td>
                <td>${avgCoverage}%</td>
                <td>${maxCoverage}%</td>
                <td>${promAvg}</td>
                <td>${promMax}</td>
                <td>${sovAvg}%</td>
                <td>${soloPct}%</td>
            `;
        }

        row += `</tr>`;

        return row;
    }

    setupTableFiltering() {
        const searchInput = document.getElementById('searchFilter');
        const sortBy = document.getElementById('sortBy');
        const sortOrder = document.getElementById('sortOrder');

        const filterAndSort = () => {
            const searchTerm = searchInput.value.toLowerCase();
            let filteredLogos = Object.keys(this.dashboard.logoStats)
                .filter(logo => logo.toLowerCase().includes(searchTerm));

            const sortField = sortBy.value;
            const isDesc = sortOrder.value === 'desc';

            filteredLogos.sort((a, b) => {
                const dataA = this.dashboard.logoStats[a];
                const dataB = this.dashboard.logoStats[b];
                
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
                    case 'prominence_avg_present':
                        return isDesc ? (dataB.prominence_avg_present || 0) - (dataA.prominence_avg_present || 0)
                                      : (dataA.prominence_avg_present || 0) - (dataB.prominence_avg_present || 0);
                    case 'prominence_max':
                        return isDesc ? (dataB.prominence_max || 0) - (dataA.prominence_max || 0)
                                      : (dataA.prominence_max || 0) - (dataB.prominence_max || 0);
                    case 'share_of_voice_avg_present':
                        return isDesc ? (dataB.share_of_voice_avg_present || 0) - (dataA.share_of_voice_avg_present || 0)
                                      : (dataA.share_of_voice_avg_present || 0) - (dataB.share_of_voice_avg_present || 0);
                    case 'share_of_voice_solo_percentage':
                        return isDesc ? (dataB.share_of_voice_solo_percentage || 0) - (dataA.share_of_voice_solo_percentage || 0)
                                      : (dataA.share_of_voice_solo_percentage || 0) - (dataB.share_of_voice_solo_percentage || 0);
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
        tbody.innerHTML = logos.map(logo => this.getTableRowHTML(logo)).join('');
        this.initTooltips();
    }
    
    initTooltips() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}
