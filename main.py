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
        else:
            messagebox.showinfo("Result", f"Incorrect! The correct answer was option {correct_answer}.")

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
        self.video_path = videogenerator.create_video(j, text)
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
            tk.Label(self, text="Video generation failed or file not found.").pack(pady=10)
        
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
        tk.Label(self, text=f"Chapter: {i['title']}", font=("Helvetica", 16)).pack(pady=10)
        for j in i["subchapters"]:
            tk.Button(self, text=j["title"], command=lambda subchapter=j: self.master.show_learning_page(subchapter["bullets"][0])).pack(pady=2)
    

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
        SyllasbusText = openai_client.Request(prompt)
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
        ParsedSyllabus = openai_client.Request(prompt)
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
        for filename in Path(user_data_dir(APP_NAME, APP_AUTHOR)).glob("*.json"):
            syllabus = json.load(open(filename, "r", encoding="utf-8"))
            Syllabuses.append(Syllabus(OriginalText=""))
            Syllabuses[-1].JSONContent = syllabus
            Syllabuses[-1].title = syllabus["syllabus_title"]
            cSI = len(Syllabuses) - 1
            tk.Button(self.home_page, text=Syllabuses[cSI].title, command=lambda idx=cSI: self.show_syllabus_page(idx)).pack(pady=5, padx=10, anchor="w")
        
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
                            text = openai_client.Request(f"Based on the following syllabus content, provide a detailed explanation for it, including its ins and outs. ONLY RETURN THE EXPLANATION NOTHING ELSE: {lid}")
                            # Save
                            bul["explanation"] = text
                            self.save_current_syllabus()
                        
                        learn_page = LearningPage(self, True, lid, text, sc)
                        self.pages[f'learn_{lid}_explanation_{cSI}'] = learn_page
                        print(f"Preloaded learning page: {lid}")

                    thread = threading.Thread(target=load_learning_page, daemon=True)
                    thread.start()

    def preload_question_pages(self, subchapters):
        global cSI
        for subchapter in subchapters:
            for bullet in subchapter.get("bullets", []):
                learn_id = bullet["content"]
       
                num_questions_prompt = f"How many practice questions should be generated to test understanding of this topic? Reply with ONLY a single integer between 1 and 5: {learn_id}"
                try:
                    num_questions_str = openai_client.Request(num_questions_prompt).strip()
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
                                question_response = openai_client.Request(question_prompt)
                                question_data = json.loads(question_response)
                                question_page = QuestionPage(self, lid, question_data, q_idx, total_q)
                                self.pages[f"learn_{lid}_question_{q_idx}_{cSI}"] = question_page
                                print(f"Preloaded question {q_idx + 1}/{total_q} for: {lid}")
                            except Exception as e:
                                print(f"Failed to preload question {q_idx + 1} for {lid}: {e}")
                        
                        thread = threading.Thread(target=load_question_page, daemon=True)
                        thread.start()

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
            # Find the bullet containing this content
            bullet = None
            subchapter = None
            for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
                for sc in chapter.get("subchapters", []):
                    for bul in sc.get("bullets", []):
                        if bul["content"] == lid:
                            bullet = bul
                            subchapter = sc
                            break
        
            if not bullet:
                print(f"Bullet not found for: {lid}")
                return

            # Check if questions already cached in the bullet
            if "questions" in bullet and bullet["questions"]:
                print(f"Loading {len(bullet['questions'])} questions from cache for: {lid}")
                for q_idx, question_data in enumerate(bullet["questions"]):
                    key = f"learn_{lid}_question_{q_idx}_{cSI}"
                    if key not in self.pages:
                        question_page = QuestionPage(self, lid, question_data, q_idx, len(bullet["questions"]))
                        self.pages[key] = question_page
                return

            # Generate new questions if not cached
            num_questions_prompt = f"How many practice questions should be generated to test understanding of this topic? Reply with ONLY a single integer between 1 and 5: {lid}"
            try:
                num_questions_str = openai_client.Request(num_questions_prompt).strip()
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
            questions_completed = [False]  # Use list to allow modification in nested function

            for qnum in range(num_questions):
                key = f"learn_{lid}_question_{qnum}_{cSI}"
                
                if key not in self.pages:
                    def load_question_page(q_idx=qnum, total_q=num_questions):
                        question_prompt = f"Create a multiple choice question about: {lid}\n\nReturn ONLY valid JSON:\n{{\n  \"question\": \"Question text here?\",\n  \"options\": [\"A\", \"B\", \"C\", \"D\"],\n  \"answer\": \"1\"\n}}"
                        try:
                            question_response = openai_client.Request(question_prompt)
                            
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
        directory = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(Syllabuses[cSI].JSONContent, f, ensure_ascii=False, indent=4)
            print(f"Saved syllabus cache: {path}")
        except Exception as e:
            print(f"Failed to save syllabus: {e}")
    
if __name__ == "__main__":
    app = App()
    app.mainloop()