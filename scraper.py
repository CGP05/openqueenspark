import requests
from bs4 import BeautifulSoup

url = "https://www.ola.org/en/legislative-business/house-documents/parliament-44/session-1"

response = requests.get(url)

print(response.status_code)
print(response.text[:500])