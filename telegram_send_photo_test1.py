import logging
import requests
from bs4 import BeautifulSoup
import asyncio
from telegram import Bot
from telegram.ext import ContextTypes

from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DSSID = os.getenv("DSSID")
DSSPW = os.getenv("DSSPW")

# 도싸 장터 URL과 검색할 키워드
DOSSA_URL = "http://m.corearoadbike.com/board/board.php?t_id=Menu31Top6"
SEARCH_KEYWORD = "듀라"

base_url = "http://m.corearoadbike.com/"

# 브라우저의 User-Agent 헤더 설정
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

# 이전에 본 매물 저장
seen_posts = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str, photo_url: str) -> None:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        if photo_url:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url},
            )
            response.raise_for_status()  # Raise an exception for HTTP errors
    except Exception as e:
        logger.error(f"Failed to send message or photo: {e}")


def fetch_html_from_dossa():
    logger.info("Trying to fetch dossa_url")
    try:
        response = requests.get(DOSSA_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to fetch URL: {e}")
        return ""


def fetch_posts():
    posts = []
    html_content = fetch_html_from_dossa()
    if not html_content:
        return posts

    soup = BeautifulSoup(html_content, "html.parser")
    rows = soup.find_all("td", class_="bd_ls_tt text_cut")
    keyword = "듀라"

    for row in rows:
        if keyword in row.text:
            title = row.text.strip()
            papa_row = row.find_parent("table", class_="hand")
            onclick_attr = papa_row.get("onclick")
            if onclick_attr:
                url_part = onclick_attr.split("location.href='")[1].split("';")[0]
                link = f"{base_url}board/{url_part[2:]}"
                thumbnail = papa_row.find("img")
                thumbnail_link = (
                    f"{base_url}{thumbnail.get('src')[1:]}" if thumbnail else ""
                )
                posts.append((title, link, thumbnail_link))

    return posts


async def main():
    # while True:
    try:
        # posts = fetch_posts()
        # for title, link, thumbnail_link in posts:
        # if title not in seen_posts:
        # seen_posts.add(title)
        title = "듀라M"
        link = "http://m.corearoadbike.com/board/board.php?g_id=recycle02&t_id=Menu31Top6&no=419802"
        thumbnail_link = "http://m.corearoadbike.com/data/file/Menu31Top6/thumbnail/1721292524125_xDUze.jpg"
        message = f"새 매물: {title}\n링크: {link}"
        await send_telegram_message(message, thumbnail_link)
    # else:
    # logger.info(f"Old item: {title}")
    # await asyncio.sleep(60 * 1)  # 1분마다 체크
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        # await asyncio.sleep(60 * 5)  # 에러가 발생해도 5분마다 재시도


if __name__ == "__main__":
    asyncio.run(main())
