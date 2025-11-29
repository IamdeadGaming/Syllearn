import tkinter as tk
import openai_client
import fitz
import threading
import json
import re
import os
from pathlib import Path
from datetime import datetime
from platformdirs import user_data_dir
from tkinter import scrolledtext, filedialog, messagebox
from PIL import Image, ImageTk
import videogenerator
import cv2
import time

mistake_pages = []
Syllabuses = []
APP_NAME = "Syllearn"
APP_AUTHOR = "GA Studios"
cSI = 0 #Current Syllabus Index
mistakes = {}  # Global mistakes dictionary

class Syllabus:
    def __init__(self, OriginalText):
        self.OriginalText = OriginalText
        self.content = ""
        self.title = ""
        self.JSONContent = {}    

class MistakesPage(tk.Frame):
    def __init__(self, master, question, qnum, totalq, chapter_title):
        super().__init__(master)
        self.master = master
        self.question = question
        self.qnum = qnum
        self.totalq = totalq
        self.chapter_title = chapter_title
        
        tk.Label(self, text=f"Mistake Review - Question {qnum + 1} of {totalq}").pack(pady=10)
        tk.Label(self, text="Question:").pack(pady=5)
        
        question_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=10)
        question_area.pack(pady=10)
        question_area.insert(tk.END, question.get("question", "No question text"))
        question_area.config(state="disabled")
        
        tk.Label(self, text="Options:").pack(pady=5)
        for i, option in enumerate(question.get("options", []), 1):
            tk.Button(self, text=f"{i}. {option}", command = lambda opt=i: self.check_answer(opt, question["answer"])).pack(anchor="w", padx=20)
        
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)
        
        if qnum > 0:
            tk.Button(button_frame, text="Previous Mistake", 
                     command=lambda: self.master.show_mistakes_page(chapter_title, qnum - 1)).pack(side="left", padx=5)
        
        tk.Button(button_frame, text="Back to Chapter", 
                 command=lambda: self.master.return_to_home()).pack(side="left", padx=5)
        
        if qnum < totalq - 1:
            tk.Button(button_frame, text="Next Mistake", 
                     command=lambda: self.master.show_mistakes_page(chapter_title, qnum + 1)).pack(side="right", padx=5)
    
    def check_answer(self, selected_option: int, correct_answer: str):
        try:
            correct_num = int(correct_answer)
        except (ValueError, TypeError):
            messagebox.showerror("Error", f"Invalid answer format: {correct_answer}")
            return
        
        if selected_option == correct_num:
            messagebox.showinfo("Result", "Correct!")
            self.remove_mistake()
        else:
            messagebox.showinfo("Result", f"Incorrect! The correct answer was option {correct_answer}.")

    def remove_mistake(self):
        mistakes[Syllabuses[cSI].title][self.chapter_title]["questions"].remove(self.question)
        mistakes[Syllabuses[cSI].title][self.chapter_title]["number"] -= 1
        
class QuestionPage(tk.Frame):
    def __init__(self, master, learn_id: str, text: str, qnum, totalq):
        super().__init__(master)
        self.learn_id = learn_id
        self.text = text
        tk.Label(self, text="Question Page").pack()
        tk.Label(self, text="Question:").pack(pady=5)
        question_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=10)
        question_area.pack(pady=10)
        question_area.insert(tk.END, text["question"])
        question_area.config(state="disabled")
        
        for i, option in enumerate(text["options"], 1):
            tk.Button(self, text=option, 
                     command=lambda opt=i: self.check_answer(opt, text["answer"])).pack(pady=5)
        
        tk.Button(self, text="Back to learning", 
                 command=lambda: self.master.show_learning_page({"content": learn_id})).pack(pady=5, anchor="se", padx=10)
        if qnum<totalq-1:
            tk.Button(self, text="Next Question", 
                     command=lambda: self.master.show_question_page({"content": learn_id}, qnum+1)).pack(pady=5, anchor="se", padx=10)
        
    def check_answer(self, selected_option: int, correct_answer: str):
        try:
            correct_num = int(correct_answer)
        except (ValueError, TypeError):
            messagebox.showerror("Error", f"Invalid answer format: {correct_answer}")
            return
        
        if selected_option == correct_num:
            messagebox.showinfo("Result", "Correct!")
            self.master.mark_bullet_reviewed(self.learn_id)
        else:
            messagebox.showinfo("Result", f"Incorrect! The correct answer was option {correct_answer}.")
            self.save_wrong_answer(self.text, self.learn_id)

    
    def save_wrong_answer(self, question, lid):
        global cSI
        global mistakes

        chapter_title = None
        for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
            for subchapter in chapter.get("subchapters", []):
                for bullet in subchapter.get("bullets", []):
                    if bullet['content'] == lid:
                        chapter_title = chapter["title"]
                        break
        
        if not chapter_title:
            print(f"Chapter not found for bullet: {lid}")
            return
        
        filename = f"{Syllabuses[cSI].title}_{chapter_title}_mistakes.json"
        directory = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / Syllabuses[cSI].title / chapter_title
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        
        self.master.create_mistakes_structure(Syllabuses[cSI].title, chapter_title)
        mistakes[Syllabuses[cSI].title][chapter_title]["number"] += 1
        mistakes[Syllabuses[cSI].title][chapter_title]["questions"].append(question)
        
        self.master.create_mistakes_page(chapter_title)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(mistakes[Syllabuses[cSI].title][chapter_title], f, ensure_ascii=False, indent=4)
            print(f"Saved wrong answer to: {path}")
        except Exception as e:
            print(f"Failed to save wrong answer: {e}")
    
class LearningPage(tk.Frame):
    def __init__(self, master, isExplanation: bool, topic, text: str, originaltext):
        self.video_path = None
        self.topic = topic
        self.question_num = 0
        super().__init__(master)
        tk.Label(self, text="Learning Page").pack()
        
        if isExplanation:
            self.video_label = tk.Label(self)
            self.video_label.pack(pady=10)

            self.play_button = tk.Button(self, text="Play", command=self.toggle_play, state="disabled")
            self.play_button.pack(pady=5)
     
            thread = threading.Thread(target=self.generate_video, args=(topic, text), daemon=True)
            thread.start()
            
            tk.Label(self, text="Explanation:").pack(pady=5)
            explanation_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=30)
            explanation_area.pack(pady=10)
            explanation_area.insert(tk.END, text)
            explanation_area.config(state="disabled")
            tk.Button(self, text="Go to questions", command=lambda: self.master.show_question_page({"content": topic}, 0)).pack(anchor="e", padx=10)

    def generate_video(self, j, text):
        chapter_title = None
        for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
            for subchapter in chapter.get("subchapters", []):
                for bullet in subchapter.get("bullets", []):
                    if bullet["explanation"] == text:
                        chapter_title = chapter["title"]
                        break
        self.video_path = videogenerator.create_video(j, text, Syllabuses[cSI], chapter_title)
        self.master.after(0, self.on_video_ready, self.video_path)
            
    def on_video_ready(self, video_path):
        if video_path and os.path.exists(video_path):
            self.cap = cv2.VideoCapture(video_path)
            self.playing = False
            self.current_frame = 0
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.delay = int(1000 / self.fps) if self.fps > 0 else 33
 
            self.play_button.config(state="normal")

            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img = img.resize((640, 360), Image.Resampling.LANCZOS)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.config(image=imgtk)
                self.current_frame = 1
        else:
            tk.Label(self, text="Video still generating.").pack(pady=10)
        
    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.config(text="Pause" if self.playing else "Play")
        if self.playing:
            self.update_frame()

    def update_frame(self):
        if self.playing and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img = img.resize((640, 360), Image.Resampling.LANCZOS)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.config(image=imgtk)
                self.current_frame += 1
                if self.current_frame < self.total_frames:
                    self.after(self.delay, self.update_frame)
                else:
                    self.playing = False
                    self.play_button.config(text="Play")
            else:
                self.playing = False
                self.play_button.config(text="Play")
            
class SectionPage(tk.Frame):
    def __init__(self, master, i):
        super().__init__(master)
        self.master = master
        self.chapter = i
        self.bullet_indices = {}
        tk.Label(self, text=f"Chapter: {i['title']}", font=("Helvetica", 16)).pack(pady=10)
        for j in i["subchapters"]:
            subchapter_title = j["title"]
            self.bullet_indices[subchapter_title] = 0
            
            bullets = j.get("bullets", [])
            reviewed_count = sum(1 for b in bullets if b.get("reviewed", False))
            button_text = f"{subchapter_title} ({reviewed_count}/{len(bullets)})"
            
            tk.Button(self, text=button_text, 
                     command=lambda subchapter=j: self.navigate_bullet(subchapter)).pack(pady=2)
        self.add_mistakes_button()
    
    def navigate_bullet(self, subchapter):
        subchapter_title = subchapter["title"]
        bullets = subchapter.get("bullets", [])
        
        if not bullets:
            messagebox.showwarning("Warning", "No bullets in this subchapter")
            return
        
        current_idx = self.bullet_indices[subchapter_title]
        self.master.show_learning_page(bullets[current_idx])
        
        self.bullet_indices[subchapter_title] = (current_idx + 1) % len(bullets)
        
    def add_mistakes_button(self):
        global cSI
        global mistakes
        tk.Button(self, text="Review Mistakes", command=lambda: self.master.show_mistakes_page(self.chapter["title"], 0)).pack(pady=5)  
        
class SyllabusPage(tk.Frame):
    def __init__(self,master):
        global cSI
        super().__init__(master)
        for i in Syllabuses[cSI].JSONContent["chapters"]:
            tk.Button(self, text=i["title"], command=lambda chapter=i: self.master.show_section_page(chapter)).pack(pady=5)

class HomePage(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True)
        self.current_text = ""
        tk.Label(self, text="Home", anchor="w").pack(pady=5, padx=10, anchor="w")
        tk.Label(self, text="Welcome to Syllearn", font=("Helvetica", 24)).pack(pady=20) 
        tk.Button(self, text="Upload Syllabus", command=self.ExtractPDF).pack(pady=10)      
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=30)
        self.text_area.pack(pady=10)
        self.text_area.config(state="disabled")
        tk.Button(self, text="Confirm syllabus content", command=self.StartParseSyllabus).pack(pady=5)
        tk.Button(self, text="Reanalyze syllabus content", command=self.ReanalyzeSyllabus).pack(pady=5)
             
    def ShowLoadingWindow(self, LoadingText):
        self.loading_window = tk.Toplevel(self)
        self.loading_window.title("Loading")
        self.loading_window.geometry("200x100")
        self.loading_window.transient(self)
        self.loading_window.grab_set()
        
        label = tk.Label(self.loading_window, text=f"{LoadingText}...\nPlease wait.", pady=20)
        label.pack()
        
    def closeLoadingWindow(self):
        if hasattr(self, 'loading_window'):
            self.loading_window.destroy()
        
    def UpdateTextArea(self, text):
        self.text_area.config(state="normal")
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, text)
        self.text_area.config(state="disabled")
        
    def ProcessSyllabus(self, text):
        global cSI
        prompt = f"The following is the syllabus of a student's course. Imagine you are a teacher trying to figure out what to teach students. Please extract the actual content of the syllabus ONLY. This means you do not have to mention exactly what part of the syllabus it is, no need how the assesment works, etc.. No need overview or anything. Just pure content. For example: 1. Topic x [enter] - SUBTOPIC WITH SMALL EXPLANATION [enter] - SUBTOPIC WITH SMALL EXPLANATION and so on This means removing redundant information. Do not return anything else. This is due to some syllabuses having additional information. Please return full content of the actual syllabus though. No removing information from the syllabus. Every bullet point. ADD A HEADER FIRST THINGS FIRST REPRESENTING THE NAME OF THE SYLLABUS AND THE SUBJECT. GIVE 2 ENTER SPACES AFTER THAT. Syllabus:\n\n{text}"
        SyllasbusText = openai_client.Request(prompt, model="gpt-4o")
        Syllabuses[cSI].content = SyllasbusText
        self.master.after(0, self.UpdateTextArea, SyllasbusText)
        self.master.after(0, self.closeLoadingWindow)
    
    def ReanalyzeSyllabus(self):
        global cSI
        self.ShowLoadingWindow("Reanalyzing Syllabus")
        Syllabuses[cSI].content = ""
        thread = threading.Thread(target=self.ProcessSyllabus, args=(self.CurrentText,))
        thread.daemon = True
        thread.start()
    
    def ExtractPDF(self):
        global cSI
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("Image files", "*.png;*.jpg;*.jpeg")])
        if file_path:
            try:
                Syllabuses.append(Syllabus(OriginalText=""))
                cSI = len(Syllabuses) - 1
                for page in fitz.open(file_path):
                    Syllabuses[cSI].OriginalText += page.get_text()
                self.CurrentText = Syllabuses[cSI].OriginalText
                self.ShowLoadingWindow("Processing Syllabus")
                
                thread = threading.Thread(target=self.ProcessSyllabus, args=(Syllabuses[cSI].OriginalText,))
                thread.daemon = True
                thread.start()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to extract text: {e}")
            
    def StartParseSyllabus(self):
        self.ShowLoadingWindow("Parsing Syllabus to JSON")
        thread = threading.Thread(target=self.ParseSyllabus)
        thread.daemon = True
        thread.start()

    def ParseSyllabus(self):
        global cSI
        prompt = """You are a curriculum planner. Parse the following SYLLABUS_TEXT into structured JSON using this format. Do not deviate from the format or add additional explanation. If there are less than a reasonable amount of chapters like less than 3 or something like that, assume the chapter doesnt exist and instead set the chapter as the subchapter (shifted). This is to prevent lag and rate limits being reached. ONLY RETURN VALID JSON in the exact format specified below:

{
  "syllabus_title": "<the syllabus title>",
  "chapters": [
    {
      "id": "<syllabus_title + '_chapter_' + number>",
      "title": "<chapter title>",
      "subchapters": [
        {
          "title": "<subchapter title>",
          "bullets": [{"content": "<key idea 1>"}, {"content": "<key idea 2>"}, {"content": "<key idea 3>"}],
          "raw_text": "<original subchapter text>"
        }
      ],
      "raw_text": "<original chapter text>"
    }
  ]
}

Rules:
- Each chapter groups related syllabus concepts together.
- Each chapter should have as many as needed subchapters.
- Each subchapter should have as many as needed bullet points.
- Output only valid JSON. Do NOT include markdown or commentary.
- Keep JSON keys lowercase and consistent.
- Use clear, concise titles.
- Make sure to include all relevant content from the syllabus, preparing an A* student for an exam.
Now, here is the syllabus text to structure:
"""

        prompt = prompt + Syllabuses[cSI].content
        ParsedSyllabus = openai_client.Request(prompt, model="gpt-4o")
        try:
            ParsedSyllabusJSON = json.loads(ParsedSyllabus)
        except Exception:
            m = re.search(r'(\{.*\})', ParsedSyllabus, flags=re.S)
            if not m:
                self.master.after(0, self.closeLoadingWindow)
                raise RuntimeError("LLM did not produce valid JSON output:\n" + ParsedSyllabus[:500])
            ParsedSyllabusJSON = json.loads(m.group(1))

        for chapter in ParsedSyllabusJSON.get("chapters", []):
            for subchapter in chapter.get("subchapters", []):
                for bullet in subchapter.get("bullets", []):
                    if "explanation" not in bullet:
                        bullet["explanation"] = None
                    if "questions" not in bullet:
                        bullet["questions"] = None
                    if "reviewed" not in bullet:  
                        bullet["reviewed"] = False

        self.master.after(0, self.closeLoadingWindow)

        title = None
        lines = Syllabuses[cSI].content.splitlines()
        if lines:
            title = lines[0].strip()
            if not title:  
                for line in lines:
                    if line.strip():
                        title = line.strip()
                        break
    
        if not title:
            title = datetime.now().strftime("syllabus_%Y%m%d_%H%M%S")

        if title.startswith("###"):
            title = title[3:].strip()
        Syllabuses[cSI].title = re.sub(r'[<>:"/\\|?*#]', '_', title)[:120]  
        Syllabuses[cSI].JSONContent = ParsedSyllabusJSON
        tk.Button(self, text=Syllabuses[cSI].title, 
            command=lambda i=cSI: self.master.show_syllabus_page(i)).pack(pady=5, padx=10, anchor="w")
        self.master.save_current_syllabus()
        
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global cSI
        self.title("Syllearn")
        self.geometry("880x1080")
        tk.Button(self,
                     text="Back to Home",
                     command=lambda: self.return_to_home()).pack(pady=5, anchor="w", padx=10)
        self.pages = {}
        self.home_page = HomePage(self)
        self.pages['home'] = self.home_page
        self.current_page = self.home_page

        base_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        if base_dir.exists():
            for syllabus_folder in base_dir.iterdir():
                if syllabus_folder.is_dir():
                    json_files = list(syllabus_folder.glob("*.json"))
                    if json_files:
                        for json_file in json_files:                   
                            try:
                                with open(json_file, "r", encoding="utf-8") as f:
                                    syllabus_data = json.load(f)
                                Syllabuses.append(Syllabus(OriginalText=""))
                                Syllabuses[-1].JSONContent = syllabus_data
                                Syllabuses[-1].title = syllabus_data.get("syllabus_title", syllabus_folder.name)

                                idx = len(Syllabuses) - 1
                                tk.Button(self.home_page, text=Syllabuses[idx].title, 
                                    command=lambda i=idx: self.show_syllabus_page(i)).pack(pady=5, padx=10, anchor="w")
                            except Exception as e:
                                print(f"Failed to load syllabus from {json_file}: {e}")
                    for chapter_folder in syllabus_folder.iterdir():
                        json_files = list(chapter_folder.glob("*.json"))
                        if json_files:
                            for json_file in json_files:
                                if os.path.basename(syllabus_folder) not in mistakes:
                                    self.create_mistakes_structure(os.path.basename(syllabus_folder), os.path.basename(chapter_folder))
                                    mistakes[os.path.basename(syllabus_folder)][os.path.basename(chapter_folder)]["question"] = json.load(open(json_file, "r", encoding="utf-8"))
                                    mistakes[os.path.basename(syllabus_folder)][os.path.basename(chapter_folder)]["number"] = len(mistakes[os.path.basename(syllabus_folder)][os.path.basename(chapter_folder)]["question"])    
                            self.create_mistakes_page(os.path.basename(chapter_folder))
                            
    def preload_learning_pages(self, subchapters):
        global cSI
        for subchapter in subchapters:
            for bullet in subchapter.get("bullets", []):
                learn_id = bullet["content"]
                key = f'learn_{learn_id}_explanation_{cSI}'

                if key not in self.pages:
                    def load_learning_page(lid=learn_id, sc=subchapter, bul=bullet):
                        if "explanation" in bul and bul["explanation"]:
                            text = bul["explanation"]
                            print(f"Loaded explanation from cache: {lid}")
                        else:
                            text = openai_client.Request(f"Based on the following syllabus content, provide a detailed explanation for it, including its ins and outs. ONLY RETURN THE EXPLANATION NOTHING ELSE: {lid}", model="gpt-4o-mini")
                            # Save
                            bul["explanation"] = text
                            self.save_current_syllabus()
                        
                        learn_page = LearningPage(self, True, lid, text, sc)
                        self.pages[f'learn_{lid}_explanation_{cSI}'] = learn_page
                        print(f"Preloaded learning page: {lid}")

                    thread = threading.Thread(target=load_learning_page, daemon=True)
                    thread.start()
                time.sleep(0.3)
            time.sleep(10)

    def preload_question_pages(self, subchapters):
        global cSI
        for subchapter in subchapters:
            for bullet in subchapter.get("bullets", []):
                learn_id = bullet["content"]
       
                num_questions_prompt = f"How many practice questions should be generated to test understanding of this topic? Reply with ONLY a single integer between 1 and 5: {learn_id}"
                try:
                    num_questions_str = openai_client.Request(num_questions_prompt, model="gpt-4o-mini").strip()
                    num_questions = int(num_questions_str)
                    num_questions = max(1, min(5, num_questions)) 
                except Exception as e:
                    print(f"Failed to determine question count for {learn_id}: {e}")
                    num_questions = 3  

                for qnum in range(num_questions):
                    key = f"learn_{learn_id}_question_{qnum}_{cSI}"
                    
                    if key not in self.pages:
                        def load_question_page(lid=learn_id, q_idx=qnum, total_q=num_questions):
                            question_prompt = f"Based on the following syllabus content, generate question {q_idx + 1} of {total_q} that tests understanding of it. Return a JSON object ONLY:\n{{\n  \"question\": \"<the question text>\",\n  \"options\": [\"<option 1>\", \"<option 2>\", \"<option 3>\", \"<option 4>\"],\n  \"answer\": \"<correct option number as string (1-4)>\"\n}}\nTopic: {lid}"
                            try:
                                question_response = openai_client.Request(question_prompt, model="gpt-4o-mini")
                                question_data = json.loads(question_response)
                                question_page = QuestionPage(self, lid, question_data, q_idx, total_q)
                                self.pages[f"learn_{lid}_question_{q_idx}_{cSI}"] = question_page
                                print(f"Preloaded question {q_idx + 1}/{total_q} for: {lid}")
                            except Exception as e:
                                print(f"Failed to preload question {q_idx + 1} for {lid}: {e}")
                        
                        thread = threading.Thread(target=load_question_page, daemon=True)
                        thread.start()
                    time.sleep(0.1)
                time.sleep(0.2)

    def show_syllabus_page(self, idx):
        global cSI
        cSI = idx
        syllabus_id = Syllabuses[cSI].title
        if f'syllabus_{syllabus_id}_{cSI}' not in self.pages:
            syllabus_page = SyllabusPage(self)
            self.pages[f'syllabus_{syllabus_id}_{cSI}'] = syllabus_page
        self.current_page.pack_forget()
        self.pages[f'syllabus_{syllabus_id}_{cSI}'].pack(fill="both", expand=True)
        self.current_page = self.pages[f'syllabus_{syllabus_id}_{cSI}']

    def show_section_page(self, i):
        global cSI
        section_id = i["title"]
        if f'section_{section_id}_{cSI}' not in self.pages:
            section_page = SectionPage(self, i)
            self.pages[f'section_{section_id}_{cSI}'] = section_page

            subchapters = i.get("subchapters", [])
            self.preload_learning_pages(subchapters)
            self.preload_question_pages(subchapters)
        
        self.current_page.pack_forget()
        self.pages[f'section_{section_id}_{cSI}'].pack(fill="both", expand=True)
        self.current_page = self.pages[f'section_{section_id}_{cSI}']
        
    def show_learning_page(self, bullet):
        global cSI
        learn_id = bullet["content"]
        key = f'learn_{learn_id}_explanation_{cSI}'

        import time
        timeout = time.time() + 60
        while key not in self.pages and time.time() < timeout:
            time.sleep(0.1)
        
        if key in self.pages:
            learn_page = self.pages[key]
            self.current_page.pack_forget()
            learn_page.pack(fill="both", expand=True)
            self.current_page = learn_page
            
            self.preload_questions_for_bullet(learn_id)
        else:
            messagebox.showerror("Error", f"Learning page still loading for: {learn_id}")
            
    def create_mistakes_page(self, chapter_title):
        global mistake_pages
        for question in mistakes[Syllabuses[cSI].title][chapter_title]["questions"]:
            key = f'mistake_{Syllabuses[cSI].title}_{chapter_title}_question_{mistakes[Syllabuses[cSI].title][chapter_title]["questions"].index(question)}_{cSI}'
            if key not in self.pages:
                mistake_page = MistakesPage(self, question, mistakes[Syllabuses[cSI].title][chapter_title]["questions"].index(question), mistakes[Syllabuses[cSI].title][chapter_title]["number"], chapter_title)
                self.pages[key] = mistake_page    

    def show_mistakes_page(self, chapter_title, qnum):
        global cSI
        key = f'mistake_{Syllabuses[cSI].title}_{chapter_title}_question_{qnum}_{cSI}'
        if key in self.pages:
            mistake_page = self.pages[key]
            self.current_page.pack_forget()
            mistake_page.pack(fill="both", expand=True)
            self.current_page = mistake_page
        else:
            messagebox.showerror("Error", f"No mistakes found for chapter: {chapter_title}")             
    
    def show_question_page(self, bullet, qnum):
        global cSI
        learn_id = bullet["content"]
        key = f"learn_{learn_id}_question_{qnum}_{cSI}"
        
        import time
        timeout = time.time() + 60 
        while key not in self.pages and time.time() < timeout:
            time.sleep(0.1)
        
        if key in self.pages:
            learn_page = self.pages[key]
            self.current_page.pack_forget()
            learn_page.pack(fill="both", expand=True)
            self.current_page = learn_page
        else:
            messagebox.showerror("Error", f"Question page still loading for: {learn_id}")
            
    def return_to_home(self):
        self.current_page.pack_forget()
        self.home_page.pack(fill="both", expand=True)
        self.current_page = self.home_page

    
    def preload_questions_for_bullet(self, learn_id):
        global cSI

        if any(f"learn_{learn_id}_question_" in key for key in self.pages.keys()):
            return

        def load_questions_batch(lid=learn_id):
            bullet = None
            for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
                for sc in chapter.get("subchapters", []):
                    for bul in sc.get("bullets", []):
                        if bul["content"] == lid:
                            bullet = bul
                            break
        
            if not bullet:
                print(f"Bullet not found for: {lid}")
                return

            if "questions" in bullet and bullet["questions"]:
                print(f"Loading {len(bullet['questions'])} questions from cache for: {lid}")
                for q_idx, question_data in enumerate(bullet["questions"]):
                    key = f"learn_{lid}_question_{q_idx}_{cSI}"
                    if key not in self.pages:
                        question_page = QuestionPage(self, lid, question_data, q_idx, len(bullet["questions"]))
                        self.pages[key] = question_page
                return

            num_questions_prompt = f"How many practice questions should be generated to test understanding of this topic? Reply with ONLY a single integer between 1 and 5: {lid}"
            try:
                num_questions_str = openai_client.Request(num_questions_prompt, model="gpt-4o-mini").strip()
                if not num_questions_str:
                    print(f"Empty response for question count: {lid}")
                    num_questions = 3
                else:
                    num_questions = int(num_questions_str)
                    num_questions = max(1, min(5, num_questions))
                print(f"Generating {num_questions} questions for: {lid}")
            except Exception as e:
                print(f"Failed to determine question count for {lid}: {e}")
                num_questions = 3
            generated_questions = []

            for qnum in range(num_questions):
                key = f"learn_{lid}_question_{qnum}_{cSI}"
                
                if key not in self.pages:
                    def load_question_page(q_idx=qnum, total_q=num_questions):
                        question_prompt = f"Create a multiple choice question about: {lid}\n\nReturn ONLY valid JSON:\n{{\n  \"question\": \"Question text here?\",\n  \"options\": [\"A\", \"B\", \"C\", \"D\"],\n  \"answer\": \"1\"\n}}"
                        try:
                            question_response = openai_client.Request(question_prompt, model="gpt-4o-mini")
                            
                            if not question_response or question_response.strip() == "":
                                print(f"Empty response for question {q_idx + 1} for {lid}")
                                return
                            
                            print(f"Raw response for question {q_idx + 1}: {question_response[:100]}...")
                            
                            question_data = json.loads(question_response)
                            generated_questions.append(question_data)
                            
                            question_page = QuestionPage(self, lid, question_data, q_idx, total_q)
                            self.pages[f"learn_{lid}_question_{q_idx}_{cSI}"] = question_page
                            print(f"Successfully preloaded question {q_idx + 1}/{total_q} for: {lid}")
                        except json.JSONDecodeError as e:
                            print(f"JSON parse error for question {q_idx + 1} for {lid}: {e}")
                            print(f"Response was: {question_response[:200] if question_response else 'None'}")
                        except Exception as e:
                            print(f"Failed to preload question {q_idx + 1} for {lid}: {e}")
                
                thread = threading.Thread(target=load_question_page, daemon=True)
                thread.start()
                import time
                time.sleep(0.5)
    
        thread = threading.Thread(target=load_questions_batch, daemon=True)
        thread.start()
        
    def save_current_syllabus(self):
        global cSI
        filename = f"{Syllabuses[cSI].title}.json"
        directory = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / Syllabuses[cSI].title
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(Syllabuses[cSI].JSONContent, f, ensure_ascii=False, indent=4)
            print(f"Saved syllabus cache: {path}")
        except Exception as e:
            print(f"Failed to save syllabus: {e}")
    
    def mark_bullet_reviewed(self, learn_id):
        global cSI
        for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
            for subchapter in chapter.get("subchapters", []):
                for bullet in subchapter.get("bullets", []):
                    if bullet["content"] == learn_id:
                        bullet["reviewed"] = True
                        self.save_current_syllabus()
                        print(f"Marked as reviewed: {learn_id}")
                        return
    
    def create_mistakes_structure(self, syllabus_title, chapter):
        global mistakes
        if syllabus_title not in mistakes:
            mistakes[syllabus_title] = {}
        if chapter not in mistakes[syllabus_title]:
            mistakes[syllabus_title][chapter] = {"questions": [], "number": 0}
    
if __name__ == "__main__":
    app = App()
    app.mainloop()