import random
import requests
import time

SLANG_MAP = {
    "company": "stonk",
    "increase": "pump",
    "decrease": "dump",
    "good": "lit",
    "bad": "trash",
    "profit": "bag",
    "loss": "rekt"
}

ABBREVIATIONS = {
    "you": "u",
    "are": "r",
    "for": "4",
    "to": "2"
}

NOISE = ["🚀", "😂", "💀", "!!!", "$$$"]

API_URL = "http://localhost:8000/predict"

def inject_slang(text: str) -> str:
    words = text.split()
    return " ".join([SLANG_MAP.get(w.lower(), w) for w in words])

def inject_abbreviations(text: str) -> str:
    words = text.split()
    return " ".join([ABBREVIATIONS.get(w.lower(), w) for w in words])

def inject_noise(text: str) -> str:
    if random.random() < 0.5:
        return text + " " + random.choice(NOISE)
    return text
    

def distort_text(text: str) -> str:
    text = inject_slang(text)
    text = inject_abbreviations(text)
    text = inject_noise(text)

    return text

def send_request(text: str):
    response = requests.post(API_URL, json={"text": [text]})
    return response.json()

def simulate_drift(texts):
    results = []

    for text in texts:
        drifted = distort_text(text)

        print(f"Original text: {text}")
        print(f"Drifted: {drifted}")

        res = send_request(drifted)

        results.append(res)

    return results


if __name__ == '__main__':
    texts = ["The company reported strong quarterly earnings",
        "Revenue increased by 12 percent year over year",
        "The firm announced a dividend payout for shareholders",
        "Operating margins improved due to cost optimization",
        "The stock showed steady growth over the past quarter",
        "Management expects moderate growth in the next fiscal year",
        "The company reduced its debt significantly",
        "Earnings per share exceeded analyst expectations",
        "The firm is expanding into new international markets",
        "The quarterly results indicate stable financial performance",
        "The company maintains a strong balance sheet",
        "Investor confidence remains high for this sector",
        "The firm reported consistent revenue growth",
        "The business outlook remains positive for the coming year",
        "The company announced a strategic acquisition",
        "The organization is focusing on long-term profitability",
        "Cash flow from operations remains strong",
        "The company continues to invest in research and development",
        "The firm has a stable earnings trajectory",
        "The industry outlook remains favorable"
    ]
    simulate_drift(texts)
