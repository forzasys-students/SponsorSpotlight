// Main JavaScript for SponsorSpotlight

document.addEventListener('DOMContentLoaded', function() {
    // File upload preview
    const fileInput = document.getElementById('file');
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
            
            // Check file size (max 500MB)
            const maxSize = 500 * 1024 * 1024; // 500MB in bytes
            if (file.size > maxSize) {
                alert('File is too large. Maximum size is 500MB.');
                this.value = '';
                return;
            }
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
});