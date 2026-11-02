import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

# Бүх source-д нийтлэг тохиргоо
CLOSE_RATIO_LIMIT = 0.20    # нэг scan-д хаагдаж болох дээд хувь
MIN_COVERAGE = 0.90 
CLOSE_MIN_ABS = 25   # үүнээс цөөн зар хаагдвал харьцааны хамгаалалт ажиллахгүй        # scan-ыг "бүрэн" гэж үзэх доод хамралт