// Main JavaScript for SponsorSpotlight

document.addEventListener('DOMContentLoaded', function() {
    // File upload preview
    const fileInput = document.getElementById('file');
    const uploadBtn = document.getElementById('uploadBtn');
    const fileSection = document.getElementById('fileSection');
    const urlSection = document.getElementById('urlSection');

    const setUrlMode = (enabled) => {
        if (processUrlBtn) processUrlBtn.disabled = !enabled;
        if (urlInput) urlInput.disabled = !enabled;
        if (urlSection) {
            urlSection.classList.toggle('disabled', !enabled);
        }
    };

    const setFileMode = (enabled) => {
        if (fileInput) fileInput.disabled = !enabled;
        if (uploadBtn) uploadBtn.disabled = !enabled;
        if (fileSection) {
            fileSection.classList.toggle('disabled', !enabled);
        }
    };

    const resetModesIfEmpty = () => {
        const urlEmpty = !urlInput || !urlInput.value || urlInput.value.trim() === '';
        const fileEmpty = !fileInput || !fileInput.files || fileInput.files.length === 0;
        if (urlEmpty && fileEmpty) {
            setUrlMode(true);
            setFileMode(true);
        }
    };

    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            if (!file) return;
            
            // Check if file type is supported
            const fileType = file.type.split('/')[0];
            if (fileType !== 'image' && fileType !== 'video') {
                alert('Unsupported file type. Please upload an image or video.');
                this.value = '';
                return;
            }
            
            // Check file size (max 6GB)
            const maxSize = 6 * 1024 * 1024 * 1024; // 6GB in bytes
            if (file.size > maxSize) {
                alert('File is too large. Maximum size is 6GB.');
                this.value = '';
                return;
            }

            // Disable URL mode when file selected
            setUrlMode(false);
        });
    }
    
    // Add pulse animation to processing elements
    const processingElements = document.querySelectorAll('#processing-status');
    processingElements.forEach(element => {
        element.classList.add('pulse');
    });
    
    // Enable tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    // URL preview and processing
    const urlInput = document.getElementById('urlInput');
    const previewContainer = document.getElementById('previewContainer');
    const previewImg = document.getElementById('urlPreview');
    const processUrlBtn = document.getElementById('processUrlBtn');

    const genRawUrl = document.getElementById('genRawUrl');
    const genAnnotUrl = document.getElementById('genAnnotUrl');

    const debounce = (fn, delay = 600) => {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), delay);
        };
    };

    const fetchPreview = debounce(() => {
        if (!urlInput || !urlInput.value) return;
        fetch(`/api/preview_frame?url=${encodeURIComponent(urlInput.value)}`)
            .then(r => r.json())
            .then(data => {
                if (data.image_data) {
                    previewImg.src = data.image_data;
                    previewContainer.classList.remove('d-none');
                }
            })
            .catch(() => {});
    }, 700);

    if (urlInput) {
        urlInput.addEventListener('input', () => {
            if (urlInput.value && urlInput.value.startsWith('http')) {
                fetchPreview();
                // Disable file mode when URL typed
                setFileMode(false);
            } else {
                previewContainer.classList.add('d-none');
                previewImg.src = '';
                // Re-enable both if empty
                resetModesIfEmpty();
            }
        });
    }

    if (processUrlBtn) {
        processUrlBtn.addEventListener('click', () => {
            const url = urlInput?.value?.trim();
            if (!url) {
                alert('Please paste a URL.');
                return;
            }
            const body = {
                url,
                generate_raw_video: !!genRawUrl?.checked,
                generate_annotated_video: !!genAnnotUrl?.checked
            };
            fetch('/upload_url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
            .then(r => r.json())
            .then(data => {
                if (data.redirect) {
                    window.location.href = data.redirect;
                } else if (data.error) {
                    alert(data.error);
                }
            })
            .catch(err => alert(`Failed to submit URL: ${err}`));
        });
    }

    // If the page loads with both empty, ensure both modes enabled
    resetModesIfEmpty();
});