import json
import re
from unittest.mock import patch

# Import the VideoGenerator class
from videogenerator import VideoGenerator

def test_generate_script():
    # Test case 1: Valid JSON response
    valid_json = '{"title": "Test Title", "scenes": []}'
    with patch('openai_client.Request', return_value=valid_json):
        generator = VideoGenerator("Test Topic", "Test Content")
        script = generator.generate_script()
        assert script is not None
        assert script['title'] == "Test Title"
        print("Test 1 passed: Valid JSON handled correctly.")

    # Test case 2: JSON embedded in extra text
    embedded_json = 'Here is some text {"title": "Embedded Title", "scenes": []} and more text.'
    with patch('openai_client.Request', return_value=embedded_json):
        generator = VideoGenerator("Test Topic", "Test Content")
        script = generator.generate_script()
        assert script is not None
        assert script['title'] == "Embedded Title"
        print("Test 2 passed: Embedded JSON extracted correctly.")

    # Test case 3: Invalid response (no JSON)
    invalid_response = 'This is not JSON at all.'
    with patch('openai_client.Request', return_value=invalid_response):
        generator = VideoGenerator("Test Topic", "Test Content")
        script = generator.generate_script()
        assert script is None
        print("Test 3 passed: Invalid response handled correctly (returned None).")

    # Test case 4: Malformed JSON in response
    malformed_json = 'Here is some text {"title": "Malformed", "scenes": [} and more text.'
    with patch('openai_client.Request', return_value=malformed_json):
        generator = VideoGenerator("Test Topic", "Test Content")
        script = generator.generate_script()
        assert script is None
        print("Test 4 passed: Malformed JSON handled correctly (returned None).")

if __name__ == "__main__":
    test_generate_script()
    print("All tests passed!")
