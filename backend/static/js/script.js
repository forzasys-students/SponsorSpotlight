document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("uploadForm");
    const errorMsg = document.getElementById("errorMsg");
    const fileInput = document.querySelector("input[name='mediaFile']");
    const urlInput = document.getElementById("videoUrl");
    const videoPlayer = document.getElementById("videoPlayer");
    const imageView = document.getElementById("imageView");

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        errorMsg.textContent = ""; 

        let response;

        try {
            if (urlInput.value.trim()) {
                const videoUrl = urlInput.value.trim();

                response = await fetch("/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ videoUrl })
                });

            } 
            else if (fileInput.files.length > 0) {
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

            if (!response.ok) throw new Error("Error handlig request");

           
            const blob = await response.blob();
            console.log("Blob size: ", blob.size);
            const contentType = response.headers.get("Content-Type");
            const mediaUrl = URL.createObjectURL(blob);

            if (contentType.startsWith("image")) {
                imageView.src = mediaUrl;
                imageView.style.display = "block";
                videoPlayer.style.display = "none";
            } else if (contentType.startsWith("video")) {
                videoPlayer.src = mediaUrl;
                videoPlayer.style.display = "block";
                imageView.style.display = "none";
                videoPlayer.play();
            } else {
                throw new Error("Uknown media type.");
            }

        } catch (error) {
            errorMsg.textContent = error.message;
            console.error(error);
        }
    });
});
