// Add any future JavaScript interactions here.
console.log("Parking App script loaded.");

// Example: Add confirmation dialog for delete buttons
document.addEventListener('DOMContentLoaded', function() {
    const deleteForms = document.querySelectorAll('form[action*="/delete/"]');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            const confirmed = confirm('Are you sure you want to delete this item? This action cannot be undone.');
            if (!confirmed) {
                event.preventDefault(); // Stop the form submission
            }
        });
    });
});