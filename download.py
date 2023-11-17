import requests

base_url = 'https://unit1.hrandequity.utoronto.ca/?page='
start_page = 1
end_page = 51

for page in range(start_page, end_page + 1):
    url = base_url + str(page)
    response = requests.get(url)

    if response.status_code == 200:
        file_name = f'page_{page}.html'  # Specify the desired file name
        with open(file_name, 'wb') as file:
            file.write(response.content)
            print(f'Downloaded {file_name}')
    else:
        print(f'Failed to download {url}')
