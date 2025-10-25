import tkinter as tk
import os
from tkinter import scrolledtext, filedialog, messagebox
from PIL import Image, ImageTk
import openai_client
import fitz
import threading

class HomePage(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True)  
        tk.Label(self, text="Home", anchor="w").pack(pady=5, padx=10, anchor="w")
        tk.Label(self, text="Welcome to Syllearn", font=("Helvetica", 24)).pack(pady=20) 
        tk.Button(self, text="Upload Syllabus", command=self.ExtractPDF).pack(pady=10)      
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=30)
        self.text_area.pack(pady=10)
        self.text_area.config(state="disabled")
        
    def ShowLoadingWindow(self):
        self.loading_window = tk.Toplevel(self)
        self.loading_window.title("Processing")
        self.loading_window.geometry("200x100")
        self.loading_window.transient(self)
        self.loading_window.grab_set()
        
        label = tk.Label(self.loading_window, text="Processing syllabus...\nPlease wait.", pady=20)
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
        SyllasbusText = openai_client.OpenAIClient().Request(prompt)
        self.master.after(0, self.UpdateTextArea, SyllasbusText)
        self.master.after(0, self.closeLoadingWindow)
    
    def ExtractPDF(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("Image files", "*.png;*.jpg;*.jpeg")])
        if file_path:
            try:
                text = ""
                for page in fitz.open(file_path):
                    text += page.get_text()
                self.ShowLoadingWindow()
                
                thread = threading.Thread(target=self.ProcessSyllabus, args=(text,))
                thread.daemon = True
                thread.start()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to extract text: {e}")
        
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Syllearn")
        self.geometry("800x1000")
        self.home_page = HomePage(self)  
        
    
if __name__ == "__main__":
    app = App()
    app.mainloop()

