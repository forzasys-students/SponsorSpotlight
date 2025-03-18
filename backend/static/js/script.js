document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("uploadForm");
    const errorMsg = document.getElementById("errorMsg");
    const fileInput = document.querySelector("input[name='file']");
    const urlInput = document.getElementById("videoUrl");
    const videoPlayer = document.getElementById("videoPlayer");
    const imageView = document.getElementById("imageView");
    const detectionCtx = document.getElementById("detectionChart").getContext("2d");
    const timeCtx = document.getElementById("timeChart").getContext("2d");
    const submitButton = document.getElementById("submitButton");
    const loadingCircle = document.getElementById("loadingCircle");

    let detectionChartInstance = null;
    let timeChartInstance = null;

    const loadingMsg = document.createElement("p");
    loadingMsg.textContent = "Loading... Please Wait";
    loadingMsg.style.color = "#007bff";
    loadingMsg.style.textAlign = "center";
    loadingMsg.style.display = "none"; 
    form.appendChild(loadingMsg);

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

            const data = await response.json();
            console.log("Response Data:", data);

            const mediaUrl = data.fileUrl;
            const stats = data.stats;

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

            // Convert JSON to statistics for charts
            const labels = Object.keys(stats);
            const detectionCounts = labels.map(logo => stats[logo].frames);
            const timeCounts = labels.map(logo => stats[logo].time);

            // Sort based on detections / time
            const sortedData = labels.map((label, i) => ({
                label,
                detection: detectionCounts[i],
                time: timeCounts[i]
            })).sort((a, b) => b.detection - a.detection);

            const sortedLabels = sortedData.map(item => item.label);
            const sortedDetections = sortedData.map(item => item.detection);
            const sortedTimes = sortedData.map(item => item.time);

            // Dynamically adjusting diagram size based on amounbt of labels
            const chartHeight = Math.max(300, sortedLabels.length * 50);
            document.getElementById("detectionChart").parentElement.style.height = `${chartHeight}px`;
            document.getElementById("timeChart").parentElement.style.height = `${chartHeight}px`;

            if (detectionChartInstance) detectionChartInstance.destroy();
            if (timeChartInstance) timeChartInstance.destroy();

            // Diagram creation (Detections)
            detectionChartInstance = new Chart(detectionCtx, {
                type: 'bar',
                data: {
                    labels: sortedLabels,
                    datasets: [{
                        label: 'Number of detections',
                        data: sortedDetections,
                        backgroundColor: 'rgba(75, 192, 192, 0.6)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: 2,
                    indexAxis: 'y',
                    scales: {
                        y: {
                            ticks: {
                                autoSkip: false,
                                font: { size: 14 },
                                padding: 10
                            }
                        },
                        x: {
                            ticks: { font: { size: 14 } }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    },
                    elements: {
                        bar: {
                            categoryPercentage: 0.1,
                            barPercentage: 0.2,
                            maxBarThickness: 10
                        }
                    }
                }
            });

            // Diagram creation (time)
            timeChartInstance = new Chart(timeCtx, {
                type: 'bar',
                data: {
                    labels: sortedLabels,
                    datasets: [{
                        label: 'Total exposure time (seconds)',
                        data: sortedTimes,
                        backgroundColor: 'rgba(255, 99, 132, 0.6)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: 2,
                    indexAxis: 'y',
                    scales: {
                        y: {
                            ticks: {
                                autoSkip: false,
                                font: { size: 14 },
                                padding: 10
                            }
                        },
                        x: {
                            ticks: { font: { size: 14 } }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    },
                    elements: {
                        bar: {
                            categoryPercentage: 0.1,
                            barPercentage: 0.2,
                            maxBarThickness: 10
                        }
                    }
                }
            });

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
});
