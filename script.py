import asyncio
import datetime
import os
import random
import urllib.parse
from playwright.async_api import async_playwright

USER_AGENT_STRING = 'Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36'

async def scroll_page(page):
    for _ in range(3):
        await page.mouse.wheel(560, 300)
        await asyncio.sleep(1.5)

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка всех каналов на сайте...", flush=True)
    try:
        await page.goto("https://ip.ontivi.net", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        await scroll_page(page)
        found = {}
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean = name.strip().upper() 
                    if clean and (".html" in url or "/public/" in url):
                        full_url = url if url.startswith("http") else f"https://ontivi.net{url}"
                        if clean not in found: 
                            found[clean] = full_url
            except: 
                continue
        print(f"[+] Найдено каналов на сайте: {len(found)}")
        return found
    except Exception as e:
        print(f"[!] Ошибка парсинга главной страницы: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    # Базовый список приоритетных каналов
    MY_CHANNELS = {
        "РОССИЯ 1": "https://ip.ontivi.net/094922-rossiya-1tv.html",
        "РЕН ТВ": "https://viks.tv",
        "НТВ": "https://ontivi.net029821-ntv.html",
        "ПЕРВЫЙ КАНАЛ": "https://ip.ontivi.net051810-pervyy-kanal.html"
    }

    async with async_playwright() as p:
        is_github = os.getenv('GITHUB_ACTIONS') == 'true'
        print(f">>> [2/3] Запуск браузера (GitHub Mode: {is_github})...", flush=True)
        
        browser = await p.chromium.launch(
            headless=True,
            channel='chrome',
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        context = await browser.new_context(
            user_agent=USER_AGENT_STRING,
            viewport={'width': 1280, 'height': 720}
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Собираем остальные каналы с сайта
        temp_page = await context.new_page()
        SCRAPED = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        for name, url in SCRAPED.items():
            if name not in MY_CHANNELS: 
                MY_CHANNELS[name] = url

        print(f"\n>>> [3/3] Сбор прямых ссылок (Лимит: 60)...", flush=True)
        results = []
        
        for name, url in list(MY_CHANNELS.items())[:60]:
            if url == "https://ip.ontivi.net":
                continue
                
            ch_page = await context.new_page()
            captured_urls = []

            async def handle_request(request):
                u = request.url
                if (".m3u8" in u or ".mpd" in u) and not any(x in u for x in ["ads", "yandex", "metrika", "telemetry"]):
                    captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(6) 
                
                # Симулируем активность кликом по плееру
                await ch_page.mouse.click(640, 450)
                
                # Ожидание ссылки в логах сети
                for _ in range(10):
                    if captured_urls: break
                    await asyncio.sleep(1)

                if captured_urls:
                    masters = [u for u in captured_urls if any(x in u for x in ["master", "index"])]
                    final_link = masters[-1] if masters else max(captured_urls, key=len)
                    results.append((name, str(final_link)))
                    print("OK", flush=True)
                else:
                    src = await ch_page.evaluate("() => document.querySelector('video') ? document.querySelector('video').src : null")
                    if src and "http" in src:
                        results.append((name, src))
                        print("OK (JS)", flush=True)
                    else:
                        print("FAIL", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                await ch_page.close()

        # БЛОК ГЕНЕРАЦИИ ПЕРСОНАЛЬНЫХ ПЛЕЙЛИСТОВ С ПРОКСИ
        if results:
            # ТУТ ВПИСЫВАЮТСЯ ВАШИ ЛЮДИ И ССЫЛКИ НА ИХ ПЕРСОНАЛЬНЫЕ РАБОЧИЕ ВОРКЕРЫ
            PROXIES = {
                "ivan": "https://silent-king-7bd4.vbarishnik50.workers.dev/?url="
                #"alex": "https://workers.dev",
                #"dmitry": "https://workers.dev",
                #"sister": "https://workers.dev"
            }

            output_dir = os.path.join(os.path.dirname(os.path.abspath(file)), "playlists")
            os.makedirs(output_dir, exist_ok=True)

            print(f"\n>>> [4/4] Воркер-генерация персональных плейлистов...", flush=True)

            for username, worker_url in PROXIES.items():
                filename = f"playlist_{username}.m3u"
                
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n\n")
                    
                    for channel_name, stream_url in results:
                        # Записываем правильное имя канала
                        f.write(f'#EXTINF:-1, {channel_name}\n')
                        
                        # Экранируем спецсимволы в стрим-ссылке для безопасной передачи через GET
                        encoded_stream = urllib.parse.quote_plus(stream_url)
                        proxy_url = f"{worker_url}?stream={encoded_stream}"
                        
                        f.write(f"{proxy_url}\n\n")
                        
                print(f"[+] Сгенерирован плейлист для: {username.upper()} -> файл: {filename}")
                
            print(f"\n>>> СБОРКА ЗАВЕРШЕНА! Всего создано файлов: {len(PROXIES)}")
        else:
            print("\n[!] Ошибка: Не удалось перехватить видео-потоки.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())
