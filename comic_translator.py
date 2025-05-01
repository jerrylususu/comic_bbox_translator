import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import json
import io
import base64
import threading
import time
import os
from PIL import Image, ImageTk, ImageDraw, ImageGrab
from dotenv import load_dotenv
import re
from openai import OpenAI

# 加载.env文件中的环境变量
load_dotenv()

class ComicTranslator:
    def __init__(self, root):
        self.root = root
        self.root.title("Comic Translator")
        self.root.geometry("1000x800")
        
        # 从环境变量加载API设置
        self.api_settings = {
            "endpoint": os.getenv("OPENAI_API_ENDPOINT", "https://api.openai.com/v1"),
            "model_name": os.getenv("OPENAI_MODEL_NAME", "gpt-4-vision-preview"),
            "api_key": os.getenv("OPENAI_API_KEY", "")
        }
        
        self.image_data = None
        self.status = "Not Started"
        self.translations = []  # 存储翻译结果
        self.original_image = None  # 存储原始图像
        self.scaled_image = None  # 存储缩放后的图像
        self.scale_factor = (1.0, 1.0)  # 存储缩放比例 (x, y)
        self.selected_item_id = None  # 不再需要表格行ID
        self.show_grid = tk.BooleanVar(value=False)  # 是否显示网格
        self.grid_size = 100  # 网格大小，默认100像素
        self.timer_start_time = None
        self.timer_id = None
        self.base_status = "" # To store status without timer
        self.result_labels = [] # List to store labels needing wraplength updates
        self.selected_region_labels = [] # List for selected region labels
        
        # Manual selection state
        self.manual_select_enabled = tk.BooleanVar(value=False) # Toggle for manual selection
        self.selection_line_ids = [] # Store line IDs for the selection box
        self.selection_start_coords = None
        self.selection_end_coords = None

        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Comic Translator", font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        
        # 网格选项
        grid_frame = ttk.Frame(header_frame)
        grid_frame.pack(side=tk.LEFT, padx=20)
        ttk.Checkbutton(grid_frame, text="显示网格", variable=self.show_grid, command=self.refresh_display).pack(side=tk.LEFT)
        # Add Manual Select Toggle Checkbutton
        ttk.Checkbutton(grid_frame, text="启用手动选择", variable=self.manual_select_enabled).pack(side=tk.LEFT, padx=5)
        
        # 将翻译按钮添加到标题栏右侧
        self.translate_btn = ttk.Button(header_frame, text="Translate Full Image", command=self.start_translation) # Rename button
        self.translate_btn.pack(side=tk.RIGHT, padx=(0, 5)) # Add some padding

        # Add Reset Button
        self.reset_btn = ttk.Button(header_frame, text="Reset", command=self.reset_state)
        self.reset_btn.pack(side=tk.RIGHT)
        
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
        self.api_key_entry.insert(0, self.api_settings["api_key"])
        
        # Add User Prompt Text Area below API settings
        prompt_frame = ttk.LabelFrame(main_frame, text="User Prompt (Optional Context)")
        prompt_frame.pack(fill=tk.X, pady=(5, 0)) # Pack below API Frame (or header if API frame starts hidden)

        self.user_prompt_text = scrolledtext.ScrolledText(prompt_frame, height=3, wrap=tk.WORD)
        self.user_prompt_text.pack(fill=tk.X, padx=5, pady=5)
        self.user_prompt_text.insert(tk.END, "Translate the text in this comic image to Simplified Chinese. Provide context if helpful.") # Default prompt

        # Content section
        content_frame = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Left side - image area
        image_frame_container = ttk.Frame(content_frame, padding=5)
        image_frame = ttk.LabelFrame(image_frame_container, text="Paste image (ctrl-v) or open file")
        image_frame.pack(fill=tk.BOTH, expand=True)

        content_frame.add(image_frame_container, weight=70)

        # 使用Canvas代替Label显示图像和边界框，添加滚动条以支持大图像
        canvas_frame = ttk.Frame(image_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加水平和垂直滚动条
        hscrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        hscrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        vscrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.image_canvas = tk.Canvas(canvas_frame, xscrollcommand=hscrollbar.set, yscrollcommand=vscrollbar.set)
        self.image_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        hscrollbar.config(command=self.image_canvas.xview)
        vscrollbar.config(command=self.image_canvas.yview)
        
        # Add new bindings for manual selection drag
        self.image_canvas.bind("<ButtonPress-1>", self.on_manual_select_start)
        self.image_canvas.bind("<B1-Motion>", self.on_manual_select_drag)
        self.image_canvas.bind("<ButtonRelease-1>", self.on_manual_select_end)
        
        # Make canvas focusable to receive key events if needed later
        self.image_canvas.config(highlightthickness=0) # Remove focus border if not desired
        
        # Add button to open image file
        open_btn = ttk.Button(image_frame, text="Open Image File", command=self.open_image_file)
        open_btn.pack(side=tk.BOTTOM, pady=5)
        
        # Right side - settings and results
        right_frame_container = ttk.Frame(content_frame, padding=5)
        right_frame = ttk.Frame(right_frame_container)
        right_frame.pack(fill=tk.BOTH, expand=True)

        content_frame.add(right_frame_container, weight=30)
        
        # Status
        status_frame = ttk.Frame(right_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="Status").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.status_label = ttk.Label(status_frame, text=self.status)
        self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # 添加选中区域部分
        selected_frame = ttk.LabelFrame(right_frame, text="Selected Region")
        selected_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(selected_frame, text="Original:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.selected_original = ttk.Label(selected_frame, text="")
        self.selected_original.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E) # Allow horizontal expansion
        
        ttk.Label(selected_frame, text="Translated:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.selected_translated = ttk.Label(selected_frame, text="")
        self.selected_translated.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W+tk.E) # Allow horizontal expansion
        
        # 添加用于显示框编号和坐标的标签
        ttk.Label(selected_frame, text="Box Info:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.selected_box_info = ttk.Label(selected_frame, text="")
        self.selected_box_info.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W+tk.E) # Allow horizontal expansion
        
        # Configure column 1 to expand and take available width
        selected_frame.grid_columnconfigure(1, weight=1)
        
        # Add these labels to the list for wraplength updates
        self.selected_region_labels.append(self.selected_original)
        self.selected_region_labels.append(self.selected_translated)
        self.selected_region_labels.append(self.selected_box_info) # 添加新标签到列表
        
        # Log
        log_frame = ttk.LabelFrame(right_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=5, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Results - Changed from Treeview to Scrollable Card Area
        results_frame = ttk.LabelFrame(right_frame, text="Results")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create a Canvas widget to make the frame scrollable
        self.results_canvas = tk.Canvas(results_frame)
        results_scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.results_canvas) # Frame inside the canvas

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(
                scrollregion=self.results_canvas.bbox("all")
            )
        ) # Update scroll region when frame size changes

        # Store the window ID when adding the frame to the canvas
        self.scrollable_frame_window_id = self.results_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw") # Add frame to canvas
        self.results_canvas.configure(yscrollcommand=results_scrollbar.set)

        self.results_canvas.pack(side="left", fill="both", expand=True)
        results_scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel scrolling (cross-platform)
        # Bind to the canvas itself
        self.results_canvas.bind_all("<MouseWheel>", self._on_mousewheel) # Windows/Mac
        self.results_canvas.bind_all("<Button-4>", self._on_mousewheel)   # Linux scroll up
        self.results_canvas.bind_all("<Button-5>", self._on_mousewheel)   # Linux scroll down
        # Bind to the scrollable frame as well, in case events target it directly
        self.scrollable_frame.bind_all("<MouseWheel>", self._on_mousewheel) # Windows/Mac
        self.scrollable_frame.bind_all("<Button-4>", self._on_mousewheel)   # Linux scroll up
        self.scrollable_frame.bind_all("<Button-5>", self._on_mousewheel)   # Linux scroll down

        # Bind clipboard
        self.root.bind("<Control-v>", self.paste_image)
        
        # Bind configure event to resize the frame within the canvas and update wraplengths
        self.results_canvas.bind("<Configure>", self._on_results_canvas_configure)
        
        # Redraw boxes (clears previous highlights)
        self.draw_bounding_boxes()
        
        # Clear the list of result labels
        self.result_labels = []
        # Clear the list of selected region labels (although they persist)
        # If we were recreating the UI, we'd clear here. For now, it's fine.
        
    def toggle_api_frame(self):
        if self.api_frame_visible:
            self.api_frame.pack_forget()
            self.toggle_btn.config(text="▼")
        else:
            self.api_frame.pack(fill=tk.X, pady=5, after=self.toggle_btn.master)
            self.toggle_btn.config(text="▲")
        self.api_frame_visible = not self.api_frame_visible
        
    def update_status(self, status):
        self.status = status # Store the overall status intent

        # Stop existing timer if any
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
            self.timer_start_time = None

        if status in ("Waiting Response", "Streaming Response"):
            self.base_status = status # Store the part without time
            self.timer_start_time = time.time()
            self.update_timer_display() # Start the timer display loop
        else:
            self.base_status = status
            self.status_label.config(text=status) # Just display the final status

        self.root.update() # Ensure label updates immediately
        
    def update_timer_display(self):
        """Updates the status label with elapsed time."""
        if self.timer_start_time is not None:
            elapsed = int(time.time() - self.timer_start_time)
            display_text = f"{self.base_status} ({elapsed}s)"
            self.status_label.config(text=display_text)
            # Schedule the next update
            self.timer_id = self.root.after(1000, self.update_timer_display)
        else:
            # Timer was stopped or not started, ensure label shows base status
            self.status_label.config(text=self.base_status)
        
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
        
    def open_image_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    self.image_data = f.read()
                
                self.display_image()
                self.log(f"Image loaded from {file_path}")
            except Exception as e:
                self.log(f"Error loading image: {str(e)}")
        
    def paste_image(self, event=None):
        image_pasted = False
        # Method 1: Try Tkinter first
        try:
            self.log("Attempting to get image from clipboard using Tkinter (type='image')...")
            image_data_tk = self.root.clipboard_get(type="image")
            if image_data_tk:
                self.image_data = image_data_tk
                self.display_image()
                self.log("Image pasted successfully using Tkinter.")
                image_pasted = True
            else:
                self.log("Tkinter clipboard_get(type='image') returned empty data.")

        except tk.TclError as e:
            self.log(f"Tkinter method failed: {e}")
            # Method 2: Try PIL ImageGrab if Tkinter failed
            self.log("Attempting to get image from clipboard using PIL.ImageGrab...")
            try:
                pil_image = ImageGrab.grabclipboard()
                if isinstance(pil_image, Image.Image):
                    self.log(f"PIL.ImageGrab captured image size: {pil_image.size}") # Log captured size
                    # Convert PIL Image to bytes
                    buffer = io.BytesIO()
                    # Determine format (PNG is usually a good default for clipboard)
                    format_to_save = 'PNG' 
                    # If the image has transparency, save as PNG
                    if pil_image.mode == 'RGBA' or 'A' in pil_image.info.get('transparency', ()): 
                        format_to_save = 'PNG'
                    else: # Otherwise, try JPEG, fallback to PNG
                        try:
                            pil_image.save(buffer, format='JPEG')
                            format_to_save = 'JPEG' # Successfully saved as JPEG
                        except OSError:
                            self.log("JPEG save failed (possibly RGBA), falling back to PNG.")
                            buffer = io.BytesIO() # Reset buffer
                            pil_image.save(buffer, format='PNG')
                            format_to_save = 'PNG'
                        except Exception as save_e:
                             self.log(f"Error saving PIL image as JPEG: {save_e}. Falling back to PNG.")
                             buffer = io.BytesIO() # Reset buffer
                             pil_image.save(buffer, format='PNG')
                             format_to_save = 'PNG'
                            
                    self.image_data = buffer.getvalue()
                    self.original_image = pil_image # Store the original PIL image directly
                    self.log(f"Set self.original_image from PIL, size: {self.original_image.size}") # Log stored size
                    self.display_image() # Call display_image directly as we have the PIL image
                    self.log(f"Image pasted successfully using PIL.ImageGrab (saved as {format_to_save}).")
                    image_pasted = True
                elif pil_image is None:
                    self.log("PIL.ImageGrab.grabclipboard() returned None. No image found.")
                else:
                    # grabclipboard can sometimes return a list of filenames (strings)
                    self.log(f"PIL.ImageGrab.grabclipboard() returned unexpected data type: {type(pil_image)}")

            except ImportError:
                 self.log("PIL (Pillow) is required for this paste method but seems missing or not configured correctly.")
            except NotImplementedError:
                self.log("PIL.ImageGrab is not implemented for this platform/environment.")
            except Exception as pil_e:
                self.log(f"Error using PIL.ImageGrab: {pil_e}")

        except Exception as e:
            # Catch other unexpected errors from the Tkinter block
            self.log(f"Unexpected error during Tkinter paste attempt: {str(e)}")

        # Fallback message if both methods failed
        if not image_pasted:
            self.log("Failed to paste image using both Tkinter and PIL methods.")
            # Try checking for text again as a final diagnostic
            try:
                clipboard_text = self.root.clipboard_get()
                if clipboard_text:
                     self.log(f"Clipboard contains text: '{clipboard_text[:100]}...'")
                else:
                    self.log("Clipboard appears to be empty or contains non-text data.")
            except Exception:
                self.log("Could not check for text in clipboard after image paste failures.")
            self.log("Suggestion: Try using 'Open Image File' button.")

    def display_image(self):
        """显示图像并清除之前的边界框"""
        # Modified: Now accepts self.image_data (bytes) or self.original_image (PIL Image)
        if not self.image_data and not self.original_image:
            return
            
        # 清除画布
        self.image_canvas.delete("all")
        
        # Load image either from bytes or use existing PIL image
        if self.original_image:
            # Use the PIL image directly if it exists (likely from ImageGrab)
            img_to_display = self.original_image.copy()
            self.log(f"display_image: Using existing self.original_image (PIL), size: {img_to_display.size}")
            # Ensure self.image_data has the bytes corresponding to self.original_image
            # This might be redundant if paste_image already saved it, but ensures consistency
            if not self.image_data:
                buffer = io.BytesIO()
                format_to_save = 'PNG' if img_to_display.mode == 'RGBA' or 'A' in img_to_display.info.get('transparency', ()) else 'JPEG'
                try:
                    img_to_display.save(buffer, format=format_to_save)
                    self.image_data = buffer.getvalue()
                except Exception as e:
                    self.log(f"Error converting PIL image back to bytes: {e}")
                    # Fallback: try PNG if JPEG failed
                    if format_to_save == 'JPEG':
                        try:
                            buffer = io.BytesIO()
                            img_to_display.save(buffer, format='PNG')
                            self.image_data = buffer.getvalue()
                        except Exception as png_e:
                            self.log(f"Error converting PIL image to PNG bytes: {png_e}")
                            return # Cannot proceed without image data
                    else:
                         return # Cannot proceed
        elif self.image_data:
            # Load from bytes if self.original_image is not set (likely from Tkinter paste or file open)
            try:
                self.original_image = Image.open(io.BytesIO(self.image_data))
                img_to_display = self.original_image.copy()
                self.log(f"display_image: Loaded self.original_image from self.image_data, size: {img_to_display.size}")
            except Exception as e:
                self.log(f"Error opening image data: {e}")
                self.image_data = None # Clear bad data
                self.original_image = None
                return
        else:
             return # Should not happen based on initial check

        # 使用原始大小图像，不缩放
        img_width, img_height = img_to_display.size
        
        # 设置画布滚动区域以适应原始大小的图像
        self.image_canvas.config(scrollregion=(0, 0, img_width, img_height))
        
        # 如果需要显示网格，则添加网格线
        if self.show_grid.get():
            img_to_display = self.add_grid_to_image(img_to_display)
        
        # 创建 PhotoImage 对象
        # Keep a reference to the PhotoImage object to prevent garbage collection
        self.photo_image = ImageTk.PhotoImage(img_to_display) 
        self.log(f"display_image: Created PhotoImage size: ({self.photo_image.width()}, {self.photo_image.height()})") # Log PhotoImage size
        
        # 在画布上显示图像
        self.image_canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
        self.log(f"display_image: Canvas scrollregion set to: {self.image_canvas.cget('scrollregion')}") # Log scroll region
        
        # 设置缩放比例为1:1（无缩放）
        self.scale_factor = (1.0, 1.0)
        
        # 清除翻译结果
        self.translations = []
        for widget in self.scrollable_frame.winfo_children():
             widget.destroy()
        self.clear_selection()
        # redraw boxes if any exist (should be cleared but for safety)
        self.draw_bounding_boxes()
    
    def add_grid_to_image(self, image):
        """在图像上添加网格线"""
        # 创建图像副本
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)
        
        width, height = img_copy.size
        
        # 绘制垂直线
        for x in range(0, width, self.grid_size):
            draw.line([(x, 0), (x, height)], fill="red", width=1)
            # 添加坐标标签 - 顶部
            draw.text((x + 2, 2), str(x), fill="red")
            # 添加坐标标签 - 底部
            draw.text((x + 2, height - 15), str(x), fill="red")
        
        # 绘制水平线
        for y in range(0, height, self.grid_size):
            draw.line([(0, y), (width, y)], fill="red", width=1)
            # 添加坐标标签 - 左侧
            draw.text((2, y + 2), str(y), fill="red")
            # 添加坐标标签 - 右侧
            draw.text((width - 30, y + 2), str(y), fill="red")
        
        return img_copy
    
    def refresh_display(self):
        """刷新图像显示，应用或移除网格"""
        if self.original_image:
            # 清除画布
            self.image_canvas.delete("all")
            
            # 创建要显示的图像
            display_image = self.original_image.copy()
            
            # 如果需要显示网格，则添加网格线
            if self.show_grid.get():
                display_image = self.add_grid_to_image(display_image)
            
            # 创建新的 PhotoImage 对象
            self.photo_image = ImageTk.PhotoImage(display_image)
            
            # 在画布上显示图像
            self.image_canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
            
            # 重新绘制边界框
            self.draw_bounding_boxes()
    
    def draw_bounding_boxes(self):
        """在画布上绘制所有边界框"""
        # 清除之前的边界框
        self.image_canvas.delete("box")
        
        # 获取图像尺寸
        if not self.original_image:
             self.log("draw_bounding_boxes: No self.original_image found when trying to draw boxes.")
             return
             
        img_width, img_height = self.original_image.size
        self.log(f"draw_bounding_boxes: Using self.original_image size for coordinate calculation: ({img_width}, {img_height})") # Log size used for calc
        
        # 遍历所有翻译结果，绘制边界框
        for i, item in enumerate(self.translations):
            bbox = item["bounding_box"]
            if len(bbox) == 4:
                # 解析边界框坐标 [ymin, xmin, ymax, xmax]
                ymin, xmin, ymax, xmax = bbox
                
                # 从归一化的 1000 范围转换到实际像素坐标
                x1 = int(xmin * img_width / 1000)
                y1 = int(ymin * img_height / 1000)
                x2 = int(xmax * img_width / 1000)
                y2 = int(ymax * img_height / 1000)
                
                # 应用缩放比例
                x1 = int(x1 * self.scale_factor[0])
                y1 = int(y1 * self.scale_factor[1])
                x2 = int(x2 * self.scale_factor[0])
                y2 = int(y2 * self.scale_factor[1])
                
                # 创建边界框，使用翻译索引作为标记
                self.image_canvas.create_rectangle(
                    x1, y1, x2, y2, 
                    outline="red", 
                    width=2, 
                    tags=("box", f"box_{i}")
                )
    
    def on_canvas_click(self, event):
        """处理画布点击事件，改为检查点击坐标是否在某个边界框内"""
        # 获取点击的画布坐标
        canvas_x = self.image_canvas.canvasx(event.x)
        canvas_y = self.image_canvas.canvasy(event.y)
        
        # 获取图像尺寸
        if not self.original_image:
            return
        img_width, img_height = self.original_image.size
        
        # 遍历所有翻译结果的边界框
        clicked_idx = -1
        for idx, item in enumerate(self.translations):
            bbox = item["bounding_box"]
            if len(bbox) == 4:
                # 解析边界框坐标 [ymin, xmin, ymax, xmax]
                ymin, xmin, ymax, xmax = bbox
                
                # 从归一化的 1000 范围转换到实际像素坐标
                x1_orig = int(xmin * img_width / 1000)
                y1_orig = int(ymin * img_height / 1000)
                x2_orig = int(xmax * img_width / 1000)
                y2_orig = int(ymax * img_height / 1000)
                
                # 应用缩放比例 (虽然当前为1.0，但保持逻辑)
                x1 = int(x1_orig * self.scale_factor[0])
                y1 = int(y1_orig * self.scale_factor[1])
                x2 = int(x2_orig * self.scale_factor[0])
                y2 = int(y2_orig * self.scale_factor[1])
                
                # 检查点击坐标是否在边界框内
                if x1 <= canvas_x <= x2 and y1 <= canvas_y <= y2:
                    # 如果在，则高亮对应的边界框并更新选中区域显示
                    clicked_idx = idx
                    break # Found the topmost box

        if clicked_idx != -1:
            self.highlight_bounding_box(clicked_idx)
            self.update_selected_display(clicked_idx)
            # Optional: Scroll the results view to the corresponding card? (More complex)
        else:
             # Clicked outside any box, maybe clear highlight?
             self.clear_selection()
             self.draw_bounding_boxes() # Redraw normal boxes
    
    def update_selected_display(self, idx):
        """更新选中区域的显示"""
        if 0 <= idx < len(self.translations):
            item = self.translations[idx]
            self.selected_original.config(text=item["original_text"])
            self.selected_translated.config(text=item["translated_text"])
            # 显示框编号和坐标
            box_info_text = f"Box {idx + 1}: {item['bounding_box']}"
            self.selected_box_info.config(text=box_info_text)
    
    def highlight_bounding_box(self, idx):
        """高亮显示选中的边界框"""
        # 重置所有边界框的样式
        self.image_canvas.delete("box")
        self.draw_bounding_boxes()
        
        # 高亮显示选中的边界框
        if 0 <= idx < len(self.translations):
            self.image_canvas.delete(f"box_{idx}")
            
            bbox = self.translations[idx]["bounding_box"]
            if len(bbox) == 4:
                # 获取图像尺寸
                img_width, img_height = self.original_image.size
                
                # 解析边界框坐标 [ymin, xmin, ymax, xmax]
                ymin, xmin, ymax, xmax = bbox
                
                # 从归一化的 1000 范围转换到实际像素坐标
                x1 = int(xmin * img_width / 1000)
                y1 = int(ymin * img_height / 1000)
                x2 = int(xmax * img_width / 1000)
                y2 = int(ymax * img_height / 1000)
                
                # 应用缩放比例
                x1 = int(x1 * self.scale_factor[0])
                y1 = int(y1 * self.scale_factor[1])
                x2 = int(x2 * self.scale_factor[0])
                y2 = int(y2 * self.scale_factor[1])
                
                # 创建高亮的边界框
                self.image_canvas.create_rectangle(
                    x1, y1, x2, y2, 
                    outline="blue", 
                    width=3, 
                    tags=("box", f"box_{idx}")
                )
    
    def clear_selection(self):
        """清除选中状态"""
        self.selected_original.config(text="")
        self.selected_translated.config(text="")
        self.selected_box_info.config(text="") # 清除框信息
            
    def start_translation(self):
        if not self.image_data:
            self.log("No image to translate")
            return
            
        self.update_status("Sent")
        
        # 清除之前的结果
        self.translations = []
        for widget in self.scrollable_frame.winfo_children():
             widget.destroy()
        self.clear_selection()
        
        # Get current API settings from UI
        self.api_settings["endpoint"] = self.endpoint_entry.get()
        self.api_settings["model_name"] = self.model_entry.get()
        self.api_settings["api_key"] = self.api_key_entry.get()
        
        # 硬编码提示词
        prompt = "Translate comic to zh_cn"
        # Get prompt from the new text area
        prompt = self.user_prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            prompt = "Translate comic to zh_cn" # Fallback if empty
            self.log("User prompt is empty, using default.")
        
        # Start translation in a separate thread
        threading.Thread(target=self.translate_image, args=(prompt,), daemon=True).start()
        
    def translate_image(self, prompt):
        try:
            self.log("Starting translation...")
            # Moved status update to before the blocking call
            self.update_status("Waiting Response")
            
            # Configure OpenAI client
            client = OpenAI(api_key=self.api_settings["api_key"], base_url=self.api_settings["endpoint"])
            
            # 准备发送的图像数据
            image_to_send = self.image_data
            
            # 如果需要包含网格，则处理图像
            if self.show_grid.get() and self.original_image:
                # 添加网格到图像
                grid_image = self.add_grid_to_image(self.original_image)
                # 转换回字节流
                img_byte_arr = io.BytesIO()
                grid_image.save(img_byte_arr, format=self.original_image.format or 'JPEG')
                image_to_send = img_byte_arr.getvalue()
            
            # Encode image
            base64_image = base64.b64encode(image_to_send).decode('utf-8')
            
            # 修改系统提示要求返回JSONL格式
            system_message = """
            You are a comic translator. Analyze the image to:
            1. Find text in speech bubbles or captions
            2. Return the original text
            3. Translate it to Chinese (Simplified)
            4. Return the bounding box coordinates for each text segment
            
            Format your response as JSONL (JSON Lines) where each text bubble is a separate JSON object on a new line:
            (coordinates are normalized to 1000 and in the format [ymin, xmin, ymax, xmax] where the top left corner is the zero point and has position 0,0)
            {"box_2d": [ymin, xmin, ymax, xmax], "org": "Original text", "res": "Translated text"}
            ...
            
            This format allows each text bubble to be processed as soon as it's identified.
            
            Important: Always normalize the bounding box coordinates to a range of 0 to 1000, where 0,0 is the top-left corner
            and 1000,1000 is the bottom-right corner of the image. The bounding box coordinates MUST be in the order:
            [ymin, xmin, ymax, xmax]. Make sure the keys are exactly "box_2d", "org", and "res".
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
            response_stream = client.chat.completions.create(
                model=self.api_settings["model_name"],
                messages=messages,
                stream=True
            )
            
            # 收集和处理流式响应
            collected_messages = ""
            first_chunk_received = False # Flag to switch status

            for chunk in response_stream:
                if not first_chunk_received:
                     self.update_status("Streaming Response") # Update status when first data arrives
                     first_chunk_received = True

                # Check if choices exist before accessing delta content
                if chunk.choices:
                    # Check if delta content exists and is not None
                    if chunk.choices[0].delta and chunk.choices[0].delta.content:
                        chunk_text = chunk.choices[0].delta.content
                        collected_messages += chunk_text
                        # Update log view efficiently by inserting only the new chunk
                        self.log_text.insert(tk.END, chunk_text)
                        self.log_text.see(tk.END)

                        # --- Process potentially complete JSON lines ---
                        # Find the last newline to process complete lines only
                        # Using accumulated 'collected_messages' which now contains the *entire* history
                        # We need to parse based on the *current state* of the accumulated text
                        lines_to_check = collected_messages.split('\n')
                        self.log(f"translate_image: Checking {len(lines_to_check)} potential lines from accumulated text.")

                        processed_keys_in_stream = set() # Track items added during stream

                        # Iterate through lines found in the *current* accumulated text
                        for idx, line in enumerate(lines_to_check):
                            line = line.strip()
                            # Check if it looks like a complete JSON object
                            if line.startswith("{") and line.endswith("}"):
                                try:
                                    self.log(f"translate_image: Attempting to parse potential JSON line {idx}: {line}")
                                    item = json.loads(line)

                                    if "box_2d" in item and "org" in item and "res" in item:
                                        bounding_box = item.get("box_2d", [])
                                        original_text = item.get("org", "")
                                        translated_text = item.get("res", "")

                                        item_key = (tuple(bounding_box), original_text, translated_text)

                                        # Check if already added globally or in this specific stream run
                                        is_already_added = any(
                                            tuple(t["bounding_box"]) == tuple(bounding_box) and
                                            t["original_text"] == original_text and
                                            t["translated_text"] == translated_text
                                            for t in self.translations
                                        )

                                        if item_key not in processed_keys_in_stream and not is_already_added:
                                            current_index = len(self.translations)
                                            self.log(f"translate_image: Adding new translation item at index {current_index} from streamed line.")
                                            self.translations.append({
                                                "bounding_box": bounding_box,
                                                "original_text": original_text,
                                                "translated_text": translated_text
                                            })
                                            processed_keys_in_stream.add(item_key) # Mark as processed in this stream pass

                                            self.log(f"translate_image: Calling add_result_card for index {current_index}")
                                            self.add_result_card(
                                                bounding_box=bounding_box,
                                                original_text=original_text,
                                                translated_text=translated_text,
                                                index=current_index
                                            )

                                            self.log("translate_image: Calling draw_bounding_boxes after adding card")
                                            self.draw_bounding_boxes()
                                        elif is_already_added:
                                             self.log(f"translate_image: Skipping duplicate item (already in global list): {item_key}")
                                        else: # Already processed in this stream pass
                                             self.log(f"translate_image: Skipping duplicate item (already processed this stream): {item_key}")
                                    else:
                                        self.log(f"translate_image: Parsed JSON object missing required keys: {item}")
                                except json.JSONDecodeError as e:
                                    # This is expected if a line is not complete JSON yet
                                    if idx == len(lines_to_check) - 1 and not line.endswith("}"):
                                         # Likely an incomplete line at the end, ignore decode error for now
                                         self.log(f"translate_image: JSONDecodeError likely on incomplete line {idx}: {e}. Line: '{line}'")
                                    else:
                                         # Could be malformed JSON within the stream
                                         self.log(f"translate_image: JSONDecodeError on potentially complete line {idx}: {e}. Line: '{line}'")
                                    pass # Continue collecting data
                                except Exception as inner_e: # Catch other errors during processing
                                     self.log(f"translate_image: Error processing line {idx}: {inner_e}. Line: '{line}'")
                                     pass # Try to continue

                        self.root.update()
                        time.sleep(0.01)  # Small delay for UI responsiveness
                    else:
                        # Check if this chunk might contain usage information (often delta/content is null then)
                        if hasattr(chunk, 'usage') and chunk.usage is not None:
                             self.log(f"translate_image: Received usage info: {chunk.usage}")
                             # Store token counts if available
                             if hasattr(chunk.usage, 'prompt_tokens'):
                                 self.prompt_tokens = chunk.usage.prompt_tokens
                             if hasattr(chunk.usage, 'completion_tokens'):
                                 self.completion_tokens = chunk.usage.completion_tokens
                             if hasattr(chunk.usage, 'total_tokens'):
                                 self.total_tokens = chunk.usage.total_tokens
                        #else:
                        #    # Log if choices exist but delta/content is missing/null for debugging?
                        #    self.log(f"translate_image: Chunk choices[0] exists but delta or content is missing/null. Chunk: {chunk}")
                        # --- End of added block ---

                # --- Add this else block for when chunk.choices is empty ---
                else:
                     # Check if this chunk without choices contains usage info (as seen in example)
                     if hasattr(chunk, 'usage') and chunk.usage is not None:
                         self.log(f"translate_image: Received usage info in chunk without choices: {chunk.usage}")
                         # Store token counts if available
                         if hasattr(chunk.usage, 'prompt_tokens'):
                             self.prompt_tokens = chunk.usage.prompt_tokens
                         if hasattr(chunk.usage, 'completion_tokens'):
                             self.completion_tokens = chunk.usage.completion_tokens
                         if hasattr(chunk.usage, 'total_tokens'):
                             self.total_tokens = chunk.usage.total_tokens
                     else:
                        # Log the chunk if it doesn't contain choices or usage
                        self.log(f"translate_image: Received chunk without choices or usage info: {chunk}")
                # --- End of added block ---

            self.log(f"translate_image: Finished streaming loop. Final collected_messages: '{collected_messages}'")
            # Final processing of any remaining content in collected_messages after the loop
            self.log("translate_image: Calling process_jsonl_response for final check")
            self.process_jsonl_response(collected_messages) # Pass the final accumulated string
            self.log("translate_image: Returned from process_jsonl_response")

            # Processing complete
            self.update_status(self.get_done_status_message()) # Use helper function
            self.log(f"translate_image: Translation process finished. Total translations: {len(self.translations)}")

        except Exception as e:
            self.update_status("Error")
            # Use traceback to get more detailed error info including line number
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Translation error in translate_image: {str(e)}\n{error_details}") # Modified log
    
    def process_jsonl_response(self, jsonl_text):
        self.log(f"process_jsonl_response: Starting with text: '{jsonl_text}'") # Added log
        # 尝试找出所有可能的JSON对象
        try: # Add try-except block for regex
            potential_objects = re.findall(r'({.*?})', jsonl_text, re.DOTALL)
            self.log(f"process_jsonl_response: Found {len(potential_objects)} potential JSON objects using regex.") # Added log
        except Exception as regex_e:
            self.log(f"process_jsonl_response: Error during regex findall: {regex_e}")
            potential_objects = [] # Ensure it's an empty list if regex fails

        processed_indices_in_final = set() # Track items added in this final pass

        for i, obj_str in enumerate(potential_objects):
            self.log(f"process_jsonl_response: Processing potential object {i}: {obj_str}") # Added log
            try:
                item = json.loads(obj_str)
                self.log(f"process_jsonl_response: Successfully parsed object {i}: {item}") # Added log
                
                # 确保是我们期望的格式 (using new keys)
                if "box_2d" in item and "org" in item and "res" in item:
                    bounding_box = item.get("box_2d", [])
                    original_text = item.get("org", "")
                    translated_text = item.get("res", "")
                    
                    item_key = (tuple(bounding_box), original_text, translated_text)

                    # 检查这个结果是否已经添加过 (including checks against stream and this pass)
                    if item_key not in processed_indices_in_final and not any(
                        tuple(t["bounding_box"]) == tuple(bounding_box) and
                        t["original_text"] == original_text and
                        t["translated_text"] == translated_text
                        for t in self.translations
                    ):
                        # 添加到翻译结果列表 (using internal keys)
                        current_index = len(self.translations)
                        self.log(f"process_jsonl_response: Adding new translation item at index {current_index}") # Added log
                        self.translations.append({
                            "bounding_box": bounding_box,
                            "original_text": original_text,
                            "translated_text": translated_text
                        })
                        processed_indices_in_final.add(item_key) # Mark as processed in this final pass

                        # Update the UI (add card) instead of Treeview
                        self.log(f"process_jsonl_response: Calling add_result_card for index {current_index}") # Added log
                        self.add_result_card(
                             bounding_box=bounding_box,
                             original_text=original_text,
                             translated_text=translated_text,
                             index=current_index # Pass the correct index
                        )

                        # 绘制边界框
                        self.log("process_jsonl_response: Calling draw_bounding_boxes after adding card") # Added log
                        self.draw_bounding_boxes()
                    else:
                        self.log(f"process_jsonl_response: Skipping duplicate item: {item_key}") # Added log
                else:
                     self.log(f"process_jsonl_response: Parsed JSON object missing required keys: {item}") # Added log
            except json.JSONDecodeError as json_e:
                self.log(f"process_jsonl_response: JSONDecodeError on object {i}: {json_e}. Object string: '{obj_str}'") # Added log
                continue
            except Exception as loop_e: # Catch other potential errors in the loop
                 self.log(f"process_jsonl_response: Error processing object {i}: {loop_e}. Object string: '{obj_str}'")
                 continue # Continue to next potential object

        self.log(f"process_jsonl_response: Finished processing. Final translations count: {len(self.translations)}") # Added log
            
    def reset_state(self):
        """Clears results, selections, bounding boxes, and resets status."""
        self.log("Resetting application state...")

        # Clear translations list
        self.translations = []

        # Clear result cards from the UI
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.result_labels = [] # Clear the list holding references to labels

        # Clear selected region display
        self.clear_selection()

        # Clear bounding boxes from canvas
        self.image_canvas.delete("box")
        # Also clear manual selection rectangle if present
        self.image_canvas.delete("selection_rect")
        for line_id in self.selection_line_ids:
             self.image_canvas.delete(line_id)
        self.selection_line_ids = []
        self.selection_start_coords = None
        self.selection_end_coords = None

        # Reset token counts
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

        # Reset status label and stop timer
        self.update_status("Not Started") # This also handles stopping the timer

        # Update canvas scroll region (might be empty now)
        self.results_canvas.update_idletasks()
        self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))

        self.log("State reset complete.")
        self.root.update() # Ensure UI reflects changes immediately

    def get_done_status_message(self):
        """Formats the 'Done' status message including token counts if available."""
        if self.prompt_tokens > 0 or self.completion_tokens > 0:
            return f"Done (In={self.prompt_tokens}, Out={self.completion_tokens}, Total={self.total_tokens})"
        else:
            return "Done"

    # --- New method to add result cards ---
    def add_result_card(self, bounding_box, original_text, translated_text, index):
        """Adds a new card to the scrollable results frame."""
        self.log(f"add_result_card: Called for index {index}. Current total translations: {len(self.translations)}") # Added log
        try:
            # Validate index before proceeding (important!)
            if not (0 <= index < len(self.translations)):
                 self.log(f"add_result_card: Error - Invalid index {index} provided. Max index should be {len(self.translations) - 1}.")
                 # Optionally, try to find the item if it was added but index is wrong? Or just return.
                 # For now, let's log and return to prevent crash.
                 return 
                 
            # Retrieve the item safely using the provided index IF NEEDED.
            # In this specific function, we receive the data directly, so we don't strictly *need* to access self.translations[index]
            # but it's good practice to be aware of the index relationship.

            card_frame = ttk.LabelFrame(self.scrollable_frame, padding=(5, 5), text=f"Result {index + 1} / Box: {bounding_box}")
            card_frame.pack(fill=tk.X, padx=5, pady=5)

            # Make the frame itself clickable to highlight the box
            card_frame.bind("<Button-1>", lambda e, idx=index: self.on_card_click(idx))
            
            # Use a sub-frame for labels to manage layout better and bind clicks
            text_area_frame = ttk.Frame(card_frame)
            text_area_frame.pack(fill=tk.X)
            text_area_frame.bind("<Button-1>", lambda e, idx=index: self.on_card_click(idx)) # Bind this frame too

            # Configure columns within the text area frame
            text_area_frame.columnconfigure(1, weight=1) # Make the text column expand

            # Original Text Label (clickable too)
            ttk.Label(text_area_frame, text="Original:", font=('Arial', 10, 'bold'), width=10).grid(row=0, column=0, sticky=tk.NW, padx=(0, 5))
            initial_wrap = max(100, self.results_canvas.winfo_width() - 120) # Adjusted wrap calculation slightly
            org_text_label = ttk.Label(text_area_frame, text=original_text, wraplength=initial_wrap)
            org_text_label.grid(row=0, column=1, sticky=tk.W+tk.E)
            org_text_label.bind("<Button-1>", lambda e, idx=index: self.on_card_click(idx)) # Bind label too

            # Translated Text Label (clickable too)
            ttk.Label(text_area_frame, text="Translated:", font=('Arial', 10, 'bold'), width=10).grid(row=1, column=0, sticky=tk.NW, padx=(0, 5), pady=(5,0))
            res_text_label = ttk.Label(text_area_frame, text=translated_text, wraplength=initial_wrap)
            res_text_label.grid(row=1, column=1, sticky=tk.W+tk.E, pady=(5,0))
            res_text_label.bind("<Button-1>", lambda e, idx=index: self.on_card_click(idx)) # Bind label too

            # Store labels for later wraplength updates
            self.result_labels.append(org_text_label)
            self.result_labels.append(res_text_label)

            # Ensure canvas updates its scrollregion after adding card
            self.results_canvas.update_idletasks() # Ensure widgets are placed
            self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
            self.log(f"add_result_card: Successfully added card for index {index}") # Added log
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"add_result_card: Error adding card for index {index}: {str(e)}\n{error_details}") # Added log

    def on_card_click(self, index):
        """Handles clicks on a result card."""
        self.log(f"on_card_click: Card clicked for index {index}") # Added log
        try:
            if 0 <= index < len(self.translations):
                self.update_selected_display(index)
                self.highlight_bounding_box(index)
            else:
                 self.log(f"on_card_click: Invalid index {index}. Total translations: {len(self.translations)}") # Added log
        except Exception as e:
             import traceback
             error_details = traceback.format_exc()
             self.log(f"on_card_click: Error handling click for index {index}: {str(e)}\n{error_details}") # Added log

    # --- New method to update all card wraplengths ---
    def update_all_card_wraplengths(self, event):
        """Updates the wraplength of all result labels based on canvas width."""
        # Calculate available width, subtracting padding/margins
        # Use right_frame_container width for selected region labels
        selected_region_container_width = self.selected_original.master.winfo_width()
        # Estimate label width + padding for selected region
        selected_wrap_width = max(50, selected_region_container_width - 70)

        # Use event.width which is the canvas's current width
        wrap_width = max(100, event.width - 100) # Ensure a minimum width
        for label in self.result_labels:
            try:
                # Check if widget exists before configuring
                if label.winfo_exists():
                    label.configure(wraplength=wrap_width)
            except tk.TclError:
                # Handle cases where the widget might be destroyed during update
                pass

        # Update selected region labels
        for label in self.selected_region_labels:
            try:
                # Check if widget exists before configuring
                if label.winfo_exists():
                    label.configure(wraplength=selected_wrap_width)
            except tk.TclError:
                # Handle cases where the widget might be destroyed during update
                pass

    # --- New method for mouse wheel scrolling ---
    def _on_mousewheel(self, event):
        """Handles mouse wheel scrolling for the results canvas."""
        # Determine the scroll direction and amount based on platform
        if event.num == 5 or event.delta < 0: # Scroll down (Windows/Mac negative delta, Linux Button 5)
            scroll_amount = 1
        elif event.num == 4 or event.delta > 0: # Scroll up (Windows/Mac positive delta, Linux Button 4)
            scroll_amount = -1
        else:
            scroll_amount = 0 # Should not happen

        # Check if the mouse pointer is over the results canvas or its scrollable frame
        widget_under_pointer = self.root.winfo_containing(event.x_root, event.y_root)
        is_over_results = False
        current_widget = widget_under_pointer
        while current_widget is not None:
            if current_widget == self.results_canvas:
                is_over_results = True
                break
            current_widget = current_widget.master # Check parent widget

        if is_over_results:
            self.results_canvas.yview_scroll(scroll_amount, "units")

    # --- New method to handle canvas configure ---
    def _on_results_canvas_configure(self, event):
        """Handles canvas resize to adjust the scrollable frame width and label wraplength."""
        canvas_width = event.width
        # Update the width of the frame window item inside the canvas
        self.results_canvas.itemconfigure(self.scrollable_frame_window_id, width=canvas_width)
        # Update wraplengths based on the new width
        self.update_all_card_wraplengths(event) # Pass the event along

    # --- New methods for manual selection and translation ---
    def on_manual_select_start(self, event):
        """Handles the start of a drag selection on the canvas."""
        # Get canvas coordinates (which are image coordinates due to 1:1 scaling)
        canvas_x = self.image_canvas.canvasx(event.x)
        canvas_y = self.image_canvas.canvasy(event.y)
        self.selection_start_coords = (canvas_x, canvas_y)
        self.selection_end_coords = None # Reset end coords

        # Delete previous selection lines if they exist
        for line_id in self.selection_line_ids:
            self.image_canvas.delete(line_id)
        self.selection_line_ids = []

    def on_manual_select_drag(self, event):
        """Handles the dragging motion during selection."""
        # Only draw selection rectangle if manual mode is enabled
        if not self.manual_select_enabled.get():
            return
        
        if self.selection_start_coords:
            # Get current end coordinates
            canvas_x = self.image_canvas.canvasx(event.x)
            canvas_y = self.image_canvas.canvasy(event.y)
            self.selection_end_coords = (canvas_x, canvas_y)

            # Delete the previous lines
            for line_id in self.selection_line_ids:
                self.image_canvas.delete(line_id)
            self.selection_line_ids = []

            # Draw the new rectangle border with lines
            x1, y1 = self.selection_start_coords
            x2, y2 = self.selection_end_coords
            line_color = "green"
            line_width = 2
            self.selection_line_ids.append(self.image_canvas.create_line(x1, y1, x2, y1, fill=line_color, width=line_width, tags=("selection_rect",)))
            self.selection_line_ids.append(self.image_canvas.create_line(x2, y1, x2, y2, fill=line_color, width=line_width, tags=("selection_rect",)))
            self.selection_line_ids.append(self.image_canvas.create_line(x2, y2, x1, y2, fill=line_color, width=line_width, tags=("selection_rect",)))
            self.selection_line_ids.append(self.image_canvas.create_line(x1, y2, x1, y1, fill=line_color, width=line_width, tags=("selection_rect",)))

    def on_manual_select_end(self, event):
        """Handles the end of the drag selection and triggers manual translation if enabled."""
        trigger_manual_translate = False
        is_click = True # Assume it's a click initially
        final_coords = None

        if self.selection_start_coords and self.selection_end_coords:
            x1, y1 = self.selection_start_coords
            x2, y2 = self.selection_end_coords

            # Ensure coordinates are ordered
            final_x1 = min(x1, x2)
            final_y1 = min(y1, y2)
            final_x2 = max(x1, x2)
            final_y2 = max(y1, y2)
            final_coords = (final_x1, final_y1, final_x2, final_y2)

            # Check if it was a significant drag and if manual mode is enabled
            is_drag = abs(final_x1 - final_x2) > 5 and abs(final_y1 - final_y2) > 5
            if is_drag:
                 is_click = False # It was a drag
                 if self.manual_select_enabled.get():
                      trigger_manual_translate = True
                      self.log(f"Manual selection completed: ({final_x1}, {final_y1}) to ({final_x2}, {final_y2})")
                 else:
                     self.log("Drag detected but manual selection is disabled. Treating as click.")
                     # Fall through to click handling
            # else: it was a small drag, treat as click

        # Perform action based on flags
        if trigger_manual_translate and final_coords:
            # Trigger manual translation process
            self.translate_manual_selection((final_coords[0], final_coords[1]), (final_coords[2], final_coords[3]))
        elif is_click:
            # Handle as a click (highlight existing box or do nothing)
            canvas_x = self.image_canvas.canvasx(event.x)
            canvas_y = self.image_canvas.canvasy(event.y)
            self.handle_canvas_click(canvas_x, canvas_y)
        # Else (it was a drag but manual mode was disabled), do nothing extra here, click handler was called implicitly if needed.

        # Delete the visual selection rectangle lines if they were drawn
        for line_id in self.selection_line_ids:
             self.image_canvas.delete(line_id)
        self.selection_line_ids = []

        # Reset selection state regardless
        self.selection_start_coords = None
        self.selection_end_coords = None

    def translate_manual_selection(self, start_coords, end_coords):
        """Crops the selected region and sends it for translation."""
        if not self.original_image:
            self.log("Error: No original image loaded for manual selection.")
            return

        try:
            x1, y1 = start_coords
            x2, y2 = end_coords

            # Crop the image using PIL
            # Coordinates are already image coordinates
            cropped_image = self.original_image.crop((int(x1), int(y1), int(x2), int(y2)))
            self.log(f"Cropped image size: {cropped_image.size}")

            # Convert cropped image to bytes
            buffer = io.BytesIO()
            format_to_save = 'PNG' # Use PNG for potentially small, sharp text regions
            cropped_image.save(buffer, format=format_to_save)
            cropped_image_data = buffer.getvalue()

            if not cropped_image_data:
                self.log("Error: Failed to convert cropped image to bytes.")
                return

            # Update status and log
            self.update_status("Sent (Manual)")
            self.log("Sending cropped region for translation...")

            # Get current API settings
            self.api_settings["endpoint"] = self.endpoint_entry.get()
            self.api_settings["model_name"] = self.model_entry.get()
            self.api_settings["api_key"] = self.api_key_entry.get()

            # Start translation in a separate thread
            threading.Thread(
                target=self.call_manual_translate_api,
                args=(cropped_image_data, (x1, y1, x2, y2)), # Pass image bytes and original pixel coords
                daemon=True
            ).start()

        except Exception as e:
            self.update_status("Error (Manual Crop)")
            self.log(f"Error during manual selection processing: {str(e)}")

    def call_manual_translate_api(self, cropped_image_data, selection_coords_img):
        """Makes the API call for the manually selected region."""
        try:
            self.update_status("Waiting Response") # Timer starts here

            client = OpenAI(api_key=self.api_settings["api_key"], base_url=self.api_settings["endpoint"])
            base64_image = base64.b64encode(cropped_image_data).decode('utf-8')

            # Simplified system message for direct translation
            system_message_manual = """
            You are a text translator. Analyze the provided image snippet and translate any text you find into Chinese (Simplified).
            Format your response as a single JSON object:
            {"org": "Original text found", "res": "Translated Chinese text"}

            If no text is found, return:
            {"org": "", "res": ""}
            """

            # Get the user prompt from the text area
            user_context_prompt = self.user_prompt_text.get("1.0", tk.END).strip()
            if not user_context_prompt:
                 user_context_prompt = "Translate the text in this image." # Default if empty

            messages = [
                {"role": "system", "content": system_message_manual},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_context_prompt}, # Use user prompt here
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}" # Assume PNG for cropped
                            }
                        }
                    ]
                }
            ]

            response = client.chat.completions.create(
                model=self.api_settings["model_name"],
                messages=messages,
                # No streaming needed for short expected response
            )

            self.update_status("Processing Response") # Timer stops implicitly

            # Extract response content
            if response.choices and response.choices[0].message.content:
                response_text = response.choices[0].message.content
                self.log(f"Manual translation response received: {response_text}")

                # Extract usage data (added)
                if hasattr(response, 'usage') and response.usage:
                    self.prompt_tokens = response.usage.prompt_tokens
                    self.completion_tokens = response.usage.completion_tokens
                    self.total_tokens = response.usage.total_tokens
                    self.log(f"Manual translation usage: In={self.prompt_tokens}, Out={self.completion_tokens}, Total={self.total_tokens}")
                else:
                    # Reset tokens if usage info is missing for this call
                    self.prompt_tokens = 0
                    self.completion_tokens = 0
                    self.total_tokens = 0

                # --- Robust JSON Parsing --- 
                cleaned_text = response_text.strip()
                # Remove potential markdown code block fences
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[len("```json"):].strip()
                if cleaned_text.startswith("```"):
                     cleaned_text = cleaned_text[len("```"):].strip()
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-len("```")].strip()
                
                # Attempt to remove trailing commas before closing braces/brackets
                # This is a simplified approach for the expected structure
                cleaned_text = re.sub(r",\s*(\}|\])", r"\1", cleaned_text)
                
                self.log(f"Cleaned response for JSON parsing: {cleaned_text}")

                # Parse the cleaned JSON response
                try:
                    result_json = json.loads(cleaned_text)
                    original_text = result_json.get("org", "")
                    translated_text = result_json.get("res", "")

                    if not original_text and not translated_text:
                         self.log("LLM reported no text found in the selection.")
                         self.update_status("Done (Manual - No Text)")
                         return # Don't add an empty result

                    # Calculate normalized bounding box from selection_coords_img
                    if self.original_image:
                        img_width, img_height = self.original_image.size
                        x1, y1, x2, y2 = selection_coords_img

                        # Normalize coordinates [ymin, xmin, ymax, xmax]
                        norm_ymin = int(y1 * 1000 / img_height)
                        norm_xmin = int(x1 * 1000 / img_width)
                        norm_ymax = int(y2 * 1000 / img_height)
                        norm_xmax = int(x2 * 1000 / img_width)
                        bounding_box = [norm_ymin, norm_xmin, norm_ymax, norm_xmax]

                        # Add to translations list
                        new_translation = {
                            "bounding_box": bounding_box,
                            "original_text": original_text,
                            "translated_text": translated_text
                        }
                        self.translations.append(new_translation)
                        new_index = len(self.translations) - 1

                        # Update UI
                        self.add_result_card(
                            bounding_box=bounding_box,
                            original_text=original_text,
                            translated_text=translated_text,
                            index=new_index
                        )
                        self.draw_bounding_boxes() # Redraw all boxes including the new one
                        # Update status using helper function (Manual)
                        done_status = self.get_done_status_message().replace("Done", "Done (Manual)")
                        self.update_status(done_status)
                        self.log(f"Manual translation added for box: {bounding_box}")

                    else:
                        self.update_status("Error (Manual - No Original Img)")
                        self.log("Error: Original image disappeared before processing manual result.")

                except json.JSONDecodeError as json_e:
                    self.update_status("Error (Manual - Invalid JSON)")
                    self.log(f"Error decoding JSON response from manual translation: {json_e}")
                    self.log(f"Cleaned text attempted for parsing: {cleaned_text}")
                except Exception as proc_e:
                    self.update_status("Error (Manual - Processing)")
                    self.log(f"Error processing manual translation result: {proc_e}")

            else:
                self.update_status("Error (Manual - Empty Response)")
                self.log("Manual translation failed: Empty response from API.")

        except Exception as e:
            # Stop timer if it's still running due to exception before status update
            if self.timer_id:
                 self.root.after_cancel(self.timer_id)
                 self.timer_id = None
                 self.timer_start_time = None
            self.update_status("Error (Manual API Call)")
            self.log(f"Error during manual translation API call: {str(e)}")

    # --- Function to handle clicks on the canvas (restored logic) ---
    def handle_canvas_click(self, canvas_x, canvas_y):
        """Handles simple clicks on the canvas to select/highlight boxes."""
        # Get image dimensions
        if not self.original_image:
            return
        img_width, img_height = self.original_image.size

        # Iterate through translations to find the clicked box
        clicked_idx = -1
        for idx, item in enumerate(self.translations):
            bbox = item["bounding_box"]
            if len(bbox) == 4:
                # Convert normalized bbox to pixel coordinates
                ymin, xmin, ymax, xmax = bbox
                x1_orig = int(xmin * img_width / 1000)
                y1_orig = int(ymin * img_height / 1000)
                x2_orig = int(xmax * img_width / 1000)
                y2_orig = int(ymax * img_height / 1000)

                # (No scaling needed as scale_factor is always 1.0 now)
                x1 = x1_orig
                y1 = y1_orig
                x2 = x2_orig
                y2 = y2_orig

                # Check if click is inside this box
                if x1 <= canvas_x <= x2 and y1 <= canvas_y <= y2:
                    clicked_idx = idx
                    break # Found the topmost box

        if clicked_idx != -1:
            self.log(f"Canvas click detected inside box index {clicked_idx}")
            self.highlight_bounding_box(clicked_idx)
            self.update_selected_display(clicked_idx)
        else:
            # Clicked outside any box, clear selection and highlights
            self.log("Canvas click detected outside any box.")
            self.clear_selection()
            self.draw_bounding_boxes() # Redraw normal boxes

if __name__ == "__main__":
    root = tk.Tk()
    app = ComicTranslator(root)
    root.mainloop() 