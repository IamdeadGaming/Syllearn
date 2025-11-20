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
    def __init__(self, topic: str, content: str):
        self.topic = topic
        self.content = content
        self.script = None
        self.audio_path = None
        self.audio_files = []
        self.duration = 0
        
    def generate_script(self):
        prompt = f"""You are an expert educator like the Organic Chemistry Tutor.
        Create a detailed teaching script for the following topic:

        Topic: {self.topic}
        Content: {self.content}

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
                    "duration": 5,s
                    "visuals": "<key takeaways>"
                }}
            ]
        }}"""

        try:
            response = openai_client.Request(prompt)
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
        audio_dir = DIR / safe_topic
        audio_dir.mkdir(parents=True, exist_ok=True)

        audio_segments = []

        for scene in self.script["scenes"]:
            narration = scene["script"]
            if not narration:
                continue

            audio_file = audio_dir / f"audio_scene_{scene['scene_number']}.wav"
            used = False

            if not used and GTTS_AVAILABLE:
                try:
                    tts = gTTS(narration, lang="en")
                    tmp_mp3 = audio_file.with_suffix('.mp3')
                    tts.save(str(tmp_mp3))
                    AudioSegment.from_file(str(tmp_mp3)).export(str(audio_file), format="wav")
                    os.remove(str(tmp_mp3))
                    used = True
                except Exception as e:
                    print(f"[TTS] gTTS save failed for scene {scene['scene_number']}: {e}")
                    traceback.print_exc()

            if not used:
                print(f"No TTS backend available for scene {scene['scene_number']}, skipping audio for this scene.")
                continue
            
            try:
                audio = AudioSegment.from_file(str(audio_file))
                audio_segments.append(audio)
                self.audio_files.append(str(audio_file))
                self.duration += len(audio) / 1000
                print(f"Generated audio for scene {scene['scene_number']}")
            except Exception as e:
                print(f"Failed to load audio for scene {scene['scene_number']}: {e}")

        if audio_segments:
            combined = audio_segments[0]
            for segment in audio_segments[1:]:
                combined += segment

            self.audio_path = str(audio_dir / "narration.mp3")
            combined.export(self.audio_path, format="mp3")
            print(self.audio_path)
        else:
            print("For some fucking reason the list is empty.")
    
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
        subtitle = Text("{visuals}", font_size=30)
        subtitle.next_to(title, DOWN)
        
        self.play(Write(title))
        self.play(Write(subtitle))
        self.wait({scene.get('duration', 3)})
        self.play(FadeOut(title), FadeOut(subtitle))
"""
            
            elif scene_type == "explanation":
                scenes_code += f"""
        # Scene {scene['scene_number']}: Explanation
        text = Text("{script[:100]}...", font_size=24)
        self.play(Write(text))
        self.wait({scene.get('duration', 10)})
        self.play(FadeOut(text))
"""
            
            elif scene_type == "example":
                scenes_code += f"""
        # Scene {scene['scene_number']}: Example
        example_text = Text("{visuals}", font_size=24)
        self.play(Write(example_text))
        self.wait({scene.get('duration', 15)})
        self.play(FadeOut(example_text))
"""

            elif scene_type == "summary":
                scenes_code += f"""
        # Scene {scene['scene_number']}: Summary
        summary_text = Text("{visuals}", font_size=24)
        self.play(Write(summary_text))
        self.wait({scene.get('duration', 5)})
        self.play(FadeOut(summary_text))
"""
        
        return scenes_code
    
    def render_video(self, quality="m", fps=30):
        if not self.script:
            raise ValueError("Script not generated. Call generate_script() first.")

        safe_topic = re.sub(r'[<>:"/\\|?*]', '_', self.topic)[:120]
        scene_dir = DIR / safe_topic
        scene_dir.mkdir(parents=True, exist_ok=True)

        manim_code = self.generate_manim_scenes()

        scene_file = scene_dir / "scene.py"
        with open(str(scene_file), 'w') as f:
            f.write(manim_code)

        output_file = f"{DIR}/{safe_topic}_video.mp4"

        try:
            cmd = [
                "manim",
                "-q", quality,
                "-p",
                "--fps", str(fps),
                str(scene_file),
                "EducationalVideoSequence"
            ]

            subprocess.run(cmd, check=True)

            video_file = DIR / "EducationalVideoSequence.mp4"
            if self.audio_files:
                if self.audio_path and os.path.exists(self.audio_path):
                    self.add_audio_to_video(str(video_file), output_file)
                else:
                    os.rename(str(video_file), output_file)
                    print(f"Video saved to {output_file} (no combined audio)")
            else:
                os.rename(str(video_file), output_file)
                print(f"Video saved to {output_file} (no audio)")

            print(f"Video saved to {output_file}")
            return output_file

        except subprocess.CalledProcessError as e:
            print(f"Error rendering video: {e}")
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

            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Audio added to video: {output_file}")

        except subprocess.CalledProcessError as e:
            print(f"Error adding audio to video: {e}")

def create_video(topic: str, content: str):

    if not MANIM_AVAILABLE:
        print("Manim not available, skipping video generation.")
        return None

    if not FFMPEG_AVAILABLE:
        print("FFmpeg not available, skipping video generation.")
        return None

    generator = VideoGenerator(topic, content)

    print(f"Generating script for: {topic}")
    if not generator.generate_script():
        return None

    print("Generating audio narration...")
    try:
        generator.generate_audio()
    except Exception as e:
        print(f"Error generating audio: {e}")

    print("Rendering video...")
    video_path = generator.render_video(quality="m", fps=30)

    return video_path



