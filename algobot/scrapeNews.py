import requests
from dateutil import parser, tz
from bs4 import BeautifulSoup


def scrape_news():
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
        parsedDate = parser.parse(eventDate).astimezone(tz=None).strftime("%A %m/%d/%Y %H:%M:%S")
        htmlRow = f'<a href="{hyperlink}">{title}</a> - {source} on {parsedDate} local time.'
        htmlRows.append(htmlRow)

    return htmlRows


if __name__ == '__main__':
    news = scrape_news()
