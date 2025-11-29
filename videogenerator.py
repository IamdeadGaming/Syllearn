import os
import json
import openai_client
from pathlib import Path
from manim import *
from pydub import AudioSegment
import subprocess
import re
import traceback
from platformdirs import user_data_dir
import re
import os
VOICE = "en-US-GuyNeural"
QUALITY = "medium"
APP_NAME = "Syllearn"
APP_AUTHOR = "GA Studios"
DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR))

Path(DIR).mkdir(exist_ok=True)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except Exception:
    gTTS = None
    GTTS_AVAILABLE = False

try:
    import manim
    MANIM_AVAILABLE = True
except Exception:
    manim = None
    MANIM_AVAILABLE = False

try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except Exception:
    ffmpeg = None
    FFMPEG_AVAILABLE = False


class VideoGenerator:
    def __init__(self, topic: str, content: str, syllabus, chapter):
        self.topic = topic
        self.content = content
        self.script = None
        self.audio_path = None
        self.audio_files = []
        self.duration = 0
        self.syllabus = syllabus
        self.chapter = chapter
        
    def generate_script(self):
        prompt = f"""You are an expert educator like the Organic Chemistry Tutor.
        Create a detailed teaching script for the following topic:

        Topic: {self.topic}
        Content: {self.content}
        
        Make it as long as required, for as long as the entire content is covered.
        Make duration of each scene appropriate to the amount of content, for a text to speech narration speed of about 130 words per minute (gTTS).
        Remember to create a new scene every sentence so that the text is fully visible
        Title should be relatively short so that it fits. (<6 words ideally)
        Return a JSON object with this structure (ONLY JSON, no other text), Doesn't have to be 4 scenes, can be more or less:
        {{
            "title": "<video title>",
            "scenes": [
                {{
                    "scene_number": 1,
                    "scene_type": "title",
                    "script": "<narration script>",
                    "duration": 3,
                    "visuals": "<description of what to draw>"
                }},
                {{
                    "scene_number": 2,
                    "scene_type": "explanation",
                    "script": "<narration script>",
                    "duration": 10,
                    "visuals": "<math equations, diagrams, etc>",
                    "key_points": ["point 1", "point 2"]
                }},
                {{
                    "scene_number": 3,
                    "scene_type": "example",
                    "script": "<worked example>",
                    "duration": 15,
                    "visuals": "<step by step solution>"
                }},
                {{
                    "scene_number": 4,
                    "scene_type": "summary",
                    "script": "<summary of key concepts>",
                    "duration": 5,
                    "visuals": "<key takeaways>"
                }}
            ]
        }}"""

        try:
            response = openai_client.Request(prompt, model="gpt-4o-mini")
            self.script = json.loads(response)
            return self.script
        except Exception as e:
            print(f"Error generating script: {e}")
            # Try to extract JSON from response using regex
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    m = json.loads(match.group(0))
                    self.script = m
                    return self.script
                except Exception as e2:
                    print(f"Failed to parse extracted JSON: {e2}")
            print(f"LLM did not produce valid JSON: {response[:500]}")
            return None
    
    def generate_audio(self):
        if not self.script:
            raise ValueError("Script not generated. Call generate_script() first.")

        safe_topic = re.sub(r'[<>:"/\\|?*]', '_', self.topic)[:120]
        audio_dir = DIR / self.syllabus.title / self.chapter / safe_topic
        audio_dir.mkdir(parents=True, exist_ok=True)

        self.audio_path = str(audio_dir / "narration.mp3")
        
        # Return cached audio if it exists
        if os.path.exists(self.audio_path):
            print(f"Using cached audio: {self.audio_path}")
            return self.audio_path
        
        audio_segments = []

        for scene in self.script["scenes"]:
            narration = scene.get("script", "")
            if not narration or not narration.strip():
                print(f"Skipping scene {scene['scene_number']} - no narration")
                continue

            audio_file = audio_dir / f"audio_scene_{scene['scene_number']}.mp3"
            
            # Skip if already exists
            if audio_file.exists():
                print(f"Audio already exists for scene {scene['scene_number']}, loading from cache...")
                try:
                    audio = AudioSegment.from_file(str(audio_file))
                    audio_segments.append(audio)
                except Exception as e:
                    print(f"Failed to load cached audio for scene {scene['scene_number']}: {e}")
                continue

            # Generate using gTTS
            try:
                import time
                from gtts import gTTS
                
                time.sleep(2)  # Rate limiting between requests
                
                print(f"Generating audio for scene {scene['scene_number']}: {narration[:50]}...")
                tts = gTTS(text=narration, lang='en', slow=False)
                tts.save(str(audio_file))
                
                audio = AudioSegment.from_file(str(audio_file))
                audio_segments.append(audio)
                print(f"Generated audio for scene {scene['scene_number']}")
                
            except Exception as e:
                print(f"[TTS] gTTS failed for scene {scene['scene_number']}: {e}")
                traceback.print_exc()
                continue

        if audio_segments:
            combined = audio_segments[0]
            for segment in audio_segments[1:]:
                combined += segment

            combined.export(self.audio_path, format="mp3")
            print(f"Combined audio saved to: {self.audio_path}")
            return self.audio_path
        else:
            print("No audio segments generated - creating silent placeholder")
            silent = AudioSegment.silent(duration=5000)
            silent.export(self.audio_path, format="mp3")
            return self.audio_path
    
    def generate_manim_scenes(self):
        if not self.script:
            raise ValueError("Script not generated. Call generate_script() first.")
        
        scenes_code = """from manim import *

class EducationalVideoSequence(Scene):
    def construct(self):
"""
        
        for scene in self.script["scenes"]:
            scene_type = scene.get("scene_type", "text")
            script = scene.get("script", "")
            visuals = scene.get("visuals", "")
            
            if scene_type == "title":
                scenes_code += f"""
        # Scene {scene['scene_number']}: Title
        title = Text("{scene['title'] if 'title' in scene else self.topic}", font_size=60)
        
        self.play(Write(title))

        self.wait({scene.get('duration')})
        self.play(FadeOut(title))
"""
            
            elif scene_type == "explanation":
                scenes_code += f"""
        # Scene {scene['scene_number']}: Explanation
        text = Text("{script}", font_size=24)
        self.play(Write(text))
        self.wait({scene.get('duration')})
        self.play(FadeOut(text))
"""
            
            elif scene_type == "example":
                scenes_code += f"""
        # Scene {scene['scene_number']}: Example
        example_text = Text("{script}", font_size=24)
        self.play(Write(example_text))
        self.wait({scene.get('duration')})
        self.play(FadeOut(example_text))
"""

            elif scene_type == "summary":
                scenes_code += f"""
        # Scene {scene['scene_number']}: Summary
        summary_text = Text("{script}", font_size=24)
        self.play(Write(summary_text))
        self.wait({scene.get('duration')})
        self.play(FadeOut(summary_text))
"""
        
        return scenes_code
    
    def render_video(self, fps=30):
        """Render the complete video with audio"""
        if not self.script:
            raise ValueError("Script not generated. Call generate_script() first.")
        
        if not self.audio_path or not os.path.exists(self.audio_path):
            print(f"Warning: Audio not found at: {self.audio_path}")
        
        # Sanitize all paths
        safe_syllabus = re.sub(r'[<>:"/\\|?*™®©]', '_', self.syllabus.title)
        safe_chapter = re.sub(r'[<>:"/\\|?*™®©]', '_', self.chapter)
        safe_topic = re.sub(r'[<>:"/\\|?*™®©]', '_', self.topic)[:120]
        
        output_dir = DIR / safe_syllabus / safe_chapter / safe_topic
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = str(output_dir / f"{safe_topic}_video.mp4")
        temp_video = str(output_dir / f"{safe_topic}_temp.mp4")
        
        # Check if video already exists
        if os.path.exists(output_file):
            print(f"Video already exists: {output_file}")
            return output_file
        
        try:
            print("Rendering Manim video...")

            manim_code = self.generate_manim_scenes()
            
            if not manim_code:
                print("Failed to generate Manim scenes")
                return None
            
            # Save to temp file with sanitized name
            scene_file = str(output_dir / "scene.py")
            with open(scene_file, 'w', encoding='utf-8') as f:
                f.write(manim_code)

            cmd = [
                "manim",
                "-ql",  # low quality
                "--fps", str(fps),
                scene_file,
                "EducationalVideoSequence"
            ]

            print(f"Running Manim: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Manim output: {result.stdout}")

            quality_dirs = {"l": "480p15", "m": "720p30", "h": "1080p60"}
            quality_dir = quality_dirs.get("low", "720p30")
            
            manim_video = output_dir / "videos" / "scene" / quality_dir / "EducationalVideoSequence.mp4"

            if not manim_video.exists():
                print(f"Video not found at: {manim_video}")
                print(f"Checking alternate locations...")
                
                for alt_path in output_dir.rglob("EducationalVideoSequence.mp4"):
                    print(f"Found video at: {alt_path}")
                    manim_video = alt_path
                    break
                
                if not manim_video.exists():
                    print(f"Could not find generated video")
                    return None

            print(f"Manim video found at: {manim_video}")

            if self.audio_path and os.path.exists(self.audio_path):
                print(f"Adding audio from: {self.audio_path}")
                self.add_audio_to_video(str(manim_video), str(output_dir))
            else:
                import shutil
                shutil.copy(str(manim_video), str(output_dir))
                print(f"Video saved to {output_dir} (no audio)")

            print(f"Final video saved to: {output_dir}")
            return str(output_dir)

        except subprocess.CalledProcessError as e:
            print(f"Error rendering video: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()
            return None

    def add_audio_to_video(self, video_file, output_file):
        try:
            cmd = [
                "ffmpeg",
                "-i", video_file,
                "-i", self.audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output_file,
                "-y"
            ]
            
            print(f"Adding audio with ffmpeg...")
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Audio added to video successfully")
            
        except subprocess.CalledProcessError as e:
            print(f"Error adding audio to video: {e}")

def create_video(topic: str, content: str, syllabus, chapter):
    safe_syllabus = re.sub(r'[<>:"/\\|?*™®©]', '_', syllabus.title)
    safe_chapter = re.sub(r'[<>:"/\\|?*™®©]', '_', chapter)
    safe_topic = re.sub(r'[<>:"/\\|?*™®©]', '_', topic)[:120]
    
    output_dir = DIR / safe_syllabus / safe_chapter / safe_topic
    output_dir.mkdir(parents=True, exist_ok=True)
    
    video_file = output_dir / f"{safe_topic}_video.mp4"
    if video_file.exists():
        print(f"Video already exists: {video_file}")
        return str(video_file)
    
    if not MANIM_AVAILABLE or not FFMPEG_AVAILABLE:
        print("Manim or FFmpeg not available, skipping video generation.")
        return None

    try:
        generator = VideoGenerator(topic, content, syllabus, chapter)

        print(f"Generating script for: {topic}")
        if not generator.generate_script():
            return None

        print("Generating audio narration...")
        try:
            generator.generate_audio()
        except Exception as e:
            print(f"Error generating audio: {e}")
            return None

        print("Rendering video...")
        video_path = generator.render_video(fps=30)

        return video_path
    except Exception as e:
        print(f"Error creating video: {e}")
        traceback.print_exc()
        return None



