import time
import random
import requests


def make_session(headers):
    session = requests.Session()
    session.headers.update(headers)
    return session


def get_json(session, url, params=None, attempts=3, timeout=20, label=""):
    """200 бол JSON, эцэст нь амжилтгүй бол None буцаана."""
    for i in range(attempts):
        try:
            res = session.get(url, params=params, timeout=timeout)
            if res.status_code == 200:
                return res.json()
            if res.status_code == 429:
                print(f"\n[Rate Limit] {label} — 30 сек хүлээж байна...")
                time.sleep(30)
            else:
                print(f"\n[{label}] HTTP {res.status_code}, оролдлого {i+1}/{attempts}")
                time.sleep(5)
        except Exception as e:
            print(f"\n[{label}] Оролдлого {i+1}/{attempts} амжилтгүй: {e}")
            time.sleep(8)
    return None


def post_json(session, url, body, attempts=3, timeout=30, label=""):
    """GraphQL зэрэг POST endpoint-д. Worki-д ашиглана."""
    for i in range(attempts):
        try:
            res = session.post(url, json=body, timeout=timeout)
            if res.status_code == 200:
                data = res.json()
                if "errors" in data:
                    print(f"\n[{label}] GraphQL алдаа: {data['errors']}")
                    return None
                return data.get("data")
            if res.status_code == 429:
                print(f"\n[Rate Limit] {label} — 30 сек хүлээж байна...")
                time.sleep(30)
            else:
                print(f"\n[{label}] HTTP {res.status_code}, оролдлого {i+1}/{attempts}")
                time.sleep(5)
        except Exception as e:
            print(f"\n[{label}] Оролдлого {i+1}/{attempts} амжилтгүй: {e}")
            time.sleep(8)
    return None


def polite_sleep(lo=1.0, hi=1.6):
    time.sleep(random.uniform(lo, hi))

# Html татах функц
def get_text(session, url, attempts=3, timeout=30, label=""):
    """HTML хуудас татна. Амжилтгүй бол None."""
    for i in range(attempts):
        try:
            res = session.get(url, timeout=timeout)
            if res.status_code == 200:
                return res.text
            if res.status_code == 429:
                print(f"\n[Rate Limit] {label} — 30 сек хүлээж байна...")
                time.sleep(30)
            else:
                print(f"\n[{label}] HTTP {res.status_code}, оролдлого {i+1}/{attempts}")
                time.sleep(5)
        except Exception as e:
            print(f"\n[{label}] Оролдлого {i+1}/{attempts} амжилтгүй: {e}")
            time.sleep(8)
    return None