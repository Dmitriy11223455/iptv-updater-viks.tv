import asyncio
import datetime
import os
import random
from playwright.async_api import async_playwright

USER_AGENT_STRING = 'Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36'

async def scroll_page(page):
    for _ in range(3):
        await page.mouse.wheel(560, 300)
        await asyncio.sleep(2)
        

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка всех каналов на сайте...", flush=True)
    try:
        # wait_until="domcontentloaded" стабильнее, чем "commit"
        await page.goto("https://live.viks.tv/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        await scroll_page(page)
        found = {}
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    # ИСПРАВЛЕНО: Сначала переводим в верхний регистр строку, а потом чистим/режем, если надо
                    clean = name.strip().upper() 
                    if clean and (".html" in url or "/public/" in url):
                        full_url = url if url.startswith("http") else f"https://smotru.tv/{url}"
                        if clean not in found: 
                            found[clean] = full_url
            except: 
                continue
        print(f"[+] Найдено каналов на сайте: {len(found)}")
        return found
    except Exception as e:
        print(f"[!] Ошибка парсинга: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    MY_CHANNELS = {
        "РОССИЯ 1": "https://live.viks.tv/102407-rossiya1_tv.html",
        "РЕН ТВ": "https://live.viks.tv/026722-ren-tv.html",
        "НТВ": "https://viks.tv",
        "ПЕРВЫЙ КАНАЛ": "https://viks.tv",
        "РОССИЯ 24": "https://viks.tv",
        "РТР ПЛАНЕТА": "https://viks.tv",
        "КАНАЛ Ю": "https://viks.tv",
        "ТНТ": "https://viks.tv",
        "ЗВЕЗДА": "https://viks.tv",
        "СТС": "https://viks.tv",
        "ТВЦ": "https://viks.tv"
        
    }
    
    async def scroll_page(page):
        for _ in range(3):
            await page.mouse.wheel(560, 300)
            await asyncio.sleep(2)

    async with async_playwright() as p:
        is_github = os.getenv('GITHUB_ACTIONS') == 'true'
        print(f">>> [2/3] Запуск браузера (GitHub Mode: {is_github})...", flush=True)
        
        browser = await p.chromium.launch(
            headless=True,
            channel="chrome",
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        # ИСПРАВЛЕНО: Удален extra_http_headers, ломающий загрузку CSS-стилей
        context = await browser.new_context(
            user_agent=USER_AGENT_STRING,
            viewport={'width': 1280, 'height': 720},
            extra_http_headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://live.viks.tv',
                'Pragma': 'no-cache',
                'Referer': 'https://live.viks.tv/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': 'Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'sec-ch-ua': '"Google Chrome";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': "Android"
            }
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        temp_page = await context.new_page()
        SCRAPED = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        for name, url in SCRAPED.items():
            if name not in MY_CHANNELS: 
                MY_CHANNELS[name] = url

        print(f"\n>>> [3/3] Сбор прямых ссылок (Лимит: 60)...", flush=True)
        results = []
        for name, url in list(MY_CHANNELS.items())[:60]:
            if url == "https://smotru.tv/": # Пропускаем заглушки, если они не спарсились нормально
                continue
                
            ch_page = await context.new_page()
            
            await ch_page.set_extra_http_headers({
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://live.viks.tv',
                'Pragma': 'no-cache',
                'Referer': 'https://live.viks.tv/028622-tet.html',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': 'Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'sec-ch-ua': '"Google Chrome";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"'
            })
            captured_urls = []

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "yandex", "metrika", "telemetry"]):
                    captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(12) 
                
                # Клик по плееру для инициализации потока, если автоматика не сработала
                await ch_page.mouse.click(640, 450)
                
                for _ in range(25):
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

        if results:
            filename = "playlist.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n\n")
                
                f.write(f'#EXTGROUP:http-user-agent={USER_AGENT_STRING}\n')
                f.write('#EXTGROUP:Referer=https://live.viks.tv/\n')
                
                
                if "?" in final_link:
                    f.write(f'{final_link}&http-user-agent={USER_AGENT_STRING}&Referer=https://live.viks.tv/\n')
                else:
                    f.write(f'{final_link}?http-user-agent={USER_AGENT_STRING}&Referer=https://live.viks.tv/\n')
            print(f"\n>>> ГОТОВО! Плейлист {filename} создан.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())




