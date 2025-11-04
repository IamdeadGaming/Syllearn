import tkinter as tk
import openai_client
import fitz
import threading
import json
import re
from pathlib import Path
from datetime import datetime
from platformdirs import user_data_dir
from tkinter import scrolledtext, filedialog, messagebox
from PIL import Image, ImageTk

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

class SectionPage(tk.Frame):
    def __init__(self,master):
        super().__init__(master)
        for i in Syllabus[cSI].JSONContent["chapters"]:
            for j in i["subchapters"]:
                tk.Button(self, text=j["title"], command=print("a")).pack(pady=2)

class SyllabusPage(tk.Frame):
    def __init__(self,master):
        super().__init__(master)
        for i in Syllabuses[cSI].JSONContent["chapters"]:
            tk.Button(self, text=i["title"], command=print("a")).pack(pady=5)

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
        for i in enumerate(Syllabuses):
            tk.Button(self, text=Syllabuses[i].title, command=print("a")).pack(pady=5, padx=10, anchor = "w")
        
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
        self.home_page = HomePage(self)  
        
    
if __name__ == "__main__":
    app = App()
    app.mainloop()

