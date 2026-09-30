"use strict";


/* ============================================================
   ACCOUNT SYSTEM
============================================================ */

document.addEventListener("DOMContentLoaded", function () {


    /* ========================================================
       ELEMENTS
    ======================================================== */

    const tabs = document.querySelectorAll(".auth-tab");

    const panels = document.querySelectorAll(".auth-panel");

    const switchButtons =
        document.querySelectorAll(".switch-auth");


    /* ========================================================
       AUTH PANEL SWITCH
    ======================================================== */

    function switchPanel(targetId) {

        tabs.forEach(function (tab) {

            tab.classList.toggle(
                "active",
                tab.dataset.target === targetId
            );

        });


        panels.forEach(function (panel) {

            panel.classList.toggle(
                "active",
                panel.id === targetId
            );

        });


        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });

    }


    tabs.forEach(function (tab) {

        tab.addEventListener("click", function () {

            switchPanel(
                tab.dataset.target
            );

        });

    });


    switchButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            switchPanel(
                button.dataset.target
            );

        });

    });


    /* ========================================================
       PASSWORD VISIBILITY
    ======================================================== */

    const passwordButtons =
        document.querySelectorAll(".password-toggle");


    passwordButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const targetId =
                button.dataset.target;

            const input =
                document.getElementById(targetId);

            if (!input) {
                return;
            }


            if (input.type === "password") {

                input.type = "text";

                button.textContent = "🙈";

            } else {

                input.type = "password";

                button.textContent = "👁";

            }

        });

    });


    /* ========================================================
       PERSIAN / ENGLISH DIGITS
    ======================================================== */

    function normalizeDigits(value) {

        if (!value) {
            return "";
        }

        return String(value)
            .replace(/[۰-۹]/g, function (digit) {
                return String(
                    "۰۱۲۳۴۵۶۷۸۹".indexOf(digit)
                );
            })
            .replace(/[٠-٩]/g, function (digit) {
                return String(
                    "٠١٢٣٤٥٦٧٨٩".indexOf(digit)
                );
            });

    }


    /* ========================================================
       PHONE FORMAT
    ======================================================== */

    const phoneInputs =
        document.querySelectorAll(
            'input[name="phone"]'
        );


    phoneInputs.forEach(function (input) {

        input.addEventListener("input", function () {

            input.value =
                normalizeDigits(input.value)
                    .replace(/\D/g, "")
                    .slice(0, 11);

        });

    });


    /* ========================================================
       VALIDATION HELPERS
    ======================================================== */

    function setFieldError(
        input,
        message
    ) {

        if (!input) {
            return false;
        }


        const group =
            input.closest(".form-group");


        if (!group) {
            return false;
        }


        const error =
            group.querySelector(".field-error");


        group.classList.add("invalid");

        group.classList.remove("valid");


        if (error) {
            error.textContent = message;
        }


        return false;

    }


    function setFieldValid(input) {

        if (!input) {
            return true;
        }


        const group =
            input.closest(".form-group");


        if (!group) {
            return true;
        }


        const error =
            group.querySelector(".field-error");


        group.classList.remove("invalid");

        group.classList.add("valid");


        if (error) {
            error.textContent = "";
        }


        return true;

    }


    function clearFieldState(input) {

        if (!input) {
            return;
        }


        const group =
            input.closest(".form-group");


        if (!group) {
            return;
        }


        group.classList.remove(
            "invalid",
            "valid"
        );


        const error =
            group.querySelector(".field-error");


        if (error) {
            error.textContent = "";
        }

    }


    function showMessage(
        element,
        message,
        type
    ) {

        if (!element) {
            return;
        }


        element.textContent = message;

        element.className =
            "form-message show " + type;

    }


    function clearMessage(element) {

        if (!element) {
            return;
        }


        element.textContent = "";

        element.className =
            "form-message";

    }


    /* ========================================================
       NAME VALIDATION
    ======================================================== */

    function validateName(input, label) {

        const value =
            input.value.trim();


        if (!value) {

            return setFieldError(
                input,
                `لطفاً ${label} را وارد کنید.`
            );

        }


        if (value.length < 2) {

            return setFieldError(
                input,
                `${label} باید حداقل ۲ کاراکتر باشد.`
            );

        }


        if (value.length > 50) {

            return setFieldError(
                input,
                `${label} بیش از حد طولانی است.`
            );

        }


        setFieldValid(input);

        return true;

    }


    /* ========================================================
       PHONE VALIDATION
    ======================================================== */

    function validatePhone(input) {

        const value =
            normalizeDigits(input.value)
                .replace(/\D/g, "");


        input.value = value;


        if (!value) {

            return setFieldError(
                input,
                "شماره موبایل را وارد کنید."
            );

        }


        if (!/^09\d{9}$/.test(value)) {

            return setFieldError(
                input,
                "شماره موبایل معتبر نیست."
            );

        }


        setFieldValid(input);

        return true;

    }


    /* ========================================================
       EMAIL VALIDATION
    ======================================================== */

    function validateEmail(input) {

        const value =
            input.value.trim();


        if (!value) {

            clearFieldState(input);

            return true;

        }


        const pattern =
            /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


        if (!pattern.test(value)) {

            return setFieldError(
                input,
                "فرمت ایمیل صحیح نیست."
            );

        }


        setFieldValid(input);

        return true;

    }


    /* ========================================================
       PASSWORD VALIDATION
    ======================================================== */

    function validatePassword(input) {

        const value =
            input.value;


        if (!value) {

            return setFieldError(
                input,
                "رمز عبور را وارد کنید."
            );

        }


        if (value.length < 8) {

            return setFieldError(
                input,
                "رمز عبور باید حداقل ۸ کاراکتر باشد."
            );

        }


        setFieldValid(input);

        return true;

    }


    /* ========================================================
       PASSWORD STRENGTH
    ======================================================== */

    const passwordInput =
        document.getElementById("password");


    if (passwordInput) {

        passwordInput.addEventListener(
            "input",
            function () {

                const value =
                    passwordInput.value;

                const bar =
                    document.querySelector(
                        ".strength-bar span"
                    );

                if (!bar) {
                    return;
                }


                let score = 0;


                if (value.length >= 8) {
                    score++;
                }

                if (/[A-Z]/.test(value)) {
                    score++;
                }

                if (/[a-z]/.test(value)) {
                    score++;
                }

                if (/[0-9]/.test(value)) {
                    score++;
                }

                if (/[^A-Za-z0-9]/.test(value)) {
                    score++;
                }


                const width =
                    Math.min(score * 20, 100);


                bar.style.width =
                    width + "%";

            }
        );

    }


    /* ========================================================
       REGISTER FORM
    ======================================================== */

    const registerForm =
        document.getElementById(
            "register-form"
        );


    if (registerForm) {

        registerForm.addEventListener(
            "submit",
            async function (event) {

                event.preventDefault();


                const message =
                    document.getElementById(
                        "register-message"
                    );


                clearMessage(message);


                const firstName =
                    document.getElementById(
                        "first-name"
                    );

                const lastName =
                    document.getElementById(
                        "last-name"
                    );

                const phone =
                    document.getElementById(
                        "phone"
                    );

                const email =
                    document.getElementById(
                        "email"
                    );

                const province =
                    document.getElementById(
                        "province"
                    );

                const city =
                    document.getElementById(
                        "city"
                    );

                const password =
                    document.getElementById(
                        "password"
                    );

                const passwordConfirm =
                    document.getElementById(
                        "password-confirm"
                    );

                const terms =
                    document.getElementById(
                        "terms"
                    );


                let valid = true;


                if (
                    !validateName(
                        firstName,
                        "نام"
                    )
                ) {
                    valid = false;
                }


                if (
                    !validateName(
                        lastName,
                        "نام خانوادگی"
                    )
                ) {
                    valid = false;
                }


                if (
                    !validatePhone(phone)
                ) {
                    valid = false;
                }


                if (
                    !validateEmail(email)
                ) {
                    valid = false;
                }


                if (!province.value) {

                    setFieldError(
                        province,
                        "استان را انتخاب کنید."
                    );

                    valid = false;

                } else {

                    setFieldValid(province);

                }


                if (!city.value.trim()) {

                    setFieldError(
                        city,
                        "شهر را وارد کنید."
                    );

                    valid = false;

                } else {

                    setFieldValid(city);

                }


                const gender =
                    registerForm.querySelector(
                        'input[name="gender"]:checked'
                    );


                const genderGroup =
                    registerForm.querySelector(
                        ".gender-options"
                    );


                if (!gender) {

                    const group =
                        genderGroup.closest(
                            ".form-group"
                        );

                    const error =
                        group.querySelector(
                            ".field-error"
                        );

                    group.classList.add(
                        "invalid"
                    );

                    if (error) {
                        error.textContent =
                            "جنسیت را انتخاب کنید.";
                    }

                    valid = false;

                } else {

                    const group =
                        genderGroup.closest(
                            ".form-group"
                        );

                    group.classList.remove(
                        "invalid"
                    );

                    group.classList.add(
                        "valid"
                    );

                }


                if (
                    !validatePassword(
                        password
                    )
                ) {
                    valid = false;
                }


                if (
                    passwordConfirm.value !==
                    password.value
                ) {

                    setFieldError(
                        passwordConfirm,
                        "تکرار رمز عبور صحیح نیست."
                    );

                    valid = false;

                } else if (
                    passwordConfirm.value
                ) {

                    setFieldValid(
                        passwordConfirm
                    );

                }


                if (!terms.checked) {

                    const termsGroup =
                        terms.closest(
                            ".terms-group"
                        );

                    const error =
                        termsGroup.querySelector(
                            ".field-error"
                        );

                    if (error) {
                        error.textContent =
                            "برای ساخت حساب باید با قوانین سایت موافق باشید.";
                    }

                    valid = false;

                } else {

                    const termsGroup =
                        terms.closest(
                            ".terms-group"
                        );

                    const error =
                        termsGroup.querySelector(
                            ".field-error"
                        );

                    if (error) {
                        error.textContent = "";
                    }

                }


                if (!valid) {

                    showMessage(
                        message,
                        "لطفاً اطلاعات مشخص‌شده را بررسی کنید.",
                        "error"
                    );

                    return;

                }


                const submitButton =
                    registerForm.querySelector(
                        ".submit-button"
                    );


                submitButton.disabled = true;

                submitButton.classList.add(
                    "loading"
                );


                const formData =
                    new FormData(
                        registerForm
                    );


                const data =
                    Object.fromEntries(
                        formData.entries()
                    );


                data.phone =
                    normalizeDigits(
                        data.phone
                    );


                data.terms =
                    terms.checked;


                try {

                    const response =
                        await fetch(
                            "/api/account/register",
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                credentials: "same-origin",

                                body:
                                    JSON.stringify(data)
                            }
                        );


                    const result =
                        await response.json();


                    if (!response.ok) {

                        throw new Error(
                            result.message ||
                            "ثبت نام انجام نشد."
                        );

                    }


                    showMessage(
                        message,
                        result.message ||
                        "حساب شما با موفقیت ساخته شد.",
                        "success"
                    );


                    registerForm.reset();


                    if (passwordInput) {

                        const bar =
                            document.querySelector(
                                ".strength-bar span"
                            );

                        if (bar) {
                            bar.style.width =
                                "0%";
                        }

                    }


                    setTimeout(
                        function () {

                            window.location.href =
                                result.redirect ||
                                "/account";

                        },
                        900
                    );


                } catch (error) {

                    showMessage(
                        message,
                        error.message ||
                        "خطایی در ارتباط با سرور رخ داد.",
                        "error"
                    );


                } finally {

                    submitButton.disabled =
                        false;

                    submitButton.classList.remove(
                        "loading"
                    );

                }

            }
        );

    }


    /* ========================================================
       LOGIN FORM
    ======================================================== */

    const loginForm =
        document.getElementById(
            "login-form"
        );


    if (loginForm) {

        loginForm.addEventListener(
            "submit",
            async function (event) {

                event.preventDefault();


                const message =
                    document.getElementById(
                        "login-message"
                    );


                clearMessage(message);


                const phone =
                    document.getElementById(
                        "login-phone"
                    );

                const password =
                    document.getElementById(
                        "login-password"
                    );


                let valid = true;


                if (
                    !validatePhone(phone)
                ) {
                    valid = false;
                }


                if (
                    !password.value
                ) {

                    setFieldError(
                        password,
                        "رمز عبور را وارد کنید."
                    );

                    valid = false;

                } else {

                    setFieldValid(password);

                }


                if (!valid) {

                    showMessage(
                        message,
                        "لطفاً اطلاعات ورود را بررسی کنید.",
                        "error"
                    );

                    return;

                }


                const submitButton =
                    loginForm.querySelector(
                        ".submit-button"
                    );


                submitButton.disabled = true;

                submitButton.classList.add(
                    "loading"
                );


                try {

                    const response =
                        await fetch(
                            "/api/account/login",
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json"
                                },

                                credentials: "same-origin",

                                body:
                                    JSON.stringify({
                                        phone:
                                            normalizeDigits(
                                                phone.value
                                            ),
                                        password:
                                            password.value
                                    })
                            }
                        );


                    const result =
                        await response.json();


                    if (!response.ok) {

                        throw new Error(
                            result.message ||
                            "ورود انجام نشد."
                        );

                    }


                    showMessage(
                        message,
                        result.message ||
                        "ورود با موفقیت انجام شد.",
                        "success"
                    );


                    setTimeout(
                        function () {

                            window.location.href =
                                result.redirect ||
                                "/account";

                        },
                        700
                    );


                } catch (error) {

                    showMessage(
                        message,
                        error.message ||
                        "خطایی در ارتباط با سرور رخ داد.",
                        "error"
                    );


                } finally {

                    submitButton.disabled =
                        false;

                    submitButton.classList.remove(
                        "loading"
                    );

                }

            }
        );

    }


});