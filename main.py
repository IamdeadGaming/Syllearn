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

global text
global Syllabuses
Syllabuses = []
APP_NAME = "Syllearn"
APP_AUTHOR = "GA Studios"
cSI = 0 #Current Syllabus Index

class Syllabus:
    def __init__(self, OriginalText):
        self.OriginalText = OriginalText
        self.content = ""
        self.title = ""
        self.JSONContent = {}               

class LearningPage(tk.Frame):
    def __init__(self,master,isExplanation: bool, j, text: str):
        super().__init__(master)
        tk.Label(self, text="Learning Page").pack()
        if isExplanation:
            video_path = videogenerator.create_video(j, text)
            if video_path and os.path.exists(video_path):
                self.video_label = tk.Label(self)
                self.video_label.pack(pady=10)
                self.cap = cv2.VideoCapture(video_path)
                self.playing = False
                self.current_frame = 0
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.delay = int(1000 / self.fps) if self.fps > 0 else 33
                self.play_button = tk.Button(self, text="Play", command=self.toggle_play)
                self.play_button.pack(pady=5)
                self.update_frame()
            else:
                tk.Label(self, text="Video generation failed or file not found.").pack(pady=10)
            tk.Label(self, text="Explanation:").pack(pady=5)
            explanation_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=30)
            explanation_area.pack(pady=10)
            explanation_area.insert(tk.END, text)
            explanation_area.config(state="disabled")
        else:
            tk.Label(self, text="Question:").pack(pady=5)
            question_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=10)
            question_area.pack(pady=10)
            question_area.insert(tk.END, text["question"])
            question_area.config(state="disabled")

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
    def __init__(self,master, i):
        super().__init__(master)
        for j in i["subchapters"]:
            tk.Button(self, text=j["title"], command=lambda subchapter=j: self.master.show_learning_page(subchapter)).pack(pady=2)

class SyllabusPage(tk.Frame):
    def __init__(self,master):
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
        prompt = f"The following is the syllabus of a student's course. Imagine you are a teacher trying to figure out what to teach students. Please extract the actual content of the syllabus ONLY. This means you do not have to mention exactly what part of the syllabus it is, no need how the assesment works, etc.. No need overview or anything. Just pure content. For example: 1. Topic x [enter] - SUBTOPIC WITH SMALL EXPLANATION [enter] - SUBTOPIC WITH SMALL EXPLANATION and so on This means removing redundant information. Do not return anything else. This is due to some syllabuses having additional information. Please return full content of the actual syllabus though. No removing information from the syllabus. Every bullet point. ADD A HEADER FIRST THINGS FIRST REPRESENTING THE NAME OF THE SYLLABUS AND THE SUBJECT. GIVE 2 ENTER SPACES AFTER THAT. Syllabus:\n\n{text}"
        SyllasbusText = openai_client.Request(prompt)
        Syllabuses[cSI].content = SyllasbusText
        self.master.after(0, self.UpdateTextArea, SyllasbusText)
        self.master.after(0, self.closeLoadingWindow)
    
    def ReanalyzeSyllabus(self):
        self.ShowLoadingWindow("Reanalyzing Syllabus")
        Syllabuses[cSI].content = ""
        thread = threading.Thread(target=self.ProcessSyllabus, args=(self.CurrentText,))
        thread.daemon = True
        thread.start()
    
    def ExtractPDF(self):
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
                
    def SaveSyllabusAsJSON(self, SyllabusJSON, SyllabusTitle):
        filename = f"{SyllabusTitle}.json"
        directory = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(SyllabusJSON, f, ensure_ascii=False, indent=4)
            Syllabuses[cSI].JSONContent = SyllabusJSON
        tk.Button(self, text=Syllabuses[-1].title, command=lambda idx=cSI: self.master.show_syllabus_page(idx)).pack(pady=5, padx=10, anchor="w")
            
    def StartParseSyllabus(self):
        self.ShowLoadingWindow("Parsing Syllabus to JSON")
        thread = threading.Thread(target=self.ParseSyllabus)
        thread.daemon = True
        thread.start()

    def ParseSyllabus(self):
        prompt = """You are a curriculum planner. Parse the following SYLLABUS_TEXT into structured JSON using this format. Do not deviate from the format or add additional explanation. ONLY RETURN VALID JSON in the exact format specified below:

{
  "syllabus_title": "<the syllabus title>",
  "chapters": [
    {
      "id": "<syllabus_title + '_chapter_' + number>",
      "title": "<chapter title>",
      "subchapters": [
        {
          "title": "<subchapter title>",
          "bullets": ["<key idea 1>", "<key idea 2>", "<key idea 3>"],
          "raw_text": "<original subchapter text>"
        }
      ],
      "raw_text": "<original chapter text>"
    }
  ]
}

Rules:
- Each chapter groups related syllabus concepts together.
- Each chapter should have 2–6 subchapters.
- Each subchapter should have 3–6 bullet points.
- Output only valid JSON. Do NOT include markdown or commentary.
- Keep JSON keys lowercase and consistent.
- Use clear, concise titles.

Now, here is the syllabus text to structure:
"""


        prompt = prompt + Syllabuses[cSI].content
        ParsedSyllabus = openai_client.Request(prompt)
        try:
            ParsedSyllabusJSON = json.loads(ParsedSyllabus)
        except Exception:
            m = re.search(r'(\{.*\})', ParsedSyllabus, flags=re.S)
            if not m:
                self.master.after(0, self.closeLoadingWindow)
                raise RuntimeError("LLM did not produce valid JSON output:\n" + ParsedSyllabus[:500])
            ParsedSyllabusJSON = json.loads(m.group(1))

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
            
        Syllabuses[cSI].title = re.sub(r'[<>:"/\\|?*]', '_', title)[:120]  
        self.SaveSyllabusAsJSON(ParsedSyllabusJSON, Syllabuses[cSI].title)
        
                   
        
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Syllearn")
        self.geometry("800x1000")
        self.pages = {}
        self.home_page = HomePage(self)
        self.pages['home'] = self.home_page
        self.current_page = self.home_page
        for filename in Path(user_data_dir(APP_NAME, APP_AUTHOR)).glob("*.json"):
            syllabus = json.load(open(filename, "r", encoding="utf-8"))
            Syllabuses.append(Syllabus(OriginalText=""))
            Syllabuses[-1].JSONContent = syllabus
            Syllabuses[-1].title = syllabus["syllabus_title"]
            cSI = len(Syllabuses) - 1
            tk.Button(self.home_page, text=Syllabuses[cSI].title, command=lambda idx=cSI: self.show_syllabus_page(idx)).pack(pady=5, padx=10, anchor="w")
            
        
    def show_syllabus_page(self, idx):
        global cSI
        cSI = idx
        syllabus_id = Syllabuses[cSI].title
        if f'syllabus_{syllabus_id}_{cSI}' not in self.pages:
            syllabus_page = SyllabusPage(self)
            tk.Button(syllabus_page,
                     text="Back to Home",
                     command=lambda: self.return_to_home()).pack(pady=5, anchor="w", padx=10)
            self.pages[f'syllabus_{syllabus_id}_{cSI}'] = syllabus_page
        self.current_page.pack_forget()
        self.pages[f'syllabus_{syllabus_id}_{cSI}'].pack(fill="both", expand=True)
        self.current_page = self.pages[f'syllabus_{syllabus_id}_{cSI}']

    def show_section_page(self, i):
        section_id = i["title"]
        if f'section_{section_id}_{cSI}' not in self.pages:
            section_page = SectionPage(self, i)
            tk.Button(section_page, text="Back to Home", command=lambda: self.return_to_home()).pack(pady=5, anchor="w", padx=10)
            self.pages[f'section_{section_id}_{cSI}'] = section_page
        self.current_page.pack_forget()
        self.pages[f'section_{section_id}_{cSI}'].pack(fill="both", expand=True)
        self.current_page = self.pages[f'section_{section_id}_{cSI}']
        
    def show_learning_page(self, j):
        learn_id = j["title"]
        for k in j["bullets"]:
            if f'section_{k}_{cSI}' not in self.pages:
                learn_id = k
                text = openai_client.Request(f"Based on the following syllabus content, provide a detailed explanation for it, including its ins and outs. ONLY RETURN THE EXPLANATION NOTHING ELSE: {k}")
                learn_page = LearningPage(self, True, k, text)
                self.pages[f'learn_{k}_explanation_{cSI}'] = learn_page
                number_questions = int(openai_client.Request(f"Based on the following syllabus content, generate a number between 3 and 6 representing how many questions can be made from it. Only return THE NUMBER ONLY. NO ADDITIONALS: {k}"))
                for _ in range(number_questions):
                    response = openai_client.Request(f"""Based on the following syllabus content, generate a (ONE) question that tests understanding of it: {k}
Use the following format and return a JSON object ONLY nothing else:
{{
  "question": "<the question text>",
  "options": ["<option 1>", "<option 2>", "<option 3>", "<option 4>"],
  "answer": "<the correct option>"
}}""")
                    try:
                        text = json.loads(response)
                    except Exception:
                        m = re.search(r'(\{.*\})', response, flags=re.S)
                        if not m:
                            print(f"LLM did not produce valid JSON for question {_}: {response[:500]}")
                            continue
                        text = json.loads(m.group(1))
                    questions_page = LearningPage(self, False, k, text)
                    self.pages[f'learn_{k}_question_{_}_{cSI}'] = questions_page
                break
            else:
                continue
        tk.Button(learn_page, text="Back to Home", command=lambda: self.return_to_home()).pack(pady=5, anchor="w", padx=10)
        self.pages[f'learn_{learn_id}_{cSI}'] = learn_page
        self.current_page.pack_forget()
        self.pages[f'learn_{learn_id}_{cSI}'].pack(fill="both", expand=True)
        self.current_page = self.pages[f'learn_{learn_id}_{cSI}']

    def return_to_home(self):
        self.current_page.pack_forget()
        self.home_page.pack(fill="both", expand=True)
        self.current_page = self.home_page

    
if __name__ == "__main__":
    app = App()
    app.mainloop()

