# انتشار رایگان شهدآور — نسخه آماده استقرار

## مسیر پیشنهادی برای همین نسخه

این پروژه از SQLite و فایل‌های محلی `uploads/` استفاده می‌کند؛ بنابراین برای کمترین تغییر معماری، **PythonAnywhere Free** مناسب‌تر از سرویس‌های رایگانی است که فایل‌سیستمشان موقتی است.

> نکته: طبق شرایط فعلی سرویس، حساب‌های رایگان جدید محدودیت زمانی برای Web App دارند و باید وضعیت حساب/وب‌اپ را در پنل سرویس پیگیری کنید. برای فروشگاه دائمی و جدی، بعداً بهتر است دیتابیس و فایل‌ها به سرویس‌های پایدار منتقل شوند.

## راه‌اندازی

1. در PythonAnywhere یک حساب رایگان بسازید.
2. یک Web App جدید بسازید و دامنه رایگان `USERNAME.pythonanywhere.com` را انتخاب کنید.
3. Python 3.12 را انتخاب کنید.
4. فایل ZIP را در Files آپلود و Extract کنید.
5. مسیر پروژه را در Web App تنظیم کنید.
6. در بخش WSGI، فایل WSGI را روی `wsgi.py` همین پروژه تنظیم کنید؛ مقدار WSGI نهایی باید شبیه این باشد:

```python
import sys
path = '/home/USERNAME/shahdavar_v7'
if path not in sys.path:
    sys.path.insert(0, path)
from wsgi import application
```

7. در بخش Environment Variables این مقادیر را تنظیم کنید:

```text
FLASK_SECRET_KEY=یک_رشته_تصادفی_طولانی_و_محرمانه
SITE_PUBLIC_URL=https://USERNAME.pythonanywhere.com
SESSION_COOKIE_SECURE=1
GOOGLE_SITE_VERIFICATION=
```

8. Web App را Reload کنید.
9. این دو آدرس را در مرورگر تست کنید:

- `/`
- `/robots.txt`
- `/sitemap.xml`

## Google

بعد از اینکه URL عمومی سایت باز شد:

1. وارد Google Search Console شوید.
2. URL سایت را به‌عنوان URL-prefix اضافه کنید.
3. برای Verification می‌توانید مقدار HTML tag را در `GOOGLE_SITE_VERIFICATION` قرار دهید.
4. Sitemap را با آدرس زیر ثبت کنید:

```text
https://USERNAME.pythonanywhere.com/sitemap.xml
```

صفحات `/owner` و APIهای خصوصی در robots.txt برای موتور جست‌وجو بسته شده‌اند.

## نکته مهم درباره دامنه

آدرس رایگان سرویس، دامنه اختصاصی شهدآور نیست. دامنه‌ای مثل `shahdavar.ir` معمولاً نیاز به خرید/ثبت دامنه دارد. اما خودِ انتشار با URL سرویس می‌تواند بدون پرداخت هزینه انجام شود.
