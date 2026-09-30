document.addEventListener(
    "DOMContentLoaded",
    function () {

        // ====================================================
        // DISCOUNT TOGGLE
        // ====================================================

        const discountCheckbox =
            document.getElementById(
                "is_discount"
            );

        const discountFields =
            document.getElementById(
                "discountFields"
            );


        function updateDiscountFields() {

            if (
                !discountCheckbox ||
                !discountFields
            ) {
                return;
            }


            if (
                discountCheckbox.checked
            ) {

                discountFields.classList.remove(
                    "hidden"
                );

            } else {

                discountFields.classList.add(
                    "hidden"
                );

            }

        }


        if (discountCheckbox) {

            discountCheckbox.addEventListener(
                "change",
                updateDiscountFields
            );

            updateDiscountFields();

        }



        // ====================================================
        // PRICE INPUT
        // ====================================================

        const priceInput =
            document.getElementById(
                "price"
            );


        const finalPriceInput =
            document.getElementById(
                "final_price"
            );


        const discountPercentInput =
            document.getElementById(
                "discount_percent"
            );



        function normalizeNumberInput(input) {

            if (!input) {
                return;
            }


            input.addEventListener(
                "input",
                function () {

                    let value =
                        this.value.replace(
                            /[^\d]/g,
                            ""
                        );

                    this.value = value;

                }
            );

        }


        normalizeNumberInput(
            priceInput
        );


        normalizeNumberInput(
            finalPriceInput
        );



        // ====================================================
        // DISCOUNT CALCULATION
        // ====================================================

        function calculateFinalPrice() {

            if (
                !priceInput ||
                !finalPriceInput ||
                !discountPercentInput
            ) {
                return;
            }


            if (
                !discountCheckbox ||
                !discountCheckbox.checked
            ) {
                return;
            }


            const price =
                parseInt(
                    priceInput.value || "0",
                    10
                );


            const percent =
                parseInt(
                    discountPercentInput.value || "0",
                    10
                );


            if (
                price <= 0 ||
                percent <= 0 ||
                percent > 100
            ) {
                return;
            }


            const finalPrice =
                Math.round(
                    price -
                    (
                        price * percent / 100
                    )
                );


            finalPriceInput.value =
                finalPrice;

        }


        if (priceInput) {

            priceInput.addEventListener(
                "input",
                calculateFinalPrice
            );

        }


        if (discountPercentInput) {

            discountPercentInput.addEventListener(
                "input",
                calculateFinalPrice
            );

        }

    }
);



// ============================================================
// DELETE PRODUCT IMAGE
// ============================================================

function deleteProductImage(
    productId,
    imageNumber
) {

    if (
        !confirm(
            "آیا از حذف این تصویر مطمئن هستید؟"
        )
    ) {

        return;

    }


    const form =
        document.createElement(
            "form"
        );


    form.method = "POST";


    form.action =
        `/owner/products/${productId}/image/${imageNumber}/delete`;


    document.body.appendChild(
        form
    );


    form.submit();

}