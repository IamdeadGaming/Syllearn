import tkinter as tk
import openai_client
import fitz
import threading
import json
import re
import os
import videogenerator
import cv2
import time
import pygame
from pathlib import Path
from datetime import datetime
from platformdirs import user_data_dir
from tkinter import scrolledtext, filedialog, messagebox
from PIL import Image, ImageTk

mistake_pages = []
Syllabuses = []
APP_NAME = "Syllearn"
APP_AUTHOR = "GA Studios"
cSI = 0 #Current Syllabus Index
mistakes = {}  # Global mistakes dictionary

def sanitize_path(text):
    # Remove/replace problematic characters
    text =  re.sub(r'[<>:"/\\|?*]', '_', text)[:120]
    # Remove leading/trailing spaces and dots
    text = text.strip('. ')
    # Limit length
    return text[:120]

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
            correct_answer = int(correct_answer) + 1
        except (ValueError, TypeError):
            if correct_answer in ["A", "B", "C", "D"]:
                correct_answer = ord(correct_answer.upper()) - ord('A') + 1
                
        if selected_option == correct_answer:
            messagebox.showinfo("Result", "Correct!")
            self.remove_mistake()
        else:
            messagebox.showinfo("Result", f"Incorrect! The correct answer was option {correct_answer}.")

    def remove_mistake(self):
        global cSI
        global mistakes
        safe_syllabus = sanitize_path(Syllabuses[cSI].title)
        safe_chapter = sanitize_path(self.chapter_title)
        
        print(f"Removing mistake from: {safe_syllabus}/{safe_chapter}")
        print(f"Current mistakes: {mistakes.get(safe_syllabus, {}).get(safe_chapter, {})}")
        
        if safe_syllabus in mistakes and safe_chapter in mistakes[safe_syllabus]:
            if self.question in mistakes[safe_syllabus][safe_chapter]["questions"]:
                mistakes[safe_syllabus][safe_chapter]["questions"].remove(self.question)
                mistakes[safe_syllabus][safe_chapter]["number"] -= 1
                
                filename = f"{safe_syllabus}_{safe_chapter}_mistakes.json"
                directory = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / safe_syllabus / safe_chapter
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / filename
                
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(mistakes[safe_syllabus][safe_chapter], f, ensure_ascii=False, indent=4)
                    print(f"Saved updated mistakes to: {path}")
                except Exception as e:
                    print(f"Failed to save updated mistakes: {e}")
                
                section_key = f'section_{safe_chapter}_{cSI}'
                if self.master.pages.get(section_key):
                    section_page = self.master.pages[section_key]
                    section_page.add_mistakes_button()
                    print("Updated section page mistakes button")
        
class QuestionPage(tk.Frame):
    def __init__(self, master, learn_id: str, text: str, qnum, totalq):
        super().__init__(master)
        self.learn_id = learn_id
        self.text = text if text else {"question": "Question not available", "options": [], "answer": "0"}
        self.qnum = qnum
        self.totalq = totalq
        
        tk.Label(self, text="Question Page").pack()
        tk.Label(self, text="Question:").pack(pady=5)
        
        question_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=10)
        question_area.pack(pady=10)
        question_area.insert(tk.END, self.text.get("question", "Question content not available"))
        question_area.config(state="disabled")
        
        options = self.text.get("options", [])
        if options:
            for i, option in enumerate(options, 1):
                tk.Button(self, text=option, 
                         command=lambda opt=i: self.check_answer(opt, self.text["answer"])).pack(pady=5)
        else:
            tk.Label(self, text="No options available", fg="red").pack(pady=10)
        
        tk.Button(self, text="Back to learning", 
                 command=lambda: self.master.show_learning_page({"content": learn_id})).pack(pady=5, anchor="se", padx=10)
        if qnum<totalq-1:
            tk.Button(self, text="Next Question", 
                     command=lambda: self.master.show_question_page({"content": learn_id}, qnum+1)).pack(pady=5, anchor="se", padx=10)
        
    def check_answer(self, selected_option: int, correct_answer: str):
        try:
            correct_answer = int(correct_answer)+1
        except (ValueError, TypeError):
            if correct_answer in ["A", "B", "C", "D"]:
                correct_answer = ord(correct_answer.upper()) - ord('A') + 1
                
        if selected_option == correct_answer:
            messagebox.showinfo("Result", "Correct!")
        else:
            messagebox.showinfo("Result", f"Incorrect! The correct answer was option {correct_answer}.")
            self.save_wrong_answer(self.text, self.learn_id)
            
        try:           
            if hasattr(self, "qnum") and hasattr(self, "totalq") and self.qnum == self.totalq - 1:
                result = self.advance_bullet_index()
                if result:
                    chapter_title, subchapter_title = result
                    print(f"Successfully advanced to next bullet in {subchapter_title}")
        except Exception as e:
            print(f"Error advancing bullet after answer: {e}")
                
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

        safe_syllabus_title = sanitize_path(Syllabuses[cSI].title)
        safe_chapter_title = sanitize_path(chapter_title)
        
        print(f"Saving wrong answer for: {safe_syllabus_title}/{safe_chapter_title}")
        
        filename = f"{safe_syllabus_title}_{safe_chapter_title}_mistakes.json"
        directory = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / safe_syllabus_title / safe_chapter_title
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        
        app = self.master
        app.create_mistakes_structure(Syllabuses[cSI].title, chapter_title)
        
        mistakes[safe_syllabus_title][safe_chapter_title]["number"] += 1
        mistakes[safe_syllabus_title][safe_chapter_title]["questions"].append(question)
        
        print(f"Added mistake. Total now: {mistakes[safe_syllabus_title][safe_chapter_title]['number']}")
        
        app.create_mistakes_page(chapter_title) 
        
        section_key = f'section_{safe_chapter_title}_{cSI}'
        if section_key in app.pages:
            section_page = app.pages[section_key]
            section_page.add_mistakes_button()
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(mistakes[safe_syllabus_title][safe_chapter_title], f, ensure_ascii=False, indent=4)
            print(f"Saved wrong answer to: {path}")
        except Exception as e:
            print(f"Failed to save wrong answer: {e}")
        
    
    def advance_bullet_index(self):
        global cSI
        chapter_title = None
        subchapter_title = None
        subchapter_obj = None

        for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
            for sub in chapter.get("subchapters", []):
                for bullet in sub.get("bullets", []):
                    if bullet['content'] == self.learn_id:
                        chapter_title = chapter["title"]
                        subchapter_title = sub["title"]
                        subchapter_obj = sub
                        break
                if subchapter_obj:
                    break
            if subchapter_obj:
                break

        if not (chapter_title and subchapter_title and subchapter_obj):
            print(f"Could not find bullet: {self.learn_id}")
            return None

        section_key = f'section_{sanitize_path(chapter_title)}_{cSI}'
        section_page = self.master.pages.get(section_key)
        if not section_page:
            print(f"Section page not found: {section_key}")
            return None

        self.master.mark_bullet_reviewed(self.learn_id)
        
        bullets = subchapter_obj.get("bullets", [])
        current_idx = section_page.bullet_indices.get(subchapter_title, 0)
        
        next_idx = None
        for i in range(len(bullets)):
            if not bullets[i].get("reviewed", False):
                next_idx = i
                break
        
        if next_idx is not None:
            section_page.bullet_indices[subchapter_title] = next_idx
            print(f"Advanced to next unreviewed bullet index {next_idx} in '{subchapter_title}'")
            
            section_page.update_button_text(subchapter_title)
            
            return (chapter_title, subchapter_title)
        
        print(f"No unreviewed bullets found in '{subchapter_title}'")
        return None
                    
class LearningPage(tk.Frame):
    def __init__(self, master, isExplanation: bool, topic, text: str, originaltext):
        self.video_path = None
        self.audio_path = None 
        self.topic = topic
        self.question_num = 0
        self.cap = None
        self.imgtk = None  
        self.playing = False
        self.pygame_initialized = False
        super().__init__(master)
        tk.Label(self, text="Learning Page").pack()
        self.init_pygame_async()
        if isExplanation:
            self.video_frame = tk.Frame(self, width=640, height=360, bg='black')
            self.video_frame.pack(pady=10)
            self.video_frame.pack_propagate(False)
            
            self.video_label = tk.Label(self.video_frame, text="Generating video...", 
                                      bg='black', fg='white', font=("Arial", 12))
            self.video_label.pack(expand=True)
            
            self.play_button = tk.Button(self, text="Play", command=self.toggle_play, state="disabled")
            self.play_button.pack(pady=5)
     
            try:
                pygame.mixer.init()
                self.pygame_initialized = True
                print("Pygame mixer initialized successfully")
            except Exception as e:
                print(f"Pygame mixer init failed: {e}")
                self.video_label.config(text="Audio not available") 
            
            thread = threading.Thread(target=self.generate_video, args=(topic, text), daemon=True)
            thread.start()
            
            tk.Label(self, text="Explanation:").pack(pady=5)
            explanation_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=30)
            explanation_area.pack(pady=10)
            explanation_area.insert(tk.END, text)
            explanation_area.config(state="disabled")
            
            button_frame = tk.Frame(self)
            button_frame.pack(pady=10)
            
            tk.Button(button_frame, text="Go to questions", 
                     command=lambda: self.master.show_question_page({"content": topic}, 0)).pack(side="left", anchor="e", padx=10)
        
    def init_pygame_async(self):
        def init_pygame():
            try:
                if not pygame.get_init():
                    pygame.init()
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                self.pygame_initialized = True
                print("Pygame initialized successfully")
            except Exception as e:
                print(f"Pygame initialization failed: {e}")
                self.pygame_initialized = False
        
        thread = threading.Thread(target=init_pygame, daemon=True)
        thread.start()
    
    def __del__(self):
        self.stop_playback()
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
        if self.pygame_initialized:
            pygame.mixer.quit()

    def stop_playback(self):
        self.playing = False
        if self.pygame_initialized:
            try:
                pygame.mixer.music.stop()
            except:
                pass

    def generate_video(self, j, text):
        global cSI
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
            try:
                self.video_path = video_path
                self.cap = cv2.VideoCapture(video_path)
                self.playing = False
                self.current_frame = 0
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.delay = int(1000 / self.fps) if self.fps > 0 else 33
    
                self.play_button.config(state="normal", text="Play")
                
                video_dir = os.path.dirname(video_path)
                self.audio_path = os.path.join(video_dir, "narration.mp3")
                
                if self.pygame_initialized and os.path.exists(self.audio_path):
                    try:
                        pygame.mixer.music.load(self.audio_path)
                        print(f"Audio loaded successfully from: {self.audio_path}")
                    except Exception as e:  
                        print(f"Pygame mixer load failed: {e}")
                        if hasattr(self, 'video_label'):
                            self.video_label.config(text="Audio not available")
                else:
                    print(f"Audio file not found: {self.audio_path}")
                    if hasattr(self, 'video_label'):
                        self.video_label.config(text="Audio not available")
                        
                if hasattr(self, 'video_label'):
                    ret, frame = self.cap.read()
                    if ret:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(frame)
                        img = img.resize((640, 360), Image.Resampling.LANCZOS)
                        self.imgtk = ImageTk.PhotoImage(image=img)
                        self.video_label.config(image=self.imgtk, text="")
                        self.current_frame = 1
                    else:
                        print("Failed to read first frame from video")
                        self.video_label.config(text="Failed to load video")
                    
                if self.master.current_page is self:
                    self.master.reload_learning_page(self.topic)
            except Exception as e:
                print(f"Error loading video: {e}")
                self.play_button.config(state="normal", text="Video loading failed")
        else:
            print(f"Video path doesn't exist: {video_path}")
            if hasattr(self, 'video_label'):
                self.video_label.config(text="Video generation failed")
        
    def toggle_play(self):
        if not self.video_path or not os.path.exists(self.video_path):
            return
            
        if self.playing:
            self.stop_playback()
            self.play_button.config(text="Play")
        else:
            self.start_playback()
            
    def start_playback(self):
        if not self.cap:
            return
            
        self.playing = True
        self.play_button.config(text="Pause")
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.current_frame = 0
        
        if self.pygame_initialized and self.audio_path and os.path.exists(self.audio_path):
            try:
                pygame.mixer.music.play()
                print("Audio playback started")
            except Exception as e:
                print(f"Audio playback failed: {e}")
        
        self.update_frame()
    
    def update_frame(self):
        if self.playing and self.cap and self.cap.isOpened():
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
                    if self.pygame_initialized:
                        pygame.mixer.music.stop()
            else:
                self.playing = False
                self.play_button.config(text="Play")
                if self.pygame_initialized:
                    pygame.mixer.music.stop()
            
class SectionPage(tk.Frame):
    def __init__(self, master, i):
        super().__init__(master)
        self.master = master
        self.chapter = i
        self.bullet_indices = {}
        self.button_widgets = {}
        self.mistakes_button = None 
        
        tk.Label(self, text=f"Chapter: {i['title']}", font=("Helvetica", 16)).pack(pady=10)
        for j in i["subchapters"]:
            subchapter_title = j["title"]
            self.bullet_indices[subchapter_title] = 0
            
            reviewed_count = self.get_reviewed_count(j)
            button_text = f"{subchapter_title} ({reviewed_count}/{len(j.get('bullets', []))})"
                        
            btn = tk.Button(self, text=button_text, 
                     command=lambda subchapter=j: self.navigate_bullet(subchapter))
            btn.pack(pady=2)
            self.button_widgets[subchapter_title] = btn
        
        self.add_mistakes_button()
    
    def add_mistakes_button(self):
        global cSI
        global mistakes
        
        if self.mistakes_button:
            self.mistakes_button.destroy()
            self.mistakes_button = None
            
        chapter_title = self.chapter["title"]
        safe_syllabus = sanitize_path(Syllabuses[cSI].title)
        safe_chapter = sanitize_path(chapter_title)
        
        print(f"Looking for mistakes in: {safe_syllabus} -> {safe_chapter}")
        print(f"Current mistakes keys: {list(mistakes.keys())}")
        if safe_syllabus in mistakes:
            print(f"Chapters in {safe_syllabus}: {list(mistakes[safe_syllabus].keys())}")
        
        mistake_count = 0
        if safe_syllabus in mistakes and safe_chapter in mistakes[safe_syllabus]:
            mistake_count = mistakes[safe_syllabus][safe_chapter].get("number", 0)
            print(f"Found {mistake_count} mistakes for chapter: {chapter_title}")
        
        if mistake_count > 0:
            self.mistakes_button = tk.Button(
                self, 
                text=f"Review Mistakes ({mistake_count})", 
                command=lambda: self.master.show_mistakes_page(chapter_title, 0)
            )
            self.mistakes_button.pack(pady=10)
        else:
            print(f"No mistakes found for chapter: {chapter_title}")
    
    def get_reviewed_count(self, subchapter):
        bullets = subchapter.get("bullets", [])
        return sum(1 for b in bullets if b.get("reviewed", False))
    
    def update_button_text(self, subchapter_title):
        if subchapter_title in self.button_widgets:
            for subchapter in self.chapter.get("subchapters", []):
                if subchapter["title"] == subchapter_title:
                    reviewed_count = self.get_reviewed_count(subchapter)
                    total_bullets = len(subchapter.get("bullets", []))
                    new_text = f"{subchapter_title} ({reviewed_count}/{total_bullets})"
                    self.button_widgets[subchapter_title].config(text=new_text)
                    break
    
    def navigate_bullet(self, subchapter):
        subchapter_title = subchapter["title"]
        bullets = subchapter.get("bullets", [])
        
        if not bullets:
            messagebox.showwarning("Warning", "No bullets in this subchapter")
            return
        
        first_unreviewed_idx = None
        for idx, b in enumerate(bullets):
            if not b.get("reviewed", False):
                first_unreviewed_idx = idx
                break
            
        if first_unreviewed_idx is None:
            first_unreviewed_idx = 0
            
        self.bullet_indices[subchapter_title] = first_unreviewed_idx
        bullet = bullets[first_unreviewed_idx]
                
        self.update_button_text(subchapter_title)
        self.master.show_learning_page(bullet)
        
        chapter_subchapters = self.chapter.get("subchapters", [])
        current_subchapter_idx = chapter_subchapters.index(subchapter) if subchapter in chapter_subchapters else -1
        if current_subchapter_idx >= 0 and current_subchapter_idx + 1 < len(chapter_subchapters):
            next_subchapter = chapter_subchapters[current_subchapter_idx + 1]
            thread = threading.Thread(
                target=self.master.preload_next_subchapter,
                args=(next_subchapter,),
                daemon=True
            )
            thread.start()
                
class AITutor(tk.Frame):
    def __init__(self,master):
        super().__init__(master)
        self.chat_history = [{"role": "system", "content": f"You are an AI tutor that helps students understand their syllabus and topics. A student is asking you questions about a topic they are studying. Provide clear, concise, and accurate explanations to help them learn. This is the syllabus they are studyibg from: {Syllabuses[cSI].content}"}]
        tk.Label(self, text="AI Tutor Page").pack(pady=10)
        tk.Label(self, text="Ask any questions about your syllabus or topics!").pack(pady=5)
        self.input_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=5)
        self.input_area.pack(pady=10)
        tk.Button(self, text="Send", command=self.send_query).pack(pady=5)
        self.response_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=20)
        self.response_area.pack(pady=10)
        self.response_area.config(state="disabled")
    def send_query(self):
        user_query = self.input_area.get("1.0", tk.END).strip()
        if not user_query:
            messagebox.showwarning("Warning", "Please enter a question.")
            return
        
        self.chat_history.append({"role": "user", "content": user_query})
        self.response_area.config(state="normal")
        self.response_area.insert(tk.END, f"You: {user_query}\n\n")
        self.response_area.config(state="disabled")
        self.input_area.delete("1.0", tk.END)
        
        threading.Thread(target=self.get_ai_response, daemon=True).start()
    def get_ai_response(self):
        global cSI
        response = openai_client.Request(
            prompt="\n".join([f"{msg['role']}: {msg['content']}" for msg in self.chat_history]),
            model="gpt-4o"
        )
        self.chat_history.append({"role": "assistant", "content": response})
        self.response_area.config(state="normal")
        self.response_area.insert(tk.END, f"AI Tutor: {response}\n\n")
        self.response_area.config(state="disabled")
        self.response_area.see(tk.END)
    
class SyllabusPage(tk.Frame):
    def __init__(self,master):
        global cSI
        super().__init__(master)
        for i in Syllabuses[cSI].JSONContent["chapters"]:
            tk.Button(self, text=i["title"], command=lambda chapter=i: self.master.show_section_page(chapter)).pack(pady=5)
        tk.Button(self, text="Talk to AI Tutor about Syllabus", command=self.chatbot_open).pack(pady=10)
    
    def chatbot_open(self):
        self.master.show_chatbot_page()
    
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
        
        Syllabuses[cSI].title = sanitize_path(title)
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
                if not syllabus_folder.is_dir():
                    continue

                json_file = syllabus_folder / f"{syllabus_folder.name}.json"
                if json_file.exists():
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
                    if not chapter_folder.is_dir():
                        continue
                    
                    mistakes_file = chapter_folder / f"{syllabus_folder.name}_{chapter_folder.name}_mistakes.json"
                    if mistakes_file.exists():
                        try:
                            with open(mistakes_file, "r", encoding="utf-8") as f:
                                mistakes_data = json.load(f)
                            
                            syllabus_title = Syllabuses[cSI].title if cSI < len(Syllabuses) else syllabus_folder.name
                            chapter_title = chapter_folder.name
                            
                            if syllabus_title not in mistakes:
                                mistakes[syllabus_title] = {}
                            
                            mistakes[syllabus_title][chapter_title] = mistakes_data
                            print(f"Loaded mistakes for {syllabus_title}/{chapter_title}")
                        except Exception as e:
                            print(f"Failed to load mistakes from {mistakes_file}: {e}")
                            
    def show_chatbot_page(self):
        global cSI
        key = f'chatbot_page_{cSI}'
        if key not in self.pages:
            chatbot_page = AITutor(self)
            self.pages[key] = chatbot_page
        self.current_page.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        self.current_page = self.pages[key]                            
                            
    def preload_next_subchapter(self, subchapter):
        self.preload_learning_pages(subchapter)
        self.preload_question_pages(subchapter)
                                
    def preload_learning_pages(self, subchapter):
        global cSI
        
        if not subchapter:
            return

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
                        bul["explanation"] = text
                        self.save_current_syllabus()
                    
                    learn_page = LearningPage(self, True, lid, text, sc)
                    self.pages[f'learn_{lid}_explanation_{cSI}'] = learn_page
                    print(f"Preloaded learning page: {lid}")

                thread = threading.Thread(target=load_learning_page, daemon=True)
                thread.start()
                time.sleep(0.15)

    def preload_question_pages(self, subchapter):
        global cSI
        
        if not subchapter:
            return
        
        for bullet in subchapter.get("bullets", []):
            self.preload_questions_for_bullet(bullet)
            time.sleep(0.15)

    def show_syllabus_page(self, idx):
        global cSI
        cSI = idx
        syllabus_id = sanitize_path(Syllabuses[cSI].title)
        if f'syllabus_{syllabus_id}_{cSI}' not in self.pages:
            syllabus_page = SyllabusPage(self)
            self.pages[f'syllabus_{syllabus_id}_{cSI}'] = syllabus_page
        self.current_page.pack_forget()
        self.pages[f'syllabus_{syllabus_id}_{cSI}'].pack(fill="both", expand=True)
        self.current_page = self.pages[f'syllabus_{syllabus_id}_{cSI}']

    def show_section_page(self, i):
        global cSI
        section_id = sanitize_path(i["title"])
        if f'section_{section_id}_{cSI}' not in self.pages:
            section_page = SectionPage(self, i)
            self.pages[f'section_{section_id}_{cSI}'] = section_page

            subchapters = i.get("subchapters", [])
            self.preload_learning_pages(subchapters[0])
            self.preload_question_pages(subchapters[0])
        
        self.current_page.pack_forget()
        self.pages[f'section_{section_id}_{cSI}'].pack(fill="both", expand=True)
        self.current_page = self.pages[f'section_{section_id}_{cSI}']
        
    def show_learning_page(self, bullet):
        global cSI
        learn_id = bullet["content"]
        key = f'learn_{learn_id}_explanation_{cSI}'

        if key in self.pages:
            if hasattr(self.current_page, '__del__'):
                self.current_page.__del__()

            learn_page = self.pages[key]
            self.current_page.pack_forget()
            learn_page.pack(fill="both", expand=True)
            self.current_page = learn_page
            
            self.preload_questions_for_bullet(bullet)
            
            for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
                for subchapter in chapter.get("subchapters", []):
                    if bullet in subchapter.get("bullets", []):
                        chapter_subchapters = chapter.get("subchapters", [])
                        current_idx = chapter_subchapters.index(subchapter)
                        if current_idx + 1 < len(chapter_subchapters):
                            next_subchapter = chapter_subchapters[current_idx + 1]
                            thread = threading.Thread(
                                target=self.preload_next_subchapter,
                                args=(next_subchapter,),
                                daemon=True
                            )
                            thread.start()
                        break
        else:
            messagebox.showerror("Error", f"Learning page not found for: {learn_id}")

    def create_mistakes_structure(self, syllabus_title, chapter_title):
        global mistakes
        safe_syllabus = sanitize_path(syllabus_title)
        safe_chapter = sanitize_path(chapter_title)
        
        if safe_syllabus not in mistakes:
            mistakes[safe_syllabus] = {}
        if safe_chapter not in mistakes[safe_syllabus]:
            mistakes[safe_syllabus][safe_chapter] = {"questions": [], "number": 0}
            print(f"Created mistakes structure for: {safe_syllabus}/{safe_chapter}")

    def show_mistakes_page(self, chapter_title, qnum):
        global cSI
        global mistakes
        
        if Syllabuses[cSI].title not in mistakes or chapter_title not in mistakes[Syllabuses[cSI].title]:
            messagebox.showerror("Error", f"No mistakes found for chapter: {chapter_title}")
            return
        
        questions = mistakes[Syllabuses[cSI].title][chapter_title].get("questions", [])
        if qnum >= len(questions):
            messagebox.showinfo("End", "No more mistakes to review")
            return
        
        key = f'mistake_{sanitize_path(Syllabuses[cSI].title)}_{sanitize_path(chapter_title)}_question_{qnum}_{cSI}'

        if key not in self.pages:
            question_data = questions[qnum]
            mistake_page = MistakesPage(self, question_data, qnum, len(questions), chapter_title)
            self.pages[key] = mistake_page
        
        mistake_page = self.pages[key]
        self.current_page.pack_forget()
        mistake_page.pack(fill="both", expand=True)
        self.current_page = mistake_page
    
    def show_question_page(self, bullet, qnum):
        global cSI
        learn_id = bullet["content"]
        key = f"learn_{learn_id}_question_{qnum}_{cSI}"
        
        def try_show_question(attempt=0):
            max_attempts = 10
            
            if key in self.pages:
                if hasattr(self.current_page, '__del__'):
                    self.current_page.__del__()
                
                learn_page = self.pages[key]
                self.current_page.pack_forget()
                learn_page.pack(fill="both", expand=True)
                self.current_page = learn_page
            elif attempt < max_attempts:
                if "questions" in bullet and bullet["questions"]:
                    self.create_question_pages_from_bullet(bullet, learn_id)
                    self.after(100, lambda: try_show_question(attempt + 1))
                else:
                    self.after(500, lambda: try_show_question(attempt + 1))
            else:
                messagebox.showerror("Error", 
                    f"Questions not ready for: {learn_id}\n"
                    "This might be due to:\n"
                    "1. Slow internet connection\n"
                    "2. OpenAI API limitations\n"
                    "3. Content not suitable for question generation\n\n"
                    "Please try again in a moment.")
                
        try_show_question()
            
    def return_to_home(self):
        if hasattr(self.current_page, '__del__'):
            self.current_page.__del__()
        
        self.current_page.pack_forget()
        self.home_page.pack(fill="both", expand=True)
        self.current_page = self.home_page
    
    def preload_questions_for_bullet(self, bullet):
        global cSI
        learn_id = bullet["content"]
        
        if "questions" in bullet and bullet["questions"]:
            print(f"Questions already cached for: {learn_id}")
            self.create_question_pages_from_bullet(bullet, learn_id)
            return
        
        if not hasattr(self, '_generating_questions'):
            self._generating_questions = set()
            
        if learn_id in self._generating_questions:
            return
            
        self._generating_questions.add(learn_id)
        
        def load_questions_batch():
            try:
                num_questions_prompt = f"""Generate exactly 3 distinct multiple choice questions about: {bullet['content']}
                Return ONLY valid JSON in this exact format:
                {{
                    "questions": [
                        {{
                            "question": "Question 1 text?",
                            "options": ["Option A", "Option B", "Option C", "Option D"],
                            "answer": "0"
                        }},
                        {{
                            "question": "Question 2 text?", 
                            "options": ["Option A", "Option B", "Option C", "Option D"],
                            "answer": "1"
                        }},
                        {{
                            "question": "Question 3 text?",
                            "options": ["Option A", "Option B", "Option C", "Option D"], 
                            "answer": "2"
                        }}
                    ]
                }}
                Make sure all 3 questions are distinct and test different aspects."""
                
                print(f"Generating questions for: {learn_id}")
                response = openai_client.Request(num_questions_prompt, model="gpt-4o-mini")
                
                if not response:
                    raise RuntimeError("Empty response from OpenAI")
                    
                response_str = response.strip()
                if response_str.startswith("```"):
                    response_str = re.sub(r"^```(?:json)?\s*", "", response_str, flags=re.I)
                if response_str.endswith("```"):
                    response_str = re.sub(r"\s*```$", "", response_str)
                        
                questions_data = json.loads(response_str)
                generated_questions = questions_data.get("questions", [])
                
                if not generated_questions:
                    raise RuntimeError("No questions generated")
                
                bullet["questions"] = generated_questions
                self.save_current_syllabus()

                self.after(0, self.create_question_pages_from_bullet, bullet, learn_id)
                print(f"Successfully generated {len(generated_questions)} questions for: {learn_id}")
                
            except Exception as e:
                print(f"Failed to generate questions for {learn_id}: {e}")
                if 'response' in locals():
                    print(f"Response was: {response}")
                placeholder_questions = [
                    {
                        "question": f"Question about: {learn_id}",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "answer": "0"
                    }
                ]
                bullet["questions"] = placeholder_questions
                self.after(0, self.create_question_pages_from_bullet, bullet, learn_id)
            finally:
                if hasattr(self, '_generating_questions') and learn_id in self._generating_questions:
                    self._generating_questions.remove(learn_id)

        thread = threading.Thread(target=load_questions_batch, daemon=True)
        thread.start()
        
    def create_question_pages_from_bullet(self, bullet, learn_id):
        global cSI
        if "questions" not in bullet or not bullet["questions"]:
            return
            
        for q_idx, question_data in enumerate(bullet["questions"]):
            key = f"learn_{learn_id}_question_{q_idx}_{cSI}"
            if key not in self.pages:
                question_page = QuestionPage(self, learn_id, question_data, q_idx, len(bullet["questions"]))
                self.pages[key] = question_page
                print(f"Created question page: {key}")
        
    def save_current_syllabus(self):
        global cSI
        safe_title = sanitize_path(Syllabuses[cSI].title)
        filename = f"{safe_title}.json"
        directory = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / safe_title
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
    
    def reload_learning_page(self, learn_id):
        global cSI
        bullet_obj = None
        for chapter in Syllabuses[cSI].JSONContent.get("chapters", []):
            for sub in chapter.get("subchapters", []):
                for bullet in sub.get("bullets", []):
                    if bullet["content"] == learn_id:
                        bullet_obj = bullet
                        break
        
        if not bullet_obj:
            print(f"Bullet not found for reload: {learn_id}")
            return

        key = f'learn_{learn_id}_explanation_{cSI}'
        if key in self.pages:
            old_page = self.pages[key]  
            if hasattr(old_page, '__del__'):
                old_page.__del__()
            del self.pages[key]
        
        new_page = LearningPage(self, True, learn_id, bullet_obj.get("explanation", ""), bullet_obj)
        self.pages[key] = new_page
        
        self.current_page.pack_forget()
        new_page.pack(fill="both", expand=True)
        self.current_page = new_page
    
    def create_mistakes_page(self, chapter_title):
        global cSI
        global mistakes
        
        safe_syllabus = sanitize_path(Syllabuses[cSI].title)
        safe_chapter = sanitize_path(chapter_title)
        
        if safe_syllabus not in mistakes or safe_chapter not in mistakes[safe_syllabus]:
            return
        
        mistake_data = mistakes[safe_syllabus][safe_chapter]
        questions = mistake_data.get("questions", [])
        
        print(f"Creating mistakes pages for {chapter_title} with {len(questions)} questions")
        
        for q_idx, question in enumerate(questions):
            key = f'mistake_{safe_syllabus}_{safe_chapter}_question_{q_idx}_{cSI}'
            if key not in self.pages:
                mistake_page = MistakesPage(self, question, q_idx, mistake_data["number"], chapter_title)
                self.pages[key] = mistake_page
                print(f"Created mistakes page: {key}")
                
    def show_loading_dialog(self, message="Loading..."):
        loading_window = tk.Toplevel(self)
        loading_window.title("Please Wait")
        loading_window.geometry("300x100")
        loading_window.transient(self)
        loading_window.grab_set()
      
        loading_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - loading_window.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - loading_window.winfo_height()) // 2
        loading_window.geometry(f"+{x}+{y}")
        
        tk.Label(loading_window, text=message, pady=20).pack()
        return loading_window
    
if __name__ == "__main__":
    app = App()
    app.mainloop()