document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("uploadForm");
    const errorMsg = document.getElementById("errorMsg");
    const fileInput = document.querySelector("input[name='file']");
    const urlInput = document.getElementById("videoUrl");
    const videoPlayer = document.getElementById("videoPlayer");
    const imageView = document.getElementById("imageView");
    const exportExcel = document.getElementById("exportExcel");
    const submitButton = document.getElementById("submitButton");
    const loadingCircle = document.getElementById("loadingCircle");
    const dropdown = document.getElementById("categoryDropdown");
    const timeChart = document.getElementById("timeChart"); 
    const timeChartHeader = document.getElementById("timeChartHeader");
       
    const loadingMsg = document.createElement("p");
    loadingMsg.textContent = "Loading... Please Wait";
    loadingMsg.style.color = "#007bff";
    loadingMsg.style.textAlign = "center";
    loadingMsg.style.display = "none";
    form.appendChild(loadingMsg);

    let responseData;

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        errorMsg.textContent = "";

        submitButton.disabled = true;
        submitButton.style.backgroundColor = "#ccc";
        submitButton.style.cursor = "not-allowed";
        loadingMsg.style.display = "block";
        loadingCircle.style.display = "block";

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

            if (!response.ok) throw new Error("Error handling request");

            responseData = await response.json();
            console.log("Response Data:", responseData);

            const mediaUrl = responseData.fileUrl;
            const stats = responseData.stats;

            // Updating media section
            if (mediaUrl.endsWith(".jpg") || mediaUrl.endsWith(".jpeg") || mediaUrl.endsWith(".png")) {
                imageView.src = mediaUrl;
                imageView.style.display = "block";
                videoPlayer.style.display = "none";
            } else if (mediaUrl.endsWith(".mp4")) {
                videoPlayer.src = mediaUrl;
                videoPlayer.style.display = "block";
                imageView.style.display = "none";
                videoPlayer.play();
            } else {
                throw new Error("Unknown media type.");
            }

            updateUIWithData(stats);
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

    function updateUIWithData(data) {
        const stats = data;

        // Prepare data for Plotly
        const labels = Object.keys(stats);
        const detectionCounts = labels.map(logo => stats[logo].frames);
        const timeCounts = labels.map(logo => stats[logo].time);

        // Sort data for the detection chart by detections in ascending order (Plotly will showcase largest value at the top)
        const sortedDetectionData = labels.map((label, i) => ({
            label,
            detection: detectionCounts[i],
            time: timeCounts[i]
        })).sort((a, b) => a.detection - b.detection);

        const sortedDetectionLabels = sortedDetectionData.map(item => item.label);
        const sortedDetections = sortedDetectionData.map(item => item.detection);

        //CHecking if data is image, as it is then no need to show time charts
        const isImage = responseData.fileUrl.endsWith(".jpg");
        
        if (isImage) {
                timeChart.style.display = "none";
                timeChartHeader.style.display = "none";
        } else {
                timeChart.style.display = "block";
                timeChartHeader.style.display = "block";
        }

        // Sort data for the time chart by time in ascending order (Plotly will showcase largest value at the top)
        const sortedTimeData = labels.map((label, i) => ({
            label,
            detection: detectionCounts[i],
            time: timeCounts[i]
        })).sort((a, b) => a.time - b.time);

        const sortedTimeLabels = sortedTimeData.map(item => item.label);
        const sortedTimes = sortedTimeData.map(item => item.time);

        // Update charts
        updateDetectionChart(sortedDetectionLabels, sortedDetections);
        updateTimeChart(sortedTimeLabels, sortedTimes);

        
        document.getElementById("categoryDropdown").style.display = "block";
        document.getElementById("infoTextDropdown").style.display = "block";
        document.getElementById("filterButton").style.display = "block";
        document.getElementById("resetButton").style.display = "block";
        
        //Update dropdown menu
        updateDropdown(labels);
    }

    function updateDetectionChart(labels, detections) {
        const wrappedLabels = wrapLabels(labels);

        const detectionTrace = {
            x: detections,
            y: wrappedLabels, // Use wrapped labels
            type: 'bar',
            orientation: 'h',
            name: 'Number of Detections',
            marker: { color: 'rgba(75, 192, 192, 0.6)' }
        };

        const layout = {
            title: 'Number of Detections',
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
                ...detections.map((value, index) => ({
                    x: value,
                    y: index,
                    text: value.toString(),
                    showarrow: false,
                    font: { size: 12, color: '#000', family: 'Arial' },
                    xanchor: 'left',
                    yanchor: 'middle'
                }))
            ]
        };

        Plotly.newPlot('detectionChart', [detectionTrace], layout);
    }

    function updateTimeChart(labels, times) {
        const wrappedLabels = wrapLabels(labels);

        const timeTrace = {
            x: times,
            y: labels, // Use wrapped labels
            type: 'bar',
            orientation: 'h',
            name: 'Total Exposure Time (seconds)',
            marker: { color: 'rgba(255, 99, 132, 0.6)' }
        };

        const layout = {
            title: 'Total Exposure Time (seconds)',
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
                ...times.map((value, index) => ({
                    x: value,
                    y: index,
                    text: value.toString(),
                    showarrow: false,
                    font: { size: 12, color: '#000', family: 'Arial' },
                    xanchor: 'left',
                    yanchor: 'middle'
                }))
            ]
        };

        Plotly.newPlot('timeChart', [timeTrace], layout);
    }

    // Option to export data to Excel file
    exportExcel.addEventListener("click", async() => {
        if (!responseData || !responseData.stats) {
            throw new Error("No data to export.");
        }

        const excelHeader = ["Logo", "Number of Detections", "Total Exposure Time (seconds)"];
        const dataForExcel = Object.keys(responseData.stats).map(logo => ({
            Logo: logo,
            "Number of Detections": responseData.stats[logo].frames,
            "Total Exposure Time (seconds)": responseData.stats[logo].time
        }));

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

    //Function for filtering logos in charts.
    document.getElementById("filterButton").addEventListener("click", function () {
        const selectedCategories = Array.from(dropdown.selectedOptions).map(option => option.value);

        const filteredData = Object.keys(responseData.stats)
            .filter(logo => selectedCategories.includes(logo))
            .reduce((acc, logo) => {
                acc[logo] = responseData.stats[logo];
                return acc;
            }, {});
    
        updateUIWithData(filteredData); 
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
});