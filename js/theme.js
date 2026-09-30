(function () {
    "use strict";

    const THEME_KEY = "shahdavar-theme";
    const root = document.documentElement;
    const saved = localStorage.getItem(THEME_KEY);
    const preferred = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    root.dataset.theme = saved === "dark" || saved === "light" ? saved : preferred;

    function setTheme(theme) {
        const value = theme === "dark" ? "dark" : "light";
        root.dataset.theme = value;
        localStorage.setItem(THEME_KEY, value);
        updateThemeControls();
    }

    function updateThemeControls() {
        const dark = root.dataset.theme === "dark";
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.setAttribute("aria-pressed", String(dark));
            button.setAttribute("title", dark ? "تغییر به حالت روشن" : "تغییر به حالت تاریک");
            button.innerHTML = `<span class="theme-switch-track" aria-hidden="true"><span class="theme-switch-sun">☀</span><span class="theme-switch-moon">☾</span><span class="theme-switch-knob"></span></span><span class="theme-switch-label">${dark ? "حالت تاریک" : "حالت روشن"}</span>`;
        });
        document.querySelectorAll(".theme-toggle").forEach((button) => {
            button.textContent = dark ? "☀️" : "🌙";
            button.title = dark ? "حالت روشن" : "حالت تاریک";
        });
    }

    function buildGlobalMenu() {
        if (document.getElementById("globalQuickMenu")) return;
        document.querySelectorAll(".menu-button, .mobile-menu").forEach((el) => {
            el.setAttribute("aria-hidden", "true");
            el.style.display = "none";
        });

        const wrap = document.createElement("div");
        wrap.id = "globalQuickMenu";
        wrap.className = "global-quick-menu";
        wrap.innerHTML = `
            <button type="button" class="global-menu-button" id="globalMenuButton" aria-expanded="false" aria-controls="globalMenuPanel" aria-label="باز کردن منوی سریع">
                <span></span><span></span><span></span>
            </button>
            <aside class="global-menu-panel" id="globalMenuPanel" hidden aria-label="منوی سریع">
                <div class="global-menu-head"><strong>منوی سریع</strong><span>شهدآور</span></div>
                <div class="global-menu-scroll">
                    <button type="button" class="global-theme-action" data-theme-toggle></button>
                    <nav class="global-menu-links">
                        <a href="/">🏠 خانه</a>
                        <a href="/pages/products.html">🛒 محصولات</a>
                        <a href="/cart">🛍️ سبد خرید</a>
                        <a href="/orders">📦 تاریخچه خرید</a>
                        <a href="/account">👤 حساب کاربری</a>
                        <a href="/pages/profiles.html">◎ پروفایل</a>
                        <a href="/pages/about.html">🍯 درباره شهدآور</a>
                        <a href="/pages/contact.html">📞 تماس با ما</a>
                        <a href="/pages/support.html">🎧 پشتیبانی</a>
                        <a href="/pages/ai.html">🤖 شهدیار</a>
                        <a href="/pages/knowledge.html">✦ دانستنی و اطلاعات</a>
                    </nav>
                </div>
            </aside>`;
        document.body.appendChild(wrap);

        const button = wrap.querySelector("#globalMenuButton");
        const panel = wrap.querySelector("#globalMenuPanel");
        const close = () => {
            panel.hidden = true;
            button.setAttribute("aria-expanded", "false");
            wrap.classList.remove("open");
        };
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            const open = panel.hidden;
            panel.hidden = !open;
            button.setAttribute("aria-expanded", String(open));
            wrap.classList.toggle("open", open);
        });
        panel.addEventListener("click", (event) => {
            const theme = event.target.closest("[data-theme-toggle]");
            if (theme) {
                event.preventDefault();
                setTheme(root.dataset.theme === "dark" ? "light" : "dark");
                return;
            }
            if (event.target.closest("a")) close();
        });
        document.addEventListener("click", (event) => {
            if (!wrap.contains(event.target)) close();
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") close();
        });
    }

    function buildCartBar() {
        if (document.getElementById("shahdavarCartBar")) return;
        fetch("/api/cart/summary", {cache:"no-store"}).then(r=>r.json()).then(d=>{
            if (!d.success || !d.count) return;
            const bar=document.createElement("div"); bar.id="shahdavarCartBar"; bar.setAttribute("role","region"); bar.setAttribute("aria-label","خلاصه سبد خرید"); bar.innerHTML=`<div><strong>🛒 شما ${d.count} محصول را انتخاب کرده‌اید</strong><span>جمع: ${Number(d.total||0).toLocaleString('fa-IR')} تومان</span></div><a href="/cart">مشاهده سبد خرید</a>`; document.body.classList.add("has-cart-bar"); document.body.appendChild(bar);
        }).catch(()=>{});
    }

    // Every same-origin state-changing fetch automatically carries the CSRF token.
    function installFetchProtection() {
        if (window.__shahdavarFetchProtected) return;
        const originalFetch = window.fetch.bind(window);
        window.fetch = function (input, init) {
            init = init || {};
            const url = typeof input === "string" ? input : input.url;
            const method = (init.method || (typeof input !== "string" && input.method) || "GET").toUpperCase();
            if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS" && /^\//.test(url || "")) {
                const meta = document.querySelector('meta[name="csrf-token"]');
                const token = meta && meta.content;
                if (token) {
                    const headers = new Headers(init.headers || (typeof input !== "string" ? input.headers : undefined));
                    headers.set("X-CSRFToken", token);
                    init.headers = headers;
                }
            }
            return originalFetch(input, init);
        };
        window.__shahdavarFetchProtected = true;
    }

    document.addEventListener("DOMContentLoaded", function () {
        buildGlobalMenu();
        updateThemeControls();
        installFetchProtection();
        buildCartBar();
        document.querySelectorAll(".theme-toggle").forEach((button) => {
            button.addEventListener("click", () => setTheme(root.dataset.theme === "dark" ? "light" : "dark"));
        });
    });
})();
