// assets/js/analog-clock.js
document.addEventListener('DOMContentLoaded', () => {
    const hourHand = document.getElementById('analog-hour');
    const minuteHand = document.getElementById('analog-min');
    const secondHand = document.getElementById('analog-sec');

    function setClock() {
        const now = new Date();

        const seconds = now.getSeconds();
        const minutes = now.getMinutes();
        const hours = now.getHours();

        const secondsDegrees = ((seconds / 60) * 360) + 90;
        const minutesDegrees = ((minutes / 60) * 360) + ((seconds / 60) * 6) + 90;
        const hoursDegrees = ((hours / 12) * 360) + ((minutes / 60) * 30) + 90;

        // Apply rotation only if the element exists
        if (secondHand) {
          secondHand.style.transform = `translateY(-50%) rotate(${secondsDegrees}deg)`;
        }
        if (minuteHand) {
          minuteHand.style.transform = `translateY(-50%) rotate(${minutesDegrees}deg)`;
        }
        if (hourHand) {
          hourHand.style.transform = `translateY(-50%) rotate(${hoursDegrees}deg)`;
        }

        // Handle the edge case where secondsDegrees resets (avoids jump back)
        if (secondsDegrees === 90) { // 0 seconds
                     if (secondHand) {
                       secondHand.style.transition = 'none';
                     } // Temporarily disable transition
                }
        else if (secondHand) {
               secondHand.style.transition = 'transform 0.1s cubic-bezier(0.4, 2.3, 0.6, 1)';
             }
    }

    // Check if hands exist before starting interval
    if (hourHand && minuteHand && secondHand) {
        setInterval(setClock, 1000); // Update every second
        setClock(); // Initial call to set clock immediately
    } else {
        console.error("Analog clock hands not found!");
    }
});