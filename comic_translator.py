import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import json
import io
import base64
import threading
import time
import os
from PIL import Image, ImageTk, ImageDraw
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
        self.selected_item_id = None  # 存储选中的表格行ID
        self.show_grid = tk.BooleanVar(value=False)  # 是否显示网格
        self.grid_size = 100  # 网格大小，默认100像素
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
        
        # 网格选项
        grid_frame = ttk.Frame(header_frame)
        grid_frame.pack(side=tk.LEFT, padx=20)
        ttk.Checkbutton(grid_frame, text="显示网格", variable=self.show_grid, command=self.refresh_display).pack(side=tk.LEFT)
        
        # 将翻译按钮添加到标题栏右侧
        self.translate_btn = ttk.Button(header_frame, text="Translate", command=self.start_translation)
        self.translate_btn.pack(side=tk.RIGHT)
        
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
        
        # Content section
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left side - image area
        image_frame = ttk.LabelFrame(content_frame, text="Paste image (ctrl-v) or open file")
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
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
        
        self.image_canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Add button to open image file
        open_btn = ttk.Button(image_frame, text="Open Image File", command=self.open_image_file)
        open_btn.pack(side=tk.BOTTOM, pady=5)
        
        # Right side - settings and results
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
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
        self.selected_original = ttk.Label(selected_frame, text="", wraplength=300)
        self.selected_original.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(selected_frame, text="Translated:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.selected_translated = ttk.Label(selected_frame, text="", wraplength=300)
        self.selected_translated.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Log
        log_frame = ttk.LabelFrame(right_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=5, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Results
        results_frame = ttk.LabelFrame(right_frame, text="Results")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 使用Treeview替代ScrolledText显示表格结果
        self.results_tree = ttk.Treeview(results_frame, columns=("bounding_box", "original_text", "translated_text"), show="headings")
        self.results_tree.heading("bounding_box", text="Bounding Box")
        self.results_tree.heading("original_text", text="Original Text")
        self.results_tree.heading("translated_text", text="Translated Text")
        
        self.results_tree.column("bounding_box", width=150)
        self.results_tree.column("original_text", width=150)
        self.results_tree.column("translated_text", width=150)
        
        # 设置行高以显示多行内容
        style = ttk.Style()
        style.configure("Treeview", rowheight=60)
        
        # 添加Treeview选择事件
        self.results_tree.bind("<<TreeviewSelect>>", self.on_treeview_select)
        
        # 添加滚动条
        tree_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=tree_scroll.set)
        
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
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
        try:
            # 尝试通过tk.TclError来捕获并处理没有图像的情况
            try:
                image = self.root.clipboard_get(type="image")
                if image:
                    self.image_data = image
                    self.display_image()
                    self.log("Image pasted successfully")
            except tk.TclError:
                # 如果没有图像在剪贴板中，尝试其他方法
                self.log("No image found in clipboard. Try using 'Open Image File' button.")
                
        except Exception as e:
            self.log(f"Error pasting image: {str(e)}")
    
    def display_image(self):
        """显示图像并清除之前的边界框"""
        if not self.image_data:
            return
            
        # 清除画布
        self.image_canvas.delete("all")
        
        # 保存原始图像
        self.original_image = Image.open(io.BytesIO(self.image_data))
        
        # 使用原始大小图像，不缩放
        img_width, img_height = self.original_image.size
        
        # 设置画布滚动区域以适应原始大小的图像
        self.image_canvas.config(scrollregion=(0, 0, img_width, img_height))
        
        # 创建要显示的图像
        display_image = self.original_image.copy()
        
        # 如果需要显示网格，则添加网格线
        if self.show_grid.get():
            display_image = self.add_grid_to_image(display_image)
        
        # 创建 PhotoImage 对象
        self.photo_image = ImageTk.PhotoImage(display_image)
        
        # 在画布上显示图像
        self.image_canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
        
        # 设置缩放比例为1:1（无缩放）
        self.scale_factor = (1.0, 1.0)
        
        # 清除翻译结果
        self.translations = []
        self.results_tree.delete(*self.results_tree.get_children())
        self.clear_selection()
    
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
        img_width, img_height = self.original_image.size
        
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
        """处理画布点击事件"""
        # 查找点击位置的边界框
        clicked_items = self.image_canvas.find_withtag(tk.CURRENT)
        for item in clicked_items:
            tags = self.image_canvas.gettags(item)
            for tag in tags:
                if tag.startswith("box_"):
                    # 从标签中提取索引
                    idx = int(tag.split("_")[1])
                    if 0 <= idx < len(self.translations):
                        # 选择对应的表格行
                        self.select_item_by_index(idx)
                        return
    
    def select_item_by_index(self, idx):
        """通过索引选择表格行"""
        if 0 <= idx < len(self.translations):
            # 获取所有行ID
            items = self.results_tree.get_children()
            if idx < len(items):
                # 选择指定的行
                self.results_tree.selection_set(items[idx])
                self.results_tree.focus(items[idx])
                self.results_tree.see(items[idx])
                # 更新选中的区域显示
                self.update_selected_display(idx)
    
    def on_treeview_select(self, event):
        """处理表格选择事件"""
        selection = self.results_tree.selection()
        if selection:
            item_id = selection[0]
            idx = self.results_tree.index(item_id)
            # 更新选中的区域显示
            self.update_selected_display(idx)
            # 高亮显示对应的边界框
            self.highlight_bounding_box(idx)
    
    def update_selected_display(self, idx):
        """更新选中区域的显示"""
        if 0 <= idx < len(self.translations):
            item = self.translations[idx]
            self.selected_original.config(text=item["original_text"])
            self.selected_translated.config(text=item["translated_text"])
    
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
            
    def start_translation(self):
        if not self.image_data:
            self.log("No image to translate")
            return
            
        self.update_status("Sent")
        
        # 清除之前的结果
        self.translations = []
        self.results_tree.delete(*self.results_tree.get_children())
        self.clear_selection()
        
        # Get current API settings from UI
        self.api_settings["endpoint"] = self.endpoint_entry.get()
        self.api_settings["model_name"] = self.model_entry.get()
        self.api_settings["api_key"] = self.api_key_entry.get()
        
        # 硬编码提示词
        prompt = "Translate comic to zh_cn"
        
        # Start translation in a separate thread
        threading.Thread(target=self.translate_image, args=(prompt,), daemon=True).start()
        
    def translate_image(self, prompt):
        try:
            self.log("Starting translation...")
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
            {"bounding_box": [ymin, xmin, ymax, xmax], "original_text": "Original text", "translated_text": "Translated text"}
            ...
            
            This format allows each text bubble to be processed as soon as it's identified.
            
            Important: Always normalize the bounding box coordinates to a range of 0 to 1000, where 0,0 is the top-left corner 
            and 1000,1000 is the bottom-right corner of the image. The bounding box coordinates MUST be in the order: 
            [ymin, xmin, ymax, xmax].
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
            response_stream = client.chat.completions.create(
                model=self.api_settings["model_name"],
                messages=messages,
                stream=True
            )
            
            # 收集和处理流式响应
            collected_messages = ""
            
            for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    chunk_text = chunk.choices[0].delta.content
                    collected_messages += chunk_text
                    self.log_text.delete(1.0, tk.END)
                    self.log_text.insert(tk.END, collected_messages)
                    self.log_text.see(tk.END)
                    
                    # 检查是否有完整的JSON对象可以解析
                    lines = collected_messages.split("\n")
                    print(collected_messages)
                    
                    for line in lines:
                        line = line.strip()
                        if line and (line.startswith("{") and line.endswith("}")):
                            try:
                                # 尝试解析单行JSON
                                item = json.loads(line)
                                if "bounding_box" in item and "original_text" in item and "translated_text" in item:
                                    bounding_box = item.get("bounding_box", [])
                                    original_text = item.get("original_text", "")
                                    translated_text = item.get("translated_text", "")
                                    
                                    # 检查这个结果是否已经添加过
                                    if not any(
                                        t["bounding_box"] == bounding_box and 
                                        t["original_text"] == original_text and 
                                        t["translated_text"] == translated_text 
                                        for t in self.translations
                                    ):
                                        # 添加到翻译结果列表
                                        self.translations.append({
                                            "bounding_box": bounding_box,
                                            "original_text": original_text,
                                            "translated_text": translated_text
                                        })
                                        
                                        # 更新表格 - 使用换行符保留多行文本
                                        self.results_tree.insert(
                                            "", "end", 
                                            values=(str(bounding_box), original_text, translated_text)
                                        )
                                        
                                        # 绘制边界框
                                        self.draw_bounding_boxes()
                            except json.JSONDecodeError:
                                # 不是有效的JSON，继续收集
                                pass
                    
                    self.root.update()
                    time.sleep(0.01)  # Small delay to ensure UI updates
            
            # 最终处理，确保所有内容都被解析
            self.process_jsonl_response(collected_messages)
            
            # 处理完成
            self.update_status("Done")
            
        except Exception as e:
            self.update_status("Error")
            self.log(f"Translation error: {str(e)}")
    
    def process_jsonl_response(self, jsonl_text):
        # 尝试找出所有可能的JSON对象
        potential_objects = re.findall(r'({.*?})', jsonl_text, re.DOTALL)
        
        for obj_str in potential_objects:
            try:
                item = json.loads(obj_str)
                
                # 确保是我们期望的格式
                if "bounding_box" in item and "original_text" in item and "translated_text" in item:
                    bounding_box = item.get("bounding_box", [])
                    original_text = item.get("original_text", "")
                    translated_text = item.get("translated_text", "")
                    
                    # 检查这个结果是否已经添加过
                    if not any(
                        t["bounding_box"] == bounding_box and 
                        t["original_text"] == original_text and 
                        t["translated_text"] == translated_text 
                        for t in self.translations
                    ):
                        # 添加到翻译结果列表
                        self.translations.append({
                            "bounding_box": bounding_box,
                            "original_text": original_text,
                            "translated_text": translated_text
                        })
                        
                        # 更新表格
                        self.results_tree.insert(
                            "", "end", 
                            values=(str(bounding_box), original_text, translated_text)
                        )
                        
                        # 绘制边界框
                        self.draw_bounding_boxes()
            except json.JSONDecodeError:
                continue
            
if __name__ == "__main__":
    root = tk.Tk()
    app = ComicTranslator(root)
    root.mainloop() 