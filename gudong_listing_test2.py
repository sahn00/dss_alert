import logging
import random
import re
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot
from dotenv import load_dotenv
import os
from typing import List, Optional, Tuple

# catgpt가 고쳐준 코드
"""
주요 변경 사항:
aiohttp 사용: 비동기 HTTP 요청을 위해 aiohttp를 사용했습니다. 이를 통해 효율적으로 네트워크 요청을 처리할 수 있습니다.
예외 처리 및 재시도 로직: HTTP 요청에서 발생할 수 있는 예외를 처리하고, 오류가 발생했을 때 적절한 대처를 추가했습니다.
비동기 함수 사용: 모든 주요 함수에 async와 await를 추가하여 비동기적으로 동작하도록 변경했습니다.
이러한 개선 사항을 통해 프로그램의 안정성을 높이고, 세션 드롭 문제를 줄일 수 있을 것입니다.
"""
# .env 파일 로드
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DSSID = os.getenv("DSS_ID")
DSSPW = os.getenv("DSS_PW")

# 도싸 장터 URL과 검색할 키워드
DOSSA_LIST_URL = (
    "http://m.corearoadbike.com/board/board.php?g_id=recycle02&t_id=Menu31Top6&page="
)
SEARCH_KEYWORD = "듀라"

base_url = "http://m.corearoadbike.com"
url_login = "https://m.corearoadbike.com:444/mypage/?M=login&login_B_url=%2F%3F"
url_login_action = "https://m.corearoadbike.com:444/mypage/mypage_data.inc"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

seen_posts = set()
sent_posts = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)


async def send_telegram_message(message: str, photo_link: Optional[str] = None) -> None:
    bot = Bot(TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(TELEGRAM_CHAT_ID, message)
        if photo_link:
            await bot.send_photo(TELEGRAM_CHAT_ID, photo_link)
    except Exception as e:
        logger.error(f"Failed to send message or photo: {e}")


async def fetch_html(url: str, session: aiohttp.ClientSession) -> str:
    logger.info(f"Trying to fetch from {url}")
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            response.raise_for_status()
            return await response.text()
    except aiohttp.ClientError as e:
        logger.error(f"An error occurred while fetching HTML: {e}")
        return None


async def dss_login(
    session: aiohttp.ClientSession, go_url_value=None
) -> aiohttp.ClientSession:
    try:
        html_text = await fetch_html(url_login, session)
        if html_text is None:
            raise ValueError("Failed to fetch HTML content from the login page.")

        soup = BeautifulSoup(html_text, "html.parser")
        if go_url_value is None:
            go_url_input = soup.find("input", {"name": "go_url"})
            if go_url_input:
                go_url_value = go_url_input.get("value")
            else:
                raise ValueError("go_url input tag not found.")

        payload = {
            "type": "login",
            "M": "login",
            "go_url": go_url_value,
            "login_id": DSSID,
            "login_pw": DSSPW,
            "Chk_Auto_Login": "on",
        }

        async with session.post(
            url_login_action, data=payload, headers=headers
        ) as response:
            response.raise_for_status()
            if response.ok:
                logger.info("Login successful!")
                return session

            logger.error(f"Login failed! Status code: {response.status}")
            return None

    except aiohttp.ClientError as e:
        logger.error(f"Login failed! An error occurred: {e}")
        return None


async def check_details(details_url: str, session: aiohttp.ClientSession) -> bool:
    html_text = await fetch_html(details_url, session)
    if html_text:
        soup = BeautifulSoup(html_text, "html.parser")
        body_cell = soup.find("td", class_="bd_vw_ct")
        body_text = body_cell.text.strip() if body_cell else ""
        if bool(
            body_text
            and ("167" in body_text)
            and ("크랭크" in body_text or "crank" in body_text)
        ):
            logger.info(f"Matched: {body_text}")
            return True
        elif "지금 로그인을 하시겠습니까?" in html_text:
            logger.info("Failed to fetch details, trying to login...")
            script_text = soup.find("script").text.strip()
            pattern = r"location\.replace\(\s*['\"](.*?)['\"]\s*\)"
            match = re.search(pattern, script_text)
            if match:
                go_url = match.group(1)
                session = await dss_login(session, go_url)
                await asyncio.sleep(random.randint(3, 8))
                return await check_details(details_url, session)

    return False


async def fetch_list(
    pageNum: int, session: aiohttp.ClientSession
) -> List[Tuple[str, str, str]]:
    posts = []
    logger.info(f"Trying to fetch page#{pageNum}")
    await asyncio.sleep(random.randint(3, 8))
    html_content = await fetch_html(f"{DOSSA_LIST_URL}{pageNum}", session)
    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        rows = soup.find_all("td", class_="bd_ls_tt text_cut")

        keyword = "듀라"
        for row in rows:
            if keyword in row.text:
                title = row.text.strip()
                papa_row = row.find_parent("table", class_="hand")
                onclick_attr = papa_row.get("onclick") if papa_row else None
                if onclick_attr:
                    url_part = onclick_attr.split("location.href='")[1].split("';")[0]
                    link = f"{base_url}/board/{url_part[2:]}"
                    thumbnail = papa_row.find("img")
                    thumbnail_link = (
                        f"{base_url}/{thumbnail.get('src')[1:]}" if thumbnail else ""
                    )
                    # post#
                    no_value = ""
                    match = re.search(r"no=(\d+)", link)
                    if match:
                        no_value = match.group(1)
                        print(no_value)  # Output: 421067

                    posts.append((no_value, title, link, thumbnail_link))

    return posts


async def fetch_recent_pages(
    session: aiohttp.ClientSession,
) -> List[Tuple[str, str, str]]:
    tasks = [fetch_list(pageNum, session) for pageNum in range(1, 6)]
    results = await asyncio.gather(*tasks)

    # Flatten the list of lists
    posts = [post for sublist in results for post in sublist]
    return posts


async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                posts = await fetch_recent_pages(session)
                for no_value, title, link, thumbnail in posts:
                    if no_value not in seen_posts:
                        seen_posts.add(no_value)
                        await asyncio.sleep(random.randint(3, 8))
                        if await check_details(link, session):
                            message = f"새 매물: {title}\n링크: {link}"
                            await send_telegram_message(message)
                        else:
                            logger.info(f"Not matched: {no_value}:{title}")
                    else:
                        logger.info(f"Old item:  {no_value}:{title}")

                logger.info("Sleeping 5 minutes...")
                await asyncio.sleep(60 * random.randint(3, 5))  # 3-5분마다 체크
            except Exception as e:
                logger.error(f"Error: {e}")
                logger.info("Sleeping 15 minutes...")
                await asyncio.sleep(60 * 15)  # 에러가 발생해도 15분마다 재시도


if __name__ == "__main__":
    asyncio.run(main())
