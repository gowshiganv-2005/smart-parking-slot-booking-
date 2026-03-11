/**
 * User Feedback System - Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    const feedbackForm = document.getElementById('feedbackForm');
    const stars = document.querySelectorAll('.star');
    const ratingInput = document.getElementById('selectedRating');
    const submitBtn = document.getElementById('submitBtn');
    const btnText = document.getElementById('btnText');
    const loader = document.getElementById('loader');
    const successMsg = document.getElementById('successMessage');

    let currentRating = 0;

    // --- Star Rating Logic ---
    stars.forEach(star => {
        // Hover effect
        star.addEventListener('mouseover', () => {
            const rating = parseInt(star.getAttribute('data-rating'));
            highlightStars(rating);
        });

        // Mouse leave (reset to current selection)
        star.addEventListener('mouseleave', () => {
            highlightStars(currentRating);
        });

        // Click to select
        star.addEventListener('click', () => {
            currentRating = parseInt(star.getAttribute('data-rating'));
            ratingInput.value = currentRating;
            highlightStars(currentRating);
            
            // Remove error if rating was missing
            document.getElementById('ratingError').style.display = 'none';
        });
    });

    function highlightStars(rating) {
        stars.forEach(star => {
            const starValue = parseInt(star.getAttribute('data-rating'));
            if (starValue <= rating) {
                star.classList.add('active');
            } else {
                star.classList.remove('active');
            }
        });
    }

    // --- Form Submission ---
    feedbackForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Validate Form
        const name = document.getElementById('name').value.trim();
        const email = document.getElementById('email').value.trim();
        const comment = document.getElementById('comment').value.trim();
        const rating = parseInt(ratingInput.value);

        let isValid = true;

        if (!name) {
            document.getElementById('nameError').style.display = 'block';
            isValid = false;
        } else {
            document.getElementById('nameError').style.display = 'none';
        }

        if (!email || !validateEmail(email)) {
            document.getElementById('emailError').style.display = 'block';
            isValid = false;
        } else {
            document.getElementById('emailError').style.display = 'none';
        }

        if (!rating || rating === 0) {
            document.getElementById('ratingError').style.display = 'block';
            isValid = false;
        } else {
            document.getElementById('ratingError').style.display = 'none';
        }

        if (!comment) {
            document.getElementById('commentError').style.display = 'block';
            isValid = false;
        } else {
            document.getElementById('commentError').style.display = 'none';
        }

        if (!isValid) return;

        // Start Loading
        setLoading(true);

        try {
            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name,
                    email,
                    rating,
                    feedback: comment
                })
            });

            const data = await response.json();

            if (data.success) {
                // Success Handling
                feedbackForm.reset();
                currentRating = 0;
                highlightStars(0);
                successMsg.innerText = "Feedback submitted successfully!";
                successMsg.style.display = 'block';
                
                // Hide message after 5 seconds
                setTimeout(() => {
                    successMsg.style.display = 'none';
                }, 5000);
            } else {
                alert(data.message || "Failed to submit feedback. Please try again.");
            }
        } catch (error) {
            console.error('Error submitting feedback:', error);
            alert("An error occurred. Please check your connection.");
        } finally {
            setLoading(false);
        }
    });

    function setLoading(isLoading) {
        if (isLoading) {
            submitBtn.disabled = true;
            btnText.style.display = 'none';
            loader.style.display = 'block';
            successMsg.style.display = 'none';
        } else {
            submitBtn.disabled = false;
            btnText.style.display = 'block';
            loader.style.display = 'none';
        }
    }

    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
});
