document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("uploadForm");
    const errorMsg = document.getElementById("errorMsg");
    const errorMsgFilter = document.getElementById("errorMsgFilter");
    const fileInput = document.querySelector("input[name='file']");
    const urlInput = document.getElementById("videoUrl");
    const videoPlayer = document.getElementById("videoPlayer");
    const imageView = document.getElementById("imageView");
    const exportExcel = document.getElementById("exportExcel");
    const submitButton = document.getElementById("submitButton");
    const loadingCircle = document.getElementById("loadingCircle");
    const dropdown = document.getElementById("categoryDropdown");
    const imageChart = document.getElementById("imageChart");
    const videoChart = document.getElementById("videoChart");
    const chartsContainer = document.getElementById("chartsContainer");
    const filterContainer = document.getElementById("filterContainer");
    const displayContainer = document.getElementById("displayContainer");
    const progressContainer = document.getElementById('progress-container');
    const scroll_button = document.getElementById("scroll-button")

    const loadingMsg = document.createElement("p");
    loadingMsg.textContent = "Loading... Please Wait";
    loadingMsg.style.color = "#007bff";
    loadingMsg.style.textAlign = "center";
    loadingMsg.style.display = "none";
    form.appendChild(loadingMsg);

    let responseData;
    let mediaType;

    const socket = io('http://127.0.0.1:5000');
    let progressSegments = [];

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        errorMsg.textContent = "";
        errorMsgFilter.textContent = "";
        
        submitButton.disabled = true;
        submitButton.style.backgroundColor = "#ccc";
        submitButton.style.cursor = "not-allowed";
        loadingMsg.style.display = "block";
        loadingCircle.style.display = "block";
        progressContainer.style.display = 'block';

        //Reset UI
        imageView.removeAttribute("src");
        videoPlayer.removeAttribute("src");
        displayContainer.style.display = "none";
        chartsContainer.style.display = "none";
        filterContainer.style.display = "none";
        scroll_button.style.display = "none";
            
        let response;
        try {
            if (urlInput.value.trim()) {
                const videoUrl = urlInput.value.trim();
                response = await fetch("/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ videoUrl })
                });

            } else if (fileInput.files.length > 0) {
                const file = fileInput.files[0];
                const formData = new FormData();
                formData.append("file", file);

                response = await fetch("/", {
                    method: "POST",
                    body: formData
                });
            } else {
                throw new Error("Please choose a file or enter a URL.");
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Unknown error");
            }

            responseData = await response.json();
            console.log("Response Data:", responseData);

            const mediaUrl = responseData.fileUrl;
            const stats = responseData.stats;

            // Updating media section
            displayContainer.style.display = "block";
            if (mediaUrl.endsWith(".jpg") || mediaUrl.endsWith(".jpeg") || mediaUrl.endsWith(".png")) {
                imageView.src = mediaUrl;
                imageView.style.display = "block";
                videoPlayer.style.display = "none";
                mediaType = "image";
            } else if (mediaUrl.endsWith(".mp4")) {
                videoPlayer.src = mediaUrl;
                videoPlayer.style.display = "block";
                imageView.style.display = "none";
                videoPlayer.play();
                mediaType = "video";
            } else {
                throw new Error("Unknown media type.");
            }

            updateUIWithData(stats, mediaType);
            exportExcel.style.display = "block";
        } catch (error) {
            errorMsg.textContent = error.message;
            console.error(error);
        } finally {
            // Reactivate button and hide "Loading... Please Wait" message
            setTimeout(() => {
                loadingMsg.style.display = "none";
                loadingCircle.style.display = "none";
                submitButton.disabled = false;
                submitButton.style.backgroundColor = "";
                submitButton.style.cursor = "pointer";
                progressContainer.style.display = "none";

                fileInput.value = "";
                urlInput.value = "";
            }, 500);
        }
    });

    //Wrap funcion for longer labels so they won't take a lot of horizontal space
    function wrapLabels(labels, maxLength = 30) {
        return labels.map(label => {
            let wrappedLabel = '';
            let currentLength = 0;

            const words = label.split(' ');

            /* Add words to the wrapped label, inserting <br> when maxLength is reached. Using this method as Plotly does not support 
            wrapping labels */
            words.forEach(word => {
                if (currentLength + word.length > maxLength) {
                    wrappedLabel += '<br>';
                    currentLength = 0;
                }
                wrappedLabel += word + ' ';
                currentLength += word.length + 1;
            });

            return wrappedLabel.trim();
        });
    }

    function updateUIWithData(stats, mediaType) {
        // Prepare data for Plotly
        const labels = Object.keys(stats);
        if (labels.length === 0) {
            errorMsg.textContent = "No logos detected";
            return;
        } else {
            errorMsg.textContent = "";
        }

        chartsContainer.style.display = "block";
        filterContainer.style.display = "block";
        scroll_button.style.display = "block";

        if (mediaType === "image") {

            const sortedData = labels.map((label, i) => ({
                label,
                detections: stats[label].detections,
            })).sort((a, b) => a.detections - b.detections);

            const sortedLabels = sortedData.map(item => item.label);
            const sortedDetections = sortedData.map(item => item.detections);

            videoChart.style.display = "none";
            imageChart.style.display = "block";

            // Update Image Chart
            updateImageChart(sortedLabels, sortedDetections);

            //Update dropdown menu
            updateDropdown(labels);

        } else {

            /* Sort data after percentages in ascending order (Plotly will showcase largest value at the top).
            All stats are shown in the same chart, but bars are based on % of exposure compared to total time.
            */
            const sortedData = labels.map((label, i) => ({
                label,
                percentage: stats[label].percentage,
                time: stats[label].time,
                frames: stats[label].frames,
                detections: stats[label].detections
            })).sort((a, b) => a.percentage - b.percentage);

            const sortedLabels = sortedData.map(item => item.label);
            const sortedPercentages = sortedData.map(item => item.percentage);

            imageChart.style.display = "none";
            videoChart.style.display = "block";

            // Update chart
            updateVideoChart(sortedLabels, sortedPercentages, stats);

            //Update dropdown menu
            updateDropdown(labels);
        }
    }

    function updateVideoChart(labels, percentages, stats) {
        const wrappedLabels = wrapLabels(labels);

        //Shorter formatted text for bars
        const barTexts = labels.map(logo => {
            const stat = stats[logo];
            return `${stat.percentage}% (f:${stat.frames}, d:${stat.detections}, t:${stat.time})`;
        });
        //Longer formatted text when hovering
        const hoverTexts = labels.map(logo => {
            const stat = stats[logo];
            return `<b>${logo}</b><br>
            Percentage: ${stat.percentage}%<br>
            Frames: ${stat.frames}<br>
            Detections: ${stat.detections}<br>
            Time: ${stat.time}s`;
        });

        const trace = {
            x: percentages,
            y: wrappedLabels, // Use wrapped labels
            type: 'bar',
            orientation: 'h',
            name: 'Exposure percentages',
            marker: { color: 'rgba(75, 192, 192, 0.6)' },
            hoverinfo: 'text',
            hovertext: hoverTexts
        };

        const layout = {
            title: 'Exposure percentages',
            height: Math.max(400, labels.length * 40),
            width: 1000,
            margin: { l: 200, r: 50, t: 50, b: 50 },
            bargap: 0.5,
            yaxis: {
                showticklabels: false,
                showgrid: true,
                gridcolor: '#ddd',
                gridwidth: 1
            },
            //Annotations used for more customization options
            annotations: [
                ...wrappedLabels.map((label, index) => ({
                    x: -0.01,
                    y: index,
                    xref: 'paper',
                    yref: 'y',
                    text: label,
                    showarrow: false,
                    font: { size: 12, color: '#000', family: 'Arial' },
                    bgcolor: '#f9f9f9',
                    bordercolor: '#ccc',
                    borderwidth: 1,
                    borderpad: 4,
                    xanchor: 'right',
                    yanchor: 'middle'
                })),
                //Show value at end of bars
                ...percentages.map((_, index) => ({
                    x: percentages[index],
                    y: index,
                    text: barTexts[index],
                    showarrow: false,
                    font: { size: 12, color: '#000', family: 'Arial' },
                    xanchor: 'left',
                    yanchor: 'middle'
                }))
            ]
        };

        Plotly.purge('imageChart');
        Plotly.purge('videoChart');
        Plotly.newPlot('videoChart', [trace], layout);
    }

    function updateImageChart(labels, detections) {
        const wrappedLabels = wrapLabels(labels);

        // Hover text for each bar
        const hoverTexts = labels.map((logo, index) =>
            `<b>${logo}</b><br>Detections: ${detections[index]}`);

        const trace = {
            x: detections,
            y: wrappedLabels,
            type: 'bar',
            orientation: 'h',
            marker: { color: 'rgba(54, 162, 235, 0.6)' },
            hoverinfo: 'text',
            hovertext: hoverTexts
        };

        const layout = {
            title: 'Logo Detections in Image',
            height: Math.max(400, labels.length * 40),
            width: 1000,
            margin: { l: 200, r: 50, t: 50, b: 50 },
            xaxis: {
                title: 'Number of Detections',
                showgrid: true,
                gridcolor: '#ddd',
                dtick: 1
            },
            yaxis: {
                showticklabels: false
            },
            annotations: [
                ...wrappedLabels.map((label, index) => ({
                    x: -0.01,
                    y: index,
                    xref: 'paper',
                    yref: 'y',
                    text: label,
                    showarrow: false,
                    font: { size: 12, color: '#000', family: 'Arial' },
                    bgcolor: '#f9f9f9',
                    bordercolor: '#ccc',
                    borderwidth: 1,
                    borderpad: 4,
                    xanchor: 'right',
                    yanchor: 'middle'
                })),
                ...detections.map((detection, index) => ({
                    x: detection,
                    y: index,
                    text: `${detection} detections`,
                    showarrow: false,
                    font: { size: 12 },
                    xanchor: 'left',
                    yanchor: 'middle'
                }))
            ]
        };

        // Clear previous chart if exists
        Plotly.purge('imageChart');
        Plotly.purge('videoChart');
        Plotly.newPlot('imageChart', [trace], layout);
    }

    // Option to export data to Excel file
    exportExcel.addEventListener("click", async () => {
        if (!responseData || !responseData.stats) {
            throw new Error("No data to export.");
        }

        const excelHeader = mediaType === "image" 
        ? ["Logo", "Detections"] 
        : ["Logo", "Detections", "Percentage", "Time (s)", "Frames"];

        const dataForExcel = Object.keys(responseData.stats).map(logo => {
            const base = {
                Logo: logo,
                Detections: responseData.stats[logo].detections
            };
            if (mediaType === "video") {
                base.Percentage = responseData.stats[logo].percentage + "%";
                base["Time (s)"] = responseData.stats[logo].time;
                base.Frames = responseData.stats[logo].frames;
            }
            return base;
        });

        const XLSX = await import("https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs");
        const worksheet = XLSX.utils.json_to_sheet(dataForExcel);
        const workbook = XLSX.utils.book_new();

        XLSX.utils.book_append_sheet(workbook, worksheet, "SponsorSpotlight");
        XLSX.utils.sheet_add_aoa(worksheet, [excelHeader], { origin: "A1" });

        let wscols = []
        excelHeader.map(arr => {
            wscols.push({ wch: arr.length + 5 })
        })
        worksheet["!cols"] = wscols;

        XLSX.writeFile(workbook, "SponsorSpotlight.xlsx", { compression: true });
    });

    //Function for scrolling down to chart on button-click
    scroll_button.addEventListener("click", function () {
        filterContainer.scrollIntoView({ behavior: 'smooth' });    
    });  

    //Function for filtering logos in chart.
    document.getElementById("filterButton").addEventListener("click", function () {
        const selectedCategories = Array.from(dropdown.selectedOptions).map(option => option.value);

        const filteredData = Object.keys(responseData.stats)
            .filter(logo => selectedCategories.includes(logo))
            .reduce((acc, logo) => {
                acc[logo] = responseData.stats[logo];
                return acc;
            }, {});
        
        if (filteredData > 0) {
            errorMsgFilter.textContent = "";
            updateUIWithData(filteredData);
        } else {
            errorMsgFilter.textContent = "No logos selected";
        }
    });

    document.getElementById("resetButton").addEventListener("click", function () {
        updateUIWithData(responseData.stats);
    });

    //Updating dropdown with new logos
    function updateDropdown(labels) {
        dropdown.innerHTML = "";

        labels.forEach(label => {
            const option = document.createElement("option");
            option.value = label;
            option.textContent = label;
            dropdown.appendChild(option);
        });
    }

    //Progress tracking
    progressSegments = [
        document.getElementById('stage1'),
        document.getElementById('stage2'), 
        document.getElementById('stage3'),
        document.getElementById('stage4'),
        document.getElementById('stage5'),
        document.getElementById('stage6'),
        document.getElementById('stage7'),
    ];

    socket.on('progress_update', (data) => {
        console.log("Progress update received:", data);
        updateProgressDisplay(data);
    });

    function updateProgressDisplay(data) {
       // progressBar.className = `progress-bar ${getStageClass(data.stage)}`;

        progressSegments.forEach(segment => {
            segment.classList.remove('active', 'completed', 'error');
        });

        // Handle error case
        if (data.stage === -1) {
            progressSegments.forEach(segment => {
                segment.classList.add('error');
            });
            return;
        }

        // Mark completed segments
        for (let i = 0; i < data.stage; i++) {
            if (i < progressSegments.length) {
                progressSegments[i].classList.add('completed');
            }
        }
    
        // Mark current active segment
        if (data.stage < progressSegments.length) {
            progressSegments[data.stage].classList.add('active');
        }
    
        // Special case when all stages are done
        if (data.stage >= progressSegments.length) {
            progressSegments.forEach(segment => {
                segment.classList.add('completed');
            });
        }

        // If current stage is INFERENCE_PROGRESS, update with frame progress
        if (data.stage === 4) {
            const progressText = `Frame ${data.frame} of ${data.total_frames} (${Math.round(data.progress_percentage)}%)`;
            document.getElementById('stage5').textContent = progressText;
        }
    };
});