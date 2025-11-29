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
    def __init__(self, topic: str, content: str, syllabus, chapter_title):
        self.topic = topic
        self.content = content
        self.script = None
        self.audio_path = None
        self.audio_files = []
        self.duration = 0
        self.syllabus = syllabus
        self.chapter_title = chapter_title
        
    def generate_script(self):
        prompt = f"""You are an expert educator like the Organic Chemistry Tutor.
        Create a detailed teaching script for the following topic:

        Topic: {self.topic}
        Content: {self.content}
        
        Make it as long as required, for as long as the entire content is covered.
        Make duration of each scene appropriate to the amount of content, for a text to speech narration speed of about 130 words per minute (gTTS).
        Remember to create a new scene every sentence so that the text is fully visible on screen.
        Title should be relatively short so that it fits. (<6 words ideally), remove any unnecessary words for title.
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
        audio_dir = DIR /self.syllabus.title / self.chapter_title / safe_topic
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
    
    def render_video(self, quality="m", fps=30):
        if not self.script:
            raise ValueError("Script not generated. Call generate_script() first.")
        
        if not self.test_ffmpeg():
            print("FFmpeg is not working properly, cannot generate video with audio")
    
        safe_syllabus = re.sub(r'[<>:"/\\|?*]', '_', self.syllabus.title)
        safe_chapter = re.sub(r'[<>:"/\\|?*]', '_', self.chapter_title)
        safe_topic = re.sub(r'[<>:"/\\|?*]', '_', self.topic)[:120]
        
        output_dir = DIR / safe_syllabus / safe_chapter / safe_topic
        output_dir.mkdir(parents=True, exist_ok=True)
        
        final_video = output_dir / f"{safe_topic}_video.mp4"
        
        if final_video.exists():
            print(f"Video already exists: {final_video}")
            return str(final_video)
        
        try:
            print("Generating Manim scenes...")
            manim_code = self.generate_manim_scenes()
            
            if not manim_code:
                print("Failed to generate Manim scenes")
                return None
       
            scene_file = output_dir / "scene.py"
            with open(scene_file, 'w', encoding='utf-8') as f:
                f.write(manim_code)

            cmd = [
                "manim",
                "-ql", 
                "--media_dir", str(output_dir),
                str(scene_file),
                "EducationalVideoSequence"
            ]

            print(f"Running Manim: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
            print(f"Manim output: {result.stdout}")

            quality_dir = "480p15"  # low quality
            manim_video_path = output_dir / "videos" / "scene" / quality_dir / "EducationalVideoSequence.mp4"
            
            if not manim_video_path.exists():
                for video_file in output_dir.rglob("EducationalVideoSequence.mp4"):
                    manim_video_path = video_file
                    break
            
            if not manim_video_path.exists():
                print("Could not find generated Manim video")
                return None

            print(f"Found Manim video at: {manim_video_path}")

            if self.audio_path and os.path.exists(self.audio_path):
                print(f"Combining video with audio: {self.audio_path}")
                success = self.add_audio_to_video(str(manim_video_path), str(final_video))
                if success:
                    print(f"Final video saved to: {final_video}")
                    if final_video.exists():
                        print(f"Video file verified: {final_video} (size: {final_video.stat().st_size} bytes)")
                        return str(final_video)
                    else:
                        print("ERROR: Final video file was not created!")
                        return None
                else:
                    print("Failed to combine audio with video, using video without audio")
                    import shutil
                    shutil.copy(str(manim_video_path), str(final_video))
                    return str(final_video)
            else:
                print("No audio available, using video without audio")
                import shutil
                shutil.copy(str(manim_video_path), str(final_video))
                return str(final_video)

        except subprocess.TimeoutExpired:
            print("Manim rendering timed out")
            return None
        except subprocess.CalledProcessError as e:
            print(f"Error rendering video: {e}")
            if e.stdout:
                print(f"Stdout: {e.stdout}")
            if e.stderr:
                print(f"Stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()
            return None
        

    def add_audio_to_video(self, video_file, output_file):
        print(f"Adding audio to video...")
        
        if not self.test_audio_file():
            print("Audio file test failed")
            return False
        
        try:
            output_dir = os.path.dirname(output_file)
            os.makedirs(output_dir, exist_ok=True)

            print("Trying method 1...")
            cmd1 = (
                f'ffmpeg -i "{video_file}" -i "{self.audio_path}" '
                f'-c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest '
                f'"{output_file}" -y'
            )
            
            result1 = subprocess.run(cmd1, shell=True, check=True, capture_output=True, text=True, timeout=60)
            
            if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:  # At least 1KB
                print(f"Method 1 succeeded")
                return True
            
        except subprocess.CalledProcessError as e:
            print(f"Method 1 failed: {e}")

        try:
            print("Trying method 2...")
            temp_file = output_file + ".temp.mp4"
            cmd2 = (
                f'ffmpeg -i "{video_file}" -i "{self.audio_path}" '
                f'-c:v libx264 -c:a aac -map 0:v:0 -map 1:a:0 -shortest '
                f'"{temp_file}" -y'
            )
            
            result2 = subprocess.run(cmd2, shell=True, check=True, capture_output=True, text=True, timeout=60)
            
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 1000:
                os.replace(temp_file, output_file)
                print(f"Method 2 succeeded")
                return True
                
        except subprocess.CalledProcessError as e:
            print(f"Method 2 failed: {e}")
        
        try:
            print("Trying method 3...")
            wav_audio = self.audio_path.replace('.mp3', '.wav')
            cmd3a = f'ffmpeg -i "{self.audio_path}" "{wav_audio}" -y'
            subprocess.run(cmd3a, shell=True, check=True, capture_output=True, text=True, timeout=30)
            
            if os.path.exists(wav_audio):
                cmd3b = (
                    f'ffmpeg -i "{video_file}" -i "{wav_audio}" '
                    f'-c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest '
                    f'"{output_file}" -y'
                )
                result3 = subprocess.run(cmd3b, shell=True, check=True, capture_output=True, text=True, timeout=60)
   
                if os.path.exists(wav_audio):
                    os.remove(wav_audio)
                    
                if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                    print(f"Method 3 succeeded")
                    return True
                    
        except Exception as e:
            print(f"Method 3 failed: {e}")

            wav_audio = self.audio_path.replace('.mp3', '.wav')
            if os.path.exists(wav_audio):
                os.remove(wav_audio)
        
        print("All audio combination methods failed")
        return False
    
    def test_ffmpeg(self):
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("FFmpeg is working correctly")
                return True
            else:
                print("FFmpeg returned error")
                return False
        except Exception as e:
            print(f"FFmpeg test failed: {e}")
            return False
        
    def test_audio_file(self):
        try:
            cmd = f'ffmpeg -i "{self.audio_path}" -f null -'
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, timeout=30)
            print(f"Audio file is valid: {self.audio_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Audio file is invalid: {e.stderr}")
            return False

def create_video(topic: str, content: str, syllabus, chapter_title):
    retopic = re.sub(r'[<>:"/\\|?*]', '_', topic)[:120]
    dir = DIR /syllabus.title / chapter_title/ retopic / f"{retopic}_video.mp4"
    if (dir).exists():
        print("Video already exists, skipping generation.")
        return str(DIR /syllabus.title / chapter_title / retopic / f"{retopic}_video.mp4")
    if not MANIM_AVAILABLE:
        print("Manim not available, skipping video generation.")
        return None

    if not FFMPEG_AVAILABLE:
        print("FFmpeg not available, skipping video generation.")
        return None

    generator = VideoGenerator(topic, content, syllabus, chapter_title)

    print(f"Generating script for: {topic}")
    if not generator.generate_script():
        return None

    print("Generating audio narration...")
    try:
        generator.generate_audio()
    except Exception as e:
        print(f"Error generating audio: {e}")

    print("Rendering video...")
    video_path = generator.render_video(fps=30)

    return video_path