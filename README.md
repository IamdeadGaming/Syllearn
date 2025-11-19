# Setup (Windows)
1. Install Miniconda.
2. conda create -n syllearn python=3.11 -y
3. conda activate syllearn
4. conda install -c conda-forge numpy pillow ffmpeg libsndfile av manim -y
5. pip install -r requirements.txt