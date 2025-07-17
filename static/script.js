document.addEventListener('DOMContentLoaded', (event) => {
    const form = document.getElementById('analysis-form');
    const button = document.getElementById('analyze-button');
    const loader = document.getElementById('loader');

    if (form) {
        form.addEventListener('submit', () => {
            // Show loader and disable button on form submission
            if (loader) {
                loader.style.display = 'block';
            }
            if (button) {
                button.disabled = true;
                button.textContent = 'جاري التحليل...';
            }
        });
    }
});
