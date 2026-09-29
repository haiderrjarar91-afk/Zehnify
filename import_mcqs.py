import glob
import json
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from ZehnifyApp.models import Chapter, MCQ

def run_import(json_file_path):
    if not os.path.exists(json_file_path):
        print(f"❌ Error: File '{json_file_path}' not found.")
        return

    if os.path.getsize(json_file_path) == 0:
        print(f"⚠️ Skipping '{os.path.basename(json_file_path)}': File is completely empty.")
        return

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error reading '{os.path.basename(json_file_path)}': Invalid JSON syntax ({e}).")
        return

    if not data:
        print(f"⚠️ Skipping '{os.path.basename(json_file_path)}': No questions inside JSON list.")
        return

    created_count = 0
    updated_count = 0

    for item in data:
        chapter_name = item.get('chapter_name') or item.get('chapter')
        
        if not chapter_name:
            print(f"⚠️ Skipping MCQ: Missing chapter identifier in item.")
            continue

        try:
            chapter = Chapter.objects.get(name__iexact=chapter_name)
        except Chapter.DoesNotExist:
            print(f"⚠️ Skipping MCQ: Chapter '{chapter_name}' does not exist.")
            continue

        # Extract options supporting both flat and nested JSON structures safely
        option_a = item.get('A') or item.get('a') or item.get('options', {}).get('A', '')
        option_b = item.get('B') or item.get('b') or item.get('options', {}).get('B', '')
        option_c = item.get('C') or item.get('c') or item.get('options', {}).get('C', '')
        option_d = item.get('D') or item.get('d') or item.get('options', {}).get('D', '')
        
        # Read correct option key (handles both correct_option and correct_answer)
        correct_opt = item.get('correct_option') or item.get('correct_answer') or item.get('answer') or 'A'

       # Store just the filename string safely
        raw_diagram = item.get('diagram_filename') or item.get('diagram') or item.get('image')
        if raw_diagram:
            diagram_path = os.path.basename(raw_diagram)
        else:
            diagram_path = None

        mcq, created = MCQ.objects.update_or_create(
            chapter=chapter,
            question_text=item['question_text'],
            defaults={
                'A': option_a,
                'B': option_b,
                'C': option_c,
                'D': option_d,
                'correct_option': correct_opt,
                'master_explanation': item.get('master_explanation', ''),
                'is_exam_question': item.get('is_exam_question', False),
                'diagram': diagram_path
            }
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    print(f"📁 Processed '{os.path.basename(json_file_path)}': ✅ {created_count} added | 🔄 {updated_count} updated")

if __name__ == '__main__':
    json_files = glob.glob('ZehnifyApp/fixtures/*.json')
    
    if not json_files:
        print("No JSON files found in ZehnifyApp/fixtures/")
    else:
        print(f"Found {len(json_files)} JSON file(s). Starting import...\n")
        for file_path in json_files:
            run_import(file_path)