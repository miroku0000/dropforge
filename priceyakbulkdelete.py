import requests
import sys
import json


def txt_to_lst(file_path):
    try:
        stopword = open(file_path, "r")
        lines = stopword.read().split("\n")
        print(lines)
        lines.pop()
        out = []
        for line in lines:
            if "22" in line:
                out.append(line)
        return out

    except Exception as e:
        print(e)


import config
account_id = config.PY_ACCOUNT_ID
api_key = config.PY_API_KEY
import requests


def login(account_id, api_key):
    headers = {
        # Already added when you pass json=
        # 'Content-Type': 'application/json',
    }
    json_data = {
        "api_key": api_key,
    }
    response = requests.post(
        "https://www.priceyak.com/v0/account/{id}/api_login".format(id=account_id),
        headers=headers,
        json=json_data,
    )
    return response.json()["token"]


def get_settings(account_id, token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": token,
    }

    response = requests.get(
        "https://www.priceyak.com/v0/account/{id}".format(id=account_id),
        headers=headers,
    )
    return response.text


token = login(account_id, api_key)

print(token)
killme = txt_to_lst("d:\\zikprocessor\\data\\kill.txt")

print(killme)
if len(killme) < 1:
    print("Nothing to kill")
    exit(0)

burp0_url = f"https://www.priceyak.com:443/v0/account/{config.PY_ACCOUNT_ID}/listings/bulk_delist"
# burp0_cookies = {"_fbp": "fb.1.1674686674927.1017553593", "_pk_ses.1.dd9e": "1", "_ga": "GA1.2.500608049.1674686675", "_gid": "GA1.2.1123531656.1674686675", "_ga_EDJB4JZ3C7": "GS1.1.1674686675.1.0.1674686678.0.0.0", "pyauth": "\"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiSndrOFQyaXZDMkFUYWNFZUtpMXVTZSIsInJvbGVzIjpbXSwiYWRtaW4iOmZhbHNlLCJleHAiOjE2NzQ3NzMxMTAsInN0b3JlcyI6WyJCdkFLVkJuQkxUWWFmdlVBWUhDd2llIl0sImVtYWlsIjoibWlyb2t1MDAwQGdtYWlsLmNvbSJ9.3QSt5JghdPDF6gTlKlwbr9NSYJUZLVqSJIol0euNjZs\"", "py_last_login": "1674686710.09", "_hp2_ses_props.2959502054": "%7B%22r%22%3A%22https%3A%2F%2Fwww.priceyak.com%2F%22%2C%22ts%22%3A1674686681266%2C%22d%22%3A%22www.priceyak.com%22%2C%22h%22%3A%22%2Flogin%22%7D", "ph_UpO7eN3a9gQkahDHq6IinbV1cnXzGpNZGvFZyOMGOSA_posthog": "%7B%22distinct_id%22%3A%22Jwk8T2ivC2ATacEeKi1uSe%22%2C%22%24device_id%22%3A%22185eb1ad0d6f6-0f466a0c6b465a-12363b7c-1fa400-185eb1ad0d7286%22%2C%22%24initial_referrer%22%3A%22https%3A%2F%2Fwww.priceyak.com%2F%22%2C%22%24initial_referring_domain%22%3A%22www.priceyak.com%22%2C%22%24referrer%22%3A%22https%3A%2F%2Fwww.priceyak.com%2F%22%2C%22%24referring_domain%22%3A%22www.priceyak.com%22%2C%22%24session_recording_enabled%22%3Afalse%2C%22%24active_feature_flags%22%3A%5B%5D%2C%22%24user_id%22%3A%22Jwk8T2ivC2ATacEeKi1uSe%22%7D", "_pk_id.1.dd9e": "a06157975de88641.1674686675.1.1674688921.1674686675.", "_hp2_id.2959502054": "%7B%22userId%22%3A%225412061984406481%22%2C%22pageviewId%22%3A%223049038024148113%22%2C%22sessionId%22%3A%226400052846065965%22%2C%22identity%22%3A%22miroku000%40gmail.com%22%2C%22trackerVersion%22%3A%224.0%22%2C%22identityField%22%3Anull%2C%22isIdentified%22%3A1%7D"}
burp0_cookies = {}
burp0_headers = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.priceyak.com",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
    "Authorization": "Bearer " + token,
}

# burp0_jsonorig={"itemids": ["225370738815", "225370738815"], "shred": False}
# burp0_json={"itemids": ["225357195239"] , "shred": False}
burp0_json = {"itemids": killme, "shred": False}
r = requests.post(
    burp0_url, headers=burp0_headers, cookies=burp0_cookies, json=burp0_json
)
print(r.text)
print(r.status_code)
