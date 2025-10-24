import tkinter as tk
import os
from tkinter import scrolledtext, filedialog, messagebox
from PIL import Image, ImageTk
import openai_client
import fitz

class HomePage(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True)  
        tk.Label(self, text="Home", anchor="w").pack(pady=5, padx=10, anchor="w")
        tk.Label(self, text="Welcome to Syllearn", font=("Helvetica", 24)).pack(pady=20) 
        tk.Button(self, text="Upload Syllabus", command=self.ExtractPDF).pack(pady=10)
    
    def ExtractPDF(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("Image files", "*.png;*.jpg;*.jpeg")])
        global SyllabusText
        if file_path:
            try:
                text = ""
                for page in fitz.open(file_path):
                    text += page.get_text()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to extract text: {e}")
        SearchText = "The following is the syllabus of a student's course. Please extract the beginning and ending to the syllabus ONLY. Do not return anything else. This is due to some syllabuses having additional information. Syllabus:" + text
        SyllabusText = openai_client.OpenAIClient().Request(SearchText) 
            
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Syllearn")
        self.geometry("800x1000")
        self.home_page = HomePage(self)  
        
    
if __name__ == "__main__":
    app = App()
    app.mainloop()

