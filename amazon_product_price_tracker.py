import requests
import json
import slack
import os
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler

SLACK_TOKEN = os.environ['SLACK_TOKEN']
SCHEDULE_INTERVAL = int(os.environ['SCHEDULE_INTERVAL'])
ASINS = os.environ['ASINS']

with open('dorm_data.json', 'w') as file:
    json.dump([], file)

sched = BlockingScheduler()

def amazon_extractor(asin):
    HEADERS = ({'User-Agent':
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36',
            'Accept-Language': 'en-US, en;q=0.5'})
    
    url = f'https://www.amazon.in/dp/{asin}/'
    webpage = requests.get(url, headers=HEADERS)
    
    soup = BeautifulSoup(webpage.content, "lxml")

    title = get_title(soup)
    price = get_price(soup)
    
    return title, price, webpage.status_code

def get_title(soup):
    try:
        title = soup.find("span", attrs={"id":'productTitle'}).string.strip()
    except AttributeError:
        title = ""
    return title

def get_price(soup):
    try:
        price = soup.find("span", attrs={'class':'a-offscreen'}).string.strip()
    except AttributeError:
        price = ""
    return price


def main_extractor():
    data = {}

    statuses = []
    
    asins = ASINS.split(' | ')
    
    for asin in asins:
        title, price, status = amazon_extractor(asin)
        data[asin] = {'title': title, 'price': price}
        statuses.append(status)
    return data, statuses


def format_data(raw_data):
    product_blocks = []
    
    for key in raw_data.keys():
        product_data = [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{key}*\n*{raw_data[key].get('title')}*\nPrice: {raw_data[key].get('price')}\n{url}"
            }
        },
            {
                "type": "divider"
            }]


            
        product_blocks = product_blocks + product_data
    
    return product_blocks


def file_communicator(product_data):
    data = {
        'timestamp': datetime.now(tz=pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d %H:%M:%S"),
        'data': product_data
    }
    
    with open('product_data.json', 'r') as file:
        file_data = json.load(file)
    
    if len(file_data) > 0:
        old_raw_data = file_data[-1].get('data', {})
    else:
        old_raw_data = {}

    file_data.append(data)
    
    with open('product_data.json', 'w') as file:
        json.dump(file_data, file)
    
    return old_raw_data



def price_update_checker(raw_data, old_raw_data):

    if len(old_raw_data.keys()) - len(raw_data.keys()) != 0:
        return True

    for key in old_raw_data.keys():
        if old_raw_data[key].get('price', '') != raw_data[key].get('price', ''):
            return True
    return False



def push_update(data):
    formatted_blocks = format_data(data)
    client = slack.WebClient(token=SLACK_TOKEN)
    client.chat_postMessage(channel='#experiment', blocks=formatted_blocks)


@sched.scheduled_job('interval', minutes=SCHEDULE_INTERVAL)
def main():
    raw_data, status = main_extractor()

    old_raw_data = file_communicator(raw_data)

    update_check = price_update_checker(raw_data, old_raw_data)
    print(update_check, status)

    if update_check is True:
        push_update(raw_data)


sched.start()
