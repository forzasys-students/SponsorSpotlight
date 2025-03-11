function loadVideo() {
    const video = document.getElementById('videoPlayer');
    const url = document.getElementById('videoUrl').value;

    if (Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(url);
        hls.attachMedia(video);
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = url;
    } else {
        alert("HLS ikke støttet i denne nettleseren.");
    }
}
