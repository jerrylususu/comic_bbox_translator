import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import io
import base64
import threading
import time
from PIL import Image, ImageTk
import openai

class ComicTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("Comic Translator")
        self.root.geometry("1000x800")
        
        self.api_settings = {
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model_name": "gpt-4-vision-preview",
            "api_key": ""
        }
        
        self.image_data = None
        self.status = "Not Started"
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Comic Translator", font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        
        # Mode selection
        mode_frame = ttk.Frame(header_frame)
        mode_frame.pack(side=tk.LEFT, padx=20)
        
        self.mode_var = tk.StringVar(value="Auto")
        ttk.Radiobutton(mode_frame, text="Auto", variable=self.mode_var, value="Auto").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="Manual", variable=self.mode_var, value="Manual").pack(side=tk.LEFT)
        
        # Collapsible API settings
        self.api_frame_visible = False
        
        api_header = ttk.Frame(main_frame)
        api_header.pack(fill=tk.X)
        
        ttk.Label(api_header, text="API Setting").pack(side=tk.LEFT)
        self.toggle_btn = ttk.Button(api_header, text="▼", width=2, command=self.toggle_api_frame)
        self.toggle_btn.pack(side=tk.LEFT, padx=5)
        
        self.api_frame = ttk.Frame(main_frame)
        
        # API Settings
        settings_frame = ttk.Frame(self.api_frame)
        settings_frame.pack(fill=tk.X, pady=5)
        
        # Endpoint
        ttk.Label(settings_frame, text="endpoint", width=12).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.endpoint_entry = ttk.Entry(settings_frame, width=60)
        self.endpoint_entry.grid(row=0, column=1, padx=5, pady=5)
        self.endpoint_entry.insert(0, self.api_settings["endpoint"])
        
        # Model name
        ttk.Label(settings_frame, text="model_name", width=12).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.model_entry = ttk.Entry(settings_frame, width=60)
        self.model_entry.grid(row=1, column=1, padx=5, pady=5)
        self.model_entry.insert(0, self.api_settings["model_name"])
        
        # API Key
        ttk.Label(settings_frame, text="api_key", width=12).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.api_key_entry = ttk.Entry(settings_frame, width=60, show="*")
        self.api_key_entry.grid(row=2, column=1, padx=5, pady=5)
        
        # Content section
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left side - image area
        image_frame = ttk.LabelFrame(content_frame, text="Paste image (ctrl-v)")
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.image_label = ttk.Label(image_frame)
        self.image_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Right side - settings and results
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Prompt
        prompt_frame = ttk.Frame(right_frame)
        prompt_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(prompt_frame, text="Prompt").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.prompt_entry = ttk.Entry(prompt_frame, width=40)
        self.prompt_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.prompt_entry.insert(0, "Translate comic to zh_cn")
        
        # Status
        status_frame = ttk.Frame(right_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="Status").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.status_label = ttk.Label(status_frame, text=self.status)
        self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Log
        log_frame = ttk.LabelFrame(right_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=5, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Results
        results_frame = ttk.LabelFrame(right_frame, text="Results")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        results_headers = ttk.Frame(results_frame)
        results_headers.pack(fill=tk.X)
        
        ttk.Label(results_headers, text="bounding_box", width=15).pack(side=tk.LEFT)
        ttk.Label(results_headers, text="original_text", width=20).pack(side=tk.LEFT)
        ttk.Label(results_headers, text="translated_text", width=20).pack(side=tk.LEFT)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, height=10, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Button area
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.translate_btn = ttk.Button(button_frame, text="Translate", command=self.start_translation)
        self.translate_btn.pack(side=tk.RIGHT)
        
        # Bind clipboard
        self.root.bind("<Control-v>", self.paste_image)
        
    def toggle_api_frame(self):
        if self.api_frame_visible:
            self.api_frame.pack_forget()
            self.toggle_btn.config(text="▼")
        else:
            self.api_frame.pack(fill=tk.X, pady=5, after=self.toggle_btn.master)
            self.toggle_btn.config(text="▲")
        self.api_frame_visible = not self.api_frame_visible
        
    def update_status(self, status):
        self.status = status
        self.status_label.config(text=status)
        self.root.update()
        
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
        
    def paste_image(self, event=None):
        try:
            image = self.root.clipboard_get(type="image")
            if image:
                self.image_data = image
                img = Image.open(io.BytesIO(image))
                # Resize image to fit in the frame while maintaining aspect ratio
                max_width, max_height = 400, 400
                img.thumbnail((max_width, max_height))
                photo = ImageTk.PhotoImage(img)
                self.image_label.config(image=photo)
                self.image_label.image = photo
                self.log("Image pasted successfully")
        except Exception as e:
            self.log(f"Error pasting image: {str(e)}")
            
    def start_translation(self):
        if not self.image_data:
            self.log("No image to translate")
            return
            
        self.update_status("Sent")
        
        # Get current API settings
        self.api_settings["endpoint"] = self.endpoint_entry.get()
        self.api_settings["model_name"] = self.model_entry.get()
        self.api_settings["api_key"] = self.api_key_entry.get()
        
        prompt = self.prompt_entry.get()
        
        # Start translation in a separate thread
        threading.Thread(target=self.translate_image, args=(prompt,), daemon=True).start()
        
    def translate_image(self, prompt):
        try:
            self.log("Starting translation...")
            self.update_status("Waiting Response")
            
            # Configure OpenAI client
            openai.api_key = self.api_settings["api_key"]
            
            # Encode image
            base64_image = base64.b64encode(self.image_data).decode('utf-8')
            
            # Prepare the message
            system_message = """
            You are a comic translator. Analyze the image to:
            1. Find text in speech bubbles or captions
            2. Return the original text
            3. Translate it to Chinese (Simplified)
            4. Return the bounding box coordinates for each text segment
            
            Format your response as a JSON object with the following structure:
            {
                "results": [
                    {
                        "bounding_box": [x1, y1, x2, y2],
                        "original_text": "Original text",
                        "translated_text": "Translated text"
                    },
                    ...
                ]
            }
            """
            
            messages = [
                {"role": "system", "content": system_message},
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # Make the API call with streaming
            self.update_status("Streaming Response")
            response_stream = openai.chat.completions.create(
                model=self.api_settings["model_name"],
                messages=messages,
                stream=True
            )
            
            # Collect the streaming response
            collected_chunks = []
            collected_messages = ""
            
            for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    chunk_text = chunk.choices[0].delta.content
                    collected_chunks.append(chunk_text)
                    collected_messages += chunk_text
                    self.log_text.delete(1.0, tk.END)
                    self.log_text.insert(tk.END, collected_messages)
                    self.log_text.see(tk.END)
                    self.root.update()
                    time.sleep(0.01)  # Small delay to ensure UI updates
            
            # Process the response
            self.update_status("Done")
            self.display_results(collected_messages)
            
        except Exception as e:
            self.update_status("Error")
            self.log(f"Translation error: {str(e)}")
            
    def display_results(self, json_text):
        try:
            # Try to extract JSON from the response
            start_idx = json_text.find("{")
            end_idx = json_text.rfind("}")
            
            if start_idx != -1 and end_idx != -1:
                json_str = json_text[start_idx:end_idx+1]
                data = json.loads(json_str)
                
                # Clear previous results
                self.results_text.delete(1.0, tk.END)
                
                # Display results
                if "results" in data:
                    for item in data["results"]:
                        bounding_box = item.get("bounding_box", [])
                        original_text = item.get("original_text", "")
                        translated_text = item.get("translated_text", "")
                        
                        result_line = f"{bounding_box}\t{original_text}\t{translated_text}\n\n"
                        self.results_text.insert(tk.END, result_line)
            else:
                self.log("Could not parse JSON from response")
                self.results_text.insert(tk.END, json_text)
                
        except json.JSONDecodeError:
            self.log("JSON parsing error")
            self.results_text.insert(tk.END, json_text)
        except Exception as e:
            self.log(f"Error displaying results: {str(e)}")
            
if __name__ == "__main__":
    root = tk.Tk()
    app = ComicTranslator(root)
    root.mainloop() 