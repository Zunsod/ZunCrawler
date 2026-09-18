import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Бүх source-д нийтлэг тохиргоо
CHUNK = 200                 # DB-д batch-аар бичих хэмжээ
CLOSE_RATIO_LIMIT = 0.20    # нэг scan-д хаагдаж болох дээд хувь
MIN_COVERAGE = 0.90 
CLOSE_MIN_ABS = 25   # үүнээс цөөн зар хаагдвал харьцааны хамгаалалт ажиллахгүй        # scan-ыг "бүрэн" гэж үзэх доод хамралт