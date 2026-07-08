import urllib.request
import re

BASE='http://127.0.0.1:5000'
url_resort=BASE+'/resort'
html=urllib.request.urlopen(url_resort,timeout=10).read().decode('utf-8','ignore')
print('GET /resort length:',len(html))
print('resort-calendar occurrences:',len(re.findall('id="resort-calendar"',html)))
print('FullCalendar global present in HTML?', 'fullcalendar@6.1.15' in html)
print('Has calendar init code?', 'safeInitCalendar' in html or 'calendar.render' in html)

api_url=BASE+'/api/availability/resort'
api=urllib.request.urlopen(api_url,timeout=10)
print('API status:',api.status)
body=api.read().decode('utf-8','ignore')
print('API body start:',body[:300])

