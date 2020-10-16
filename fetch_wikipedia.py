import logging
import numpy as np
import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format='{asctime} {message}', style='{')

BASE_URL = "https://en.wikipedia.org/wiki/"
lists = [
"List of Medieval composers",
"List of Renaissance composers",
"List of Baroque composers",
"List of Classical-era composers",
"List of Romantic-era composers",
"List of 20th-century classical composers",
"List of 21st-century classical composers",]
era = {
 "Medieval",
 "Renaissance",
 "Baroque",
 "Classical-era",
 "Romantic-era",
 "20th-century classical",
 "21st-century classical",}

def fetch_composer_list(list: str) -> pd.DataFrame:
    df = pd.read_html(f"{BASE_URL}/{list}")[0]
    return df

