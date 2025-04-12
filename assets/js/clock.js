document.addEventListener('DOMContentLoaded', (event) => {
    // Get references to the time elements
    let hrs = document.getElementById("hour");
    let min = document.getElementById("min");
    let sec = document.getElementById("sec");
    // Get reference to the date element
    let dateEl = document.getElementById("date");

    // Check if ALL elements were found before setting up the interval
    if (hrs && min && sec && dateEl) {
        setInterval(() => {
            let currentTime = new Date();

            // Update the time elements
            hrs.textContent = String(currentTime.getHours()).padStart(2, '0');
            min.textContent = String(currentTime.getMinutes()).padStart(2, '0');
            sec.textContent = String(currentTime.getSeconds()).padStart(2, '0');

            // --- Add date update logic ---
            let year = currentTime.getFullYear();
            // getMonth() is 0-indexed, so add 1
            let month = String(currentTime.getMonth() + 1).padStart(2, '0');
            let day = String(currentTime.getDate()).padStart(2, '0');

            // Update the date element
            dateEl.textContent = `${year}-${month}-${day}`;
            // --- End of date update logic ---

        }, 1000); // Specify the interval (1000ms = 1 second)
    } else {
        // Log an error if any element is missing
        console.error("Clock elements (#hour, #min, #sec, #date) not found!"); // <-- Update error message
    }
});