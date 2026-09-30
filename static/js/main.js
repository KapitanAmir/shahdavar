document.addEventListener("DOMContentLoaded", function () {

    /* ========================================================
       MOBILE MENU
    ======================================================== */

    const menuButton =
        document.getElementById("menuButton");

    const mobileMenu =
        document.getElementById("mobileMenu");


    if (menuButton && mobileMenu) {

        menuButton.addEventListener("click", function () {

            mobileMenu.classList.toggle("open");

        });

    }


    /* ========================================================
       HERO SLIDER
    ======================================================== */

    const slides =
        document.querySelectorAll(".hero-slide");

    const dots =
        document.querySelectorAll(".slider-dot");

    const prevButton =
        document.getElementById("prevButton");

    const nextButton =
        document.getElementById("nextButton");


    if (slides.length <= 1) {
        return;
    }


    let currentIndex = 0;

    let sliderTimer = null;


    /* ========================================================
       SHOW SLIDE
    ======================================================== */

    function showSlide(index) {

        if (index < 0) {
            index = slides.length - 1;
        }

        if (index >= slides.length) {
            index = 0;
        }


        slides.forEach(function (slide, i) {

            slide.classList.toggle(
                "active",
                i === index
            );

        });


        dots.forEach(function (dot, i) {

            dot.classList.toggle(
                "active",
                i === index
            );

        });


        currentIndex = index;

        startAutoSlide();

    }


    /* ========================================================
       NEXT
    ======================================================== */

    function nextSlide() {

        showSlide(
            currentIndex + 1
        );

    }


    /* ========================================================
       PREVIOUS
    ======================================================== */

    function previousSlide() {

        showSlide(
            currentIndex - 1
        );

    }


    /* ========================================================
       AUTO SLIDE
    ======================================================== */

    function startAutoSlide() {

        if (sliderTimer) {
            clearTimeout(sliderTimer);
        }


        const currentSlide =
            slides[currentIndex];


        let duration =
            parseInt(
                currentSlide.dataset.duration,
                10
            );


        if (
            Number.isNaN(duration) ||
            duration <= 0
        ) {

            duration = 5;

        }


        sliderTimer = setTimeout(
            nextSlide,
            duration * 1000
        );

    }


    /* ========================================================
       NEXT BUTTON
    ======================================================== */

    if (nextButton) {

        nextButton.addEventListener(
            "click",
            function () {

                nextSlide();

            }
        );

    }


    /* ========================================================
       PREVIOUS BUTTON
    ======================================================== */

    if (prevButton) {

        prevButton.addEventListener(
            "click",
            function () {

                previousSlide();

            }
        );

    }


    /* ========================================================
       DOTS
    ======================================================== */

    dots.forEach(function (dot, index) {

        dot.addEventListener(
            "click",
            function () {

                showSlide(index);

            }
        );

    });


    /* ========================================================
       START
    ======================================================== */

    showSlide(0);

});