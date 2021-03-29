from datetime import date, timedelta
from typing import List

import requests
from bs4 import BeautifulSoup
from dateutil import parser


def scrape_news() -> List[str]:
    """
    Scrapes latest news from www.todayonchain.com.
    :return: List of latest news.
    """
    URL = 'https://www.todayonchain.com/'
    page = requests.get(URL)

    soup = BeautifulSoup(page.content, 'html.parser')
    links = soup.find('div', class_='api_article_include').find_all('a')

    htmlRows = []
    for link in links:
        hyperlink = link['href']
        title = link.find('div', class_='api_article_title_sm').text
        source = link.find('span', class_='api_article_source').text

        eventDate = link.find('time', class_='timeago')['datetime']
        parsedDate = parser.parse(eventDate).astimezone(tz=None)
        if parsedDate.date() == date.today():
            dateString = f'today {parsedDate.strftime("%m/%d/%Y %H:%M:%S")}'
        elif parsedDate.date() == date.today() - timedelta(days=1):
            dateString = f'yesterday {parsedDate.strftime("%m/%d/%Y %H:%M:%S")}'
        else:
            dateString = parsedDate.strftime("%A %m/%d/%Y %H:%M:%S")

        htmlRow = f'<a href="{hyperlink}">{title}</a>' \
                  f'<p>Post from {source} published {dateString} local time.</p>'
        htmlRows.append(htmlRow)

    return htmlRows


if __name__ == '__main__':
    news = scrape_news()
