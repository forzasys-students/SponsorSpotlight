document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("fetchButton").addEventListener("click", loadVideo);
});

function isValidM3U8Url(url) {
    const pattern = /^https?:\/\/.+\.m3u8$/i; // Sjekker at URL starter med http/https og slutter på .m3u8
    return pattern.test(url);
}

function loadVideo() {
    const video = document.getElementById('videoPlayer');
    const url = document.getElementById('videoUrl').value.trim(); 

    if (!isValidM3U8Url(url)) {
        alert("Vennligst skriv inn en gyldig M3U8-lenke!");
        return;
    }

    console.log("Laster video fra URL:", url);

    if (Hls.isSupported()) {
        console.log("HLS er støttet, bruker Hls.js...");
        const hls = new Hls();
        hls.loadSource(url);
        hls.attachMedia(video);
        hls.on(Hls.Events.ERROR, function(event, data) {
            console.error("HLS-feil:", data);
        });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        console.log("HLS støttes av denne nettleseren, bruker native player...");
        video.src = url;
    } else {
        alert("HLS er ikke støttet i denne nettleseren.");
    }
}
