# pip install requests beautifulsoup4 python-telegram-bot

# import codecs
import logging
import random
import re
import requests
from bs4 import BeautifulSoup
import time
from telegram import Update, Bot
from telegram.ext import (
    filters,
    MessageHandler,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    Defaults,
    ExtBot,
)
import asyncio

from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DSSID = os.getenv("DSS_ID")
DSSPW = os.getenv("DSS_PW")


# 도싸 장터 URL과 검색할 키워드
# 구동계 장터
# OSSA_LIST_URL = "http://m.corearoadbike.com/board/board.php?t_id=Menu31Top6"
DOSSA_LIST_URL = (
    "http://m.corearoadbike.com/board/board.php?g_id=recycle02&t_id=Menu31Top6&page="
)
SEARCH_KEYWORD = "듀라"

base_url = "http://m.corearoadbike.com"
url_login = "https://m.corearoadbike.com:444/mypage/?M=login&login_B_url=%2F%3F"
url_login_base = "https://m.corearoadbike.com:444/"
url_login_action = ""
# "https://m.corearoadbike.com:444/"
# "https://m.corearoadbike.com:444/mypage/?M=login&login_B_url=%2F%3F"

# 브라우저의 User-Agent 헤더 설정
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

# 이전에 본 매물 저장
seen_posts = set()
sent_posts = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str, photo_link: str) -> None:
    """Function send telegram message"""
    bot = Bot(TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(TELEGRAM_CHAT_ID, message)
        if photo_link:
            print(f"trying to send photo with telegram {photo_link}")
            await bot.send_photo(TELEGRAM_CHAT_ID, photo_link)
    except Exception as e:
        logger.error(f"Failed to send message or photo: {e}")


def fetch_posts_then_save(url, file_name):
    """Function fetch posts and then save"""
    logger.info("trying to fetch from dossa and then save to file")
    response = requests.get(url, headers=headers, timeout=10)
    # HTML 내용을 파일로 저장합니다.
    with open(file_name, "w", encoding="utf-8") as file:
        file.write(response.text)


def fetch_html(url, session):

    logger.info(f"trying to fetch from dossa: {url}")
    try:
        # GET 요청을 보내고 응답을 받습니다.
        response = session.get(
            url,
            headers=headers,
            timeout=10,
            cookies=session.cookies,
        )

        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while fetching HTML: {e}")
        return None


def fetch_html_from_file(fileName):
    logger.info(f"reading {fileName} file")

    html_content = ""

    # 파일에서 HTML 내용을 읽어옵니다.
    with open(fileName, "r", encoding="utf-8") as file:
        html_content = file.read()

    return html_content


def dss_login(session, go_url_value=None) -> requests.Session:
    logger.debug(f"Login page URL: {url_login}")

    with requests.Session() as session:
        try:
            # Fetch the login page
            html_text = fetch_html(url_login, session)
            if html_text is None:
                raise ValueError("Failed to fetch HTML content from the login page.")

            soup = BeautifulSoup(html_text, "html.parser")
            if go_url_value is None:
                go_url_input = soup.find("input", {"name": "go_url"})

                if go_url_input:
                    go_url_value = go_url_input.get("value")
                    logger.info(f"Extracted go_url value: {go_url_value}")
                else:
                    logger.error("go_url input tag not found.")
                    # return None

            # Define the URL for the login form submission
            url_login_action = f"{url_login_base}mypage/mypage_data.inc"
            go_url_value = "http://m.corearoadbike.com/board/board.php?g_id=recycle02&t_id=Menu31Top6&no=419802"
            # go_url_value = "http://m.corearoadbike.com/board/board.php?g_id=recycle02&t_id=Menu31Top6"
            payload = {
                "type": "login",
                "M": "login",
                "go_url": go_url_value,
                "login_id": DSSID,
                "login_pw": DSSPW,
                "Chk_Auto_Login": "on",
            }

            # Send the POST request to login
            response = session.post(
                url_login_action, data=payload, headers=headers, allow_redirects=True
            )
            response.raise_for_status()

            if response.ok:
                logger.info("Login successful!")
                return session  # Return the session object for further use

            logger.error(f"Login failed! Status code: {response.status_code}")
            logger.info(
                f"Payload: url_login_action: {url_login_action}, go_url: {go_url_value}, login_id: {DSSID}, login_pw: {DSSPW}"
            )

            logger.error(response.text)
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Login failed! An error occurred: {e}")
            return None


def check_details(details_url, session) -> bool:
    """매물 상세페이지를 검사해서 keyword가 포함되어 있는지 확인한다."""
    details_file = ""  # "sample_details.html"
    if details_file:
        logger.info("read html from file")
        html_text = fetch_html_from_file(details_file)
    elif details_url:
        logger.info(f"read html from online : {details_url}")
        html_text = fetch_html(details_url, session)

    if html_text is not None:
        soup = BeautifulSoup(html_text, "html.parser")
        body_cell = soup.find("td", class_="bd_vw_ct")
        body_text = body_cell.text.strip() if body_cell else ""
        if bool(
            body_text
            and ("167" in body_text)
            and ("크랭크" in body_text or "crank" in body_text)
        ):
            print("Matched #####################")
            print(f"[{body_text}]")
            print("----------------------")
            return True
        elif "지금 로그인을 하시겠습니까?" in html_text:
            logger.info("Failed to fetch details, tyring to login...")
            script_text = soup.find("script").text.strip()

            # Regular expression to find the location.replace URL
            pattern = r"location\.replace\(\s*['\"](.*?)['\"]\s*\)"

            # Search for the pattern in the script_text
            match = re.search(pattern, script_text)

            if match:
                go_url = match.group(1)
                print("Extracted URL:", go_url)
            else:
                print("URL not found")

            # 0. go to login page

            # 1. process login
            session = dss_login(session, go_url)
            # 2. return check_detail(details_url)
            time.sleep(random.randint(3, 8))
            return check_details(details_url, session)

        else:
            print("Not Matched #####################")
            print(f"[{body_text}]")
            print("----------------------")
    return False


def fetch_recent_pages(session):
    posts = []
    posts = fetch_list(1, session)
    posts += fetch_list(2, session)
    posts += fetch_list(3, session)
    posts += fetch_list(4, session)
    posts += fetch_list(5, session)
    return posts


def fetch_list(pageNum, session):
    posts = []
    # fetch_posts_then_save(DOSSA_LIST_URL, "sample.html")

    # html_content = fetch_html_from_file("sample.html")
    logger.info(f"Trying to fetch page#{pageNum}")
    time.sleep(random.randint(3, 8))
    html_content = fetch_html(f"{DOSSA_LIST_URL}{pageNum}", session)
    soup = BeautifulSoup(html_content, "html.parser")
    rows = soup.find_all("td", class_="bd_ls_tt text_cut")

    # Loop through each row and check for the keyword "듀라"
    keyword = "듀라"

    for row in rows:
        if keyword in row.text:
            title = row.text.strip()
            print(f"title: {title}")
            print(f"row: {row}")

            papa_row = row.find_parent("table", class_="hand")
            onclick_attr = papa_row.get("onclick")
            if onclick_attr:
                print(f"onclick_attr: {onclick_attr}")
                # Extract URL from the onclick attribute
                url_part = onclick_attr.split("location.href='")[1].split("';")[0]
                link = f"{base_url}/board/{url_part[2:]}"  # Remove './' from the relative URL
                # Thumbnail image
                thumbnail = papa_row.find("img")
                thumbnail_link = (
                    f"{base_url}/{thumbnail.get('src')[1:]}" if thumbnail else ""
                )
                print(f"Title(1차): {title}")
                # print(f"URL: {link}\n")
                # print(f"thumbnail: {thumbnail_link}\n")
                # check_image_url(thumbnail_link)
                posts.append((title, link, thumbnail_link))

    return posts


async def main():

    with requests.Session() as session:
        while True:
            try:
                posts = fetch_recent_pages(session)

                for title, link, thumnail in posts:
                    if title not in seen_posts:
                        seen_posts.add(title)

                        time.sleep(random.randint(3, 8))
                        if check_details(link, session):
                            print(f"Matched): {title}")
                            message = f"새 매물: {title}\n링크:{link}"
                            await send_telegram_message(message, "")
                        else:
                            print(f"Not matched: {title}")

                    else:
                        print(f"old item: {title}")
                logger.info("Sleeping 5 minutes...")
                time.sleep(60 * random.randint(3, 5))  # 3-5분마다 체크
            except Exception as e:
                logger.error(f"Error: {e}")
                logger.info("Sleeping 15 minutes...")
                time.sleep(60 * 15)  # 에러가 발생해도 15분마다 재시도


if __name__ == "__main__":
    asyncio.run(main())
