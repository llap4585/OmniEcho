# -*- coding: utf-8 -*-
# @Author: llap4585
# @Project: OmniEcho
# @License: Apache-2.0
# @GitHub: https://github.com/llap4585/OmniEcho


import os
import re
import httpx
from dotenv import load_dotenv
from openai import OpenAI
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- OpenAI Grok API ---
load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
    timeout=httpx.Timeout(3600.0),
)


# (Display Name, Anchor Name / API Identifier)
LANGUAGES = [
    ("English", "english"),
    ("日本語", "japanese"),
    ("Deutsch", "deutsch"),
    ("Français", "francais"),
    ("Español", "espanol"),
         ("हिन्दी", "hindi"),
    ("한국어", "korean"),
    ("Português", "portuguese"),
    
    ("Arabic العربية", "arabic"),
    ("Bengali বাংলা", "bengali"),
    ("Russian русский", "russian"),
    ("Italian italiano", "italian"),
    ("Dutch Nederlands", "dutch"),
    ("Swedish svenska", "swedish")
]


def read_input_from_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Read failed {file_path}：{e}")
        return None

def save_output_to_txt(file_path, content):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Save failed {file_path}：{e}")

def process_task(input_path, output_dir, target_lang_name, anchor_name):
    """Process a single file translation task for one target language"""
    file_name = os.path.basename(input_path)
    lang_suffix = f"_{anchor_name}_output.md"
    output_path = os.path.join(output_dir, file_name.replace(".md", lang_suffix))

    content = read_input_from_txt(input_path)
    if not content: return False

    try:
        response = client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            messages=[
                {"role": "system", "content": f"""
你是一位专业的 Markdown 本地化专家。你的任务是将 Markdown 文档翻译成 {target_lang_name}。

严格准则：
1. 保持格式：严禁修改任何 Markdown 语法符号。
2. 代码块保护：不要翻译代码块（```）和行内代码中的内容。
3. 链接保护：翻译链接文本，但绝对不要修改 URL 地址。
4. 只输出正文：不含任何解释。
5. 特殊要求（能找到的话）：
   - 锚点同步：将开头类似 <a name="chinese"></a> 的锚点名修改为 <a name="{anchor_name}"></a>。
   - 标题对应：紧随其后的标题（如 #中文）翻译为对应语言（如 #{target_lang_name}）。
   禁止翻译按钮：类似于 [Requirements](#Requirements) 的格式为按钮，不得做任何处理和翻译，原样输出
"""},
                {"role": "user", "content": f"请将以下 Markdown 文本翻译为 {target_lang_name}：\n\n{content}"},
            ],
            temperature=0.1
        )
        result = response.choices[0].message.content
        save_output_to_txt(output_path, result)
        return True
    except Exception as e:
        print(f" Failed to translate to {target_lang_name} ({file_name}): {e}")
        return False

def auto_merge_multilingual_files(
    input_dir="output_grok_txt",
    raw_dir="readme",
    output_dir="merged_grok_txt",
    encoding="utf-8"
):
    trans_pattern = re.compile(r"^(?P<base>.+?)_part(?P<index>\d+)_(?P<lang>.+?)_output\.md$")
    raw_pattern = re.compile(r"^(?P<base>.+?)_part(?P<index>\d+)\.md$")

    grouped_files = defaultdict(list)

    
    if os.path.exists(input_dir):
        for f in os.listdir(input_dir):
            m = trans_pattern.match(f)
            if m:
                grouped_files[(m.group("base"), m.group("lang"))].append((int(m.group("index")), os.path.join(input_dir, f)))

# It collects the original Chinese chunk files and groups them by base name, preparing for sequential merging later.
    if os.path.exists(raw_dir):
        for f in os.listdir(raw_dir):
            m = raw_pattern.match(f)
            if m:
                grouped_files[(m.group("base"), "chinese")].append((int(m.group("index")), os.path.join(raw_dir, f)))

    if not grouped_files:
        print("No files found to merge.")
        return

    os.makedirs(output_dir, exist_ok=True)
    base_lang_map = defaultdict(dict)


    for (base_name, lang), files in grouped_files.items():
        files.sort(key=lambda x: x[0])
        full_text = ""
        for _, f_path in files:
            with open(f_path, "r", encoding=encoding) as f:
                content = f.read().strip()
                full_text += content + "\n"

        save_name = f"{base_name}_{lang}_merged.md"
        with open(os.path.join(output_dir, save_name), "w", encoding=encoding) as out:
            out.write(full_text)

        base_lang_map[base_name][lang] = full_text
        print(f"✅ Single-language version generated: {save_name}")

# Pass in the original language (here, Chinese)
    order = ["english", "chinese", "japanese", "deutsch", "francais", "espanol", "hindi", "korean", "portuguese"]

    for base_name, langs_dict in base_lang_map.items():
        final_readme_path = os.path.join(output_dir, f"FINAL_{base_name}_ALL.md")
        with open(final_readme_path, "w", encoding=encoding) as f_all:
            for lang_id in order:
                if lang_id in langs_dict:
                    f_all.write(langs_dict[lang_id])
                    f_all.write("\n")
        print(f"🎊 Final README generated: {final_readme_path}")


def main():
    input_dir = "readme"
    output_dir = "output_grok_txt"
    max_workers = 400   # Specifically check the maximum concurrency allowed by the API you are using

    os.makedirs(output_dir, exist_ok=True)
    files = [f for f in os.listdir(input_dir) if f.endswith(".md")]
    if not files:
        print("No .md files found")
        return

    tasks = []
    for f_name in files:
        input_path = os.path.join(input_dir, f_name)
        for lang_name, anchor in LANGUAGES:
            tasks.append((input_path, output_dir, lang_name, anchor))

    print(f" Starting to process {len(files)} files, with a total of {len(tasks)} translation tasks...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(process_task, t[0], t[1], t[2], t[3]): t for t in tasks}
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            success = future.result()
            print(f"Task {os.path.basename(task[0])} -> {task[2]} : {'Success' if success else 'Failed'}")


    auto_merge_multilingual_files()

    print("✅")

if __name__ == "__main__":
    main()
