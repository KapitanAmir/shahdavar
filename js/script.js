document.addEventListener(
    "DOMContentLoaded",
    function () {

        // ====================================================
        // MOBILE MENU
        // ====================================================

        const menuButton =
            document.getElementById(
                "menuButton"
            );

        const mobileMenu =
            document.getElementById(
                "mobileMenu"
            );


        if (
            menuButton &&
            mobileMenu
        ) {

            menuButton.addEventListener(
                "click",
                function () {

                    mobileMenu.classList.toggle(
                        "open"
                    );

                }
            );

        }



        // ====================================================
        // HERO SLIDER
        // ====================================================

        const slider =
            document.getElementById(
                "heroSlider"
            );


        if (!slider) {
            return;
        }


        const slides =
            Array.from(
                slider.querySelectorAll(
                    ".hero-slide"
                )
            );


        const dots =
            Array.from(
                slider.querySelectorAll(
                    ".slider-dot"
                )
            );


        const prevButton =
            document.getElementById(
                "prevButton"
            );


        const nextButton =
            document.getElementById(
                "nextButton"
            );


        if (
            slides.length <= 1
        ) {
            return;
        }


        let currentIndex = 0;

        let sliderTimer = null;



        // ====================================================
        // SHOW SLIDE
        // ====================================================

        function showSlide(index) {

            if (
                index < 0
            ) {
                index =
                    slides.length - 1;
            }


            if (
                index >= slides.length
            ) {
                index = 0;
            }


            currentIndex = index;


            slides.forEach(
                function (slide, i) {

                    slide.classList.toggle(
                        "active",
                        i === currentIndex
                    );

                }
            );


            dots.forEach(
                function (dot, i) {

                    dot.classList.toggle(
                        "active",
                        i === currentIndex
                    );

                }
            );


            restartSlider();

        }



        // ====================================================
        // NEXT
        // ====================================================

        function nextSlide() {

            showSlide(
                currentIndex + 1
            );

        }



        // ====================================================
        // PREVIOUS
        // ====================================================

        function previousSlide() {

            showSlide(
                currentIndex - 1
            );

        }



        // ====================================================
        // GET CURRENT DURATION
        // ====================================================

        function getCurrentDuration() {

            const duration =
                parseFloat(
                    slides[currentIndex]
                        .dataset
                        .duration
                );


            if (
                Number.isFinite(duration) &&
                duration > 0
            ) {

                return duration * 1000;

            }


            return 5000;

        }



        // ====================================================
        // AUTO SLIDER
        // ====================================================

        function startSlider() {

            clearTimeout(
                sliderTimer
            );


            sliderTimer =
                setTimeout(
                    function () {

                        nextSlide();

                    },
                    getCurrentDuration()
                );

        }


        function restartSlider() {

            startSlider();

        }



        // ====================================================
        // ARROWS
        // ====================================================

        if (nextButton) {

            nextButton.addEventListener(
                "click",
                function () {

                    nextSlide();

                }
            );

        }


        if (prevButton) {

            prevButton.addEventListener(
                "click",
                function () {

                    previousSlide();

                }
            );

        }



        // ====================================================
        // DOTS
        // ====================================================

        dots.forEach(
            function (dot, index) {

                dot.addEventListener(
                    "click",
                    function () {

                        showSlide(
                            index
                        );

                    }
                );

            }
        );



        // ====================================================
        // INITIALIZE
        // ====================================================

        showSlide(
            currentIndex
        );

    }
);