import requests
import re
import html
import json

def extract_data_page_json(content):
    # Use regular expression to extract the content of data-page attribute
    match = re.search(r'data-page="([^"]*)"', content)

    if match:
        # Extract the content inside the quotes
        something = match.group(1)
        return something
    else:
        # If no match is found
        return None

def convert_json_str_to_dictionary(result):
    decoded_json_string = html.unescape(result)
    python_dict = json.loads(decoded_json_string)
    return python_dict

jobs = []
for i in range(1, 10000000000):
    url = f'https://unit1.hrandequity.utoronto.ca/?page={i}'
    response = requests.get(url)

    if response.status_code == 200:
        content_str = response.content.decode('utf-8')  
        json_str = extract_data_page_json(content_str)
        json_dict = convert_json_str_to_dictionary(json_str)

        new_jobs = json_dict["props"]["items"]["data"]
        if len(new_jobs)==0:
            break
        jobs+=new_jobs
        print(i)

    else:
        print(f'Failed to download {url}')

import csv
with open("result.csv", mode='w', newline='') as csv_file:
    field_names = jobs[0].keys()
    data = jobs 
    csv_writer = csv.DictWriter(csv_file, fieldnames=field_names)
    # Write the header
    csv_writer.writeheader()
    # Write the data
    for row in jobs:
        csv_writer.writerow(row)
