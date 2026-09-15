import json
from pathlib import Path

FILE_PATH = Path("data/raw/zangia_jobs_selected.json")

def remove_duplicates():
    if not FILE_PATH.exists():
        print(f"[Алдаа] {FILE_PATH} файл олдсонгүй.")
        return

    print(f"Файлыг уншиж байна: {FILE_PATH}")
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    total_before = len(raw_data)
    
    # Давхардлыг шүүх logic
    seen_ids = set()
    cleaned_data = []

    for item in raw_data:
        job_id = item.get("job_id")
        
        # job_id давхардаагүй бол шинэ жагсаалтад нэмнэ
        if job_id not in seen_ids:
            seen_ids.add(job_id)
            cleaned_data.append(item)

    total_after = len(cleaned_data)
    duplicates_removed = total_before - total_after

    # Цэвэрлэсэн өгөгдлийг буцаагаад файлд дарж бичих
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print("------------------------------------------")
    print(f"Анх байсан нийт зар:        {total_before}")
    print(f"Устгагдсан давхардал:       {duplicates_removed}")
    print(f"Цэвэрлэгдсэн бодит зар:     {total_after}")
    print(f"Хадгалагдсан байршил:       {FILE_PATH}")
    print("------------------------------------------")

if __name__ == "__main__":
    remove_duplicates()