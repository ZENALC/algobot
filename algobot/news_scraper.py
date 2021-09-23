"""
News scraper function.
"""

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
    url = 'https://www.todayonchain.com/'
    page = requests.get(url)

    soup = BeautifulSoup(page.content, 'html.parser')
    links = soup.find('div', class_='api_article_include').find_all('a')

    html_rows = []
    for link in links:
        hyperlink = link['href']
        title = link.find('div', class_='api_article_title_sm').text
        source = link.find('span', class_='api_article_source').text

        event_date = link.find('time', class_='timeago')['datetime']
        parsed_date = parser.parse(event_date).astimezone(tz=None)
        if parsed_date.date() == date.today():
            date_string = f'today {parsed_date.strftime("%m/%d/%Y %H:%M:%S")}'
        elif parsed_date.date() == date.today() - timedelta(days=1):
            date_string = f'yesterday {parsed_date.strftime("%m/%d/%Y %H:%M:%S")}'
        else:
            date_string = parsed_date.strftime("%A %m/%d/%Y %H:%M:%S")

        html_row = f'<a href="{hyperlink}">{title}</a>' \
                   f'<p>Post from {source} published {date_string} local time.</p>'
        html_rows.append(html_row)

    return html_rows


if __name__ == '__main__':
    news = scrape_news()
