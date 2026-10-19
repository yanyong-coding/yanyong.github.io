import sys
import json
import time
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import re
import os

# 尝试导入markdown库，如果不存在则安装
try:
    import markdown
except ImportError:
    print("未找到markdown库，正在尝试安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown"])
    import markdown

class HexoBlogManager:
    def __init__(self, root):
        # 设置中文字体支持
        self.root = root
        self.root.title("Hexo 博客管理工具")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # 博客根目录
        self.blog_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.posts_dir = os.path.join(self.blog_root, "source", "_posts")
        self.images_dir = os.path.join(self.blog_root, "source", "images")
        
        # 确保图片目录存在
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
        
        # 当前编辑的文章
        self.current_post = None
        
        # 创建界面
        self.create_ui()
        # 加载文章列表
        self.load_posts()
    
    def create_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建左侧文章列表区域
        left_frame = ttk.LabelFrame(main_frame, text="文章列表")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5, ipadx=5, ipady=5)
        
        # 文章列表
        columns = ("title", "date", "categories")
        self.posts_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=30)
        
        # 设置列宽和标题
        self.posts_tree.heading("title", text="标题")
        self.posts_tree.column("title", width=200, anchor=tk.W)
        self.posts_tree.heading("date", text="日期")
        self.posts_tree.column("date", width=120, anchor=tk.CENTER)
        self.posts_tree.heading("categories", text="分类")
        self.posts_tree.column("categories", width=100, anchor=tk.W)
        
        self.posts_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 绑定双击事件
        self.posts_tree.bind("<Double-1>", self.edit_post)
        
        # 左侧按钮区域
        buttons_frame = ttk.Frame(left_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.new_button = ttk.Button(buttons_frame, text="新建文章", command=self.new_post)
        self.new_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.edit_button = ttk.Button(buttons_frame, text="编辑文章", command=self.edit_post)
        self.edit_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.delete_button = ttk.Button(buttons_frame, text="删除文章", command=self.delete_post)
        self.delete_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.refresh_button = ttk.Button(buttons_frame, text="刷新列表", command=self.load_posts)
        self.refresh_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 创建右侧编辑区域
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 文章信息区域
        info_frame = ttk.LabelFrame(right_frame, text="文章信息")
        info_frame.pack(fill=tk.X, padx=5, pady=5, ipadx=5, ipady=5)
        
        # 标题
        ttk.Label(info_frame, text="标题: ").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.title_entry = ttk.Entry(info_frame, width=50)
        self.title_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 日期
        ttk.Label(info_frame, text="日期: ").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_entry = ttk.Entry(info_frame, width=50)
        self.date_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 分类
        ttk.Label(info_frame, text="分类: ").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.categories_entry = ttk.Entry(info_frame, width=50)
        self.categories_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 标签
        ttk.Label(info_frame, text="标签: ").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.tags_entry = ttk.Entry(info_frame, width=50)
        self.tags_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        self.tags_entry.insert(0, "用逗号分隔多个标签")
        
        # 封面
        ttk.Label(info_frame, text="封面: ").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.cover_entry = ttk.Entry(info_frame, width=40)
        self.cover_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        self.cover_button = ttk.Button(info_frame, text="选择图片", command=self.select_cover)
        self.cover_button.grid(row=4, column=2, padx=5, pady=5)
        
        # 编辑工具栏
        self.toolbar_frame = ttk.Frame(right_frame)
        self.toolbar_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.bold_button = ttk.Button(self.toolbar_frame, text="粗体", command=lambda: self.format_text("**粗体文本**"))
        self.bold_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.italic_button = ttk.Button(self.toolbar_frame, text="斜体", command=lambda: self.format_text("*斜体文本*"))
        self.italic_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.header_button = ttk.Button(self.toolbar_frame, text="标题", command=self.insert_header)
        self.header_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.quote_button = ttk.Button(self.toolbar_frame, text="引用", command=lambda: self.format_text("> 引用文本"))
        self.quote_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.hr_button = ttk.Button(self.toolbar_frame, text="分割线", command=lambda: self.format_text("\n---\n"))
        self.hr_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.link_button = ttk.Button(self.toolbar_frame, text="链接", command=self.insert_link)
        self.link_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.image_button = ttk.Button(self.toolbar_frame, text="插入图片", command=self.insert_image)
        self.image_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.code_button = ttk.Button(self.toolbar_frame, text="代码块", command=self.insert_code_block)
        self.code_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.preview_button = ttk.Button(self.toolbar_frame, text="预览", command=self.preview_post)
        self.preview_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        # 添加列表相关按钮
        self.ul_button = ttk.Button(self.toolbar_frame, text="无序列表", command=self.insert_unordered_list)
        self.ul_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.ol_button = ttk.Button(self.toolbar_frame, text="有序列表", command=self.insert_ordered_list)
        self.ol_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        # 添加更多常用按钮
        self.table_button = ttk.Button(self.toolbar_frame, text="表格", command=self.insert_table)
        self.table_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.task_button = ttk.Button(self.toolbar_frame, text="任务列表", command=self.insert_task_list)
        self.task_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.strikethrough_button = ttk.Button(self.toolbar_frame, text="删除线", command=lambda: self.format_text("~~删除线文本~~"))
        self.strikethrough_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.inline_code_button = ttk.Button(self.toolbar_frame, text="代码行", command=lambda: self.format_text("`代码`"))
        self.inline_code_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        # 文章内容编辑区域
        content_frame = ttk.LabelFrame(right_frame, text="文章内容")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5, ipadx=5, ipady=5)
        
        self.content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, font=("SimHei", 10))
        self.content_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 底部按钮区域
        bottom_frame = ttk.Frame(right_frame)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.save_button = ttk.Button(bottom_frame, text="保存文章", command=self.save_post)
        self.save_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Hexo 命令区域
        hexo_frame = ttk.LabelFrame(right_frame, text="Hexo 命令")
        hexo_frame.pack(fill=tk.X, padx=5, pady=5, ipadx=5, ipady=5)
        
        self.server_button = ttk.Button(hexo_frame, text="启动本地服务器 (hexo s)", command=self.start_server_with_port)
        self.server_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.build_button = ttk.Button(hexo_frame, text="生成静态文件 (hexo g)", command=lambda: self.run_hexo_command("build"))
        self.build_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.clean_button = ttk.Button(hexo_frame, text="清理缓存 (hexo clean)", command=lambda: self.run_hexo_command("clean"))
        self.clean_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.deploy_button = ttk.Button(hexo_frame, text="部署网站 (hexo d)", command=lambda: self.run_hexo_command("deploy"))
        self.deploy_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 输出区域
        output_frame = ttk.LabelFrame(right_frame, text="命令输出")
        output_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5, ipadx=5, ipady=5)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=5, font=("SimHei", 10))
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.output_text.config(state=tk.DISABLED)
    
    def load_posts(self):
        # 清空文章列表
        for item in self.posts_tree.get_children():
            self.posts_tree.delete(item)
        
        # 读取文章目录
        try:
            files = [f for f in os.listdir(self.posts_dir) if f.endswith('.md')]
            posts = []
            
            for file in files:
                file_path = os.path.join(self.posts_dir, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 解析 front matter
                        post_info = self.parse_front_matter(content, file)
                        posts.append(post_info)
                except Exception as e:
                    self.log(f"读取文章 {file} 出错: {str(e)}")
            
            # 按日期排序，最新的在前
            posts.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
            
            # 添加到列表
            for post in posts:
                self.posts_tree.insert("", tk.END, values=(post['title'], post['date'], post['categories']), tags=(post['file'],))
        except Exception as e:
            self.log(f"加载文章列表出错: {str(e)}")
            messagebox.showerror("错误", f"加载文章列表出错: {str(e)}")
    
    def parse_front_matter(self, content, filename):
        # 默认信息
        post_info = {
            'file': filename,
            'title': filename[:-3],  # 去掉 .md 扩展名
            'date': '',
            'categories': '未分类',
            'tags': [],
            'cover': '',
            'content': content
        }
        
        # 尝试解析 front matter
        front_matter_match = re.search(r'^---[\s\S]*?---', content)
        if front_matter_match:
            front_matter = front_matter_match.group(0)
            # 提取正文内容
            content_part = content[front_matter_match.end():].strip()
            post_info['content'] = content_part
            
            # 解析 front matter 中的各个字段
            front_matter_lines = front_matter[3:-3].strip().split('\n')
            
            for line in front_matter_lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 去除引号
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    if key == 'title':
                        post_info['title'] = value
                    elif key == 'date':
                        post_info['date'] = value
                    elif key == 'categories':
                        post_info['categories'] = value
                    elif key == 'tags':
                        # 解析标签数组
                        if value.startswith('[') and value.endswith(']'):
                            # 尝试解析 JSON 格式
                            try:
                                # 替换中文逗号为英文逗号
                                value = value.replace('，', ',')
                                tags = json.loads(value)
                                post_info['tags'] = tags
                            except:
                                # 如果解析失败，尝试简单拆分
                                tags = [tag.strip() for tag in value[1:-1].split(',')]
                                post_info['tags'] = tags
                    elif key == 'cover':
                        post_info['cover'] = value
        
        return post_info
    
    def preview_post(self):
        """预览当前编辑的文章 - 仅显示Markdown源码"""
        # 获取文章内容
        title = self.title_entry.get().strip()
        date = self.date_entry.get().strip()
        categories = self.categories_entry.get().strip()
        tags = self.tags_entry.get().strip()
        cover = self.cover_entry.get().strip()
        content = self.content_text.get(1.0, tk.END).strip()
        
        # 创建预览窗口
        preview_window = ttk.Toplevel(self.root)
        preview_window.title("文章预览")
        preview_window.geometry("1000x700")
        
        # 创建内容框架
        content_frame = ttk.Frame(preview_window)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 如果没有内容，显示提示信息
        if not title and not content:
            no_content_label = ttk.Label(content_frame, text="暂无内容可预览")
            no_content_label.pack(fill=tk.BOTH, expand=True)
            return
            
        try:
            # 创建Markdown源码预览组件
            md_preview = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, font=("SimHei", 10))
            
            # 构建完整的Markdown内容，包括front matter
            full_content = f"---\ntitle: {title}\ndate: {date}\ncategories: {categories}\ntags: [{tags}]\ncover: {cover}\n---\n\n{content}"
            md_preview.insert(tk.END, full_content)
            md_preview.config(state=tk.DISABLED)
            md_preview.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            # 如果预览失败，显示错误信息
            error_preview = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, font=("SimHei", 10))
            error_preview.insert(tk.END, f"预览失败: {str(e)}")
            error_preview.config(state=tk.DISABLED)
            error_preview.pack(fill=tk.BOTH, expand=True)
    
    def new_post(self):
        """新建一篇文章，带默认模板"""
        # 清空编辑区域
        self.clear_edit_area()
        # 设置当前时间
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, now)
        # 设置默认分类
        self.categories_entry.delete(0, tk.END)
        self.categories_entry.insert(0, "技术")
        # 设置默认标签
        self.tags_entry.delete(0, tk.END)
        self.tags_entry.insert(0, "hexo, blog")
        # 设置为新建模式
        self.current_post = None
        # 添加文章模板
        template = """# 标题

## 副标题

### 内容开始

这里是文章正文内容。可以使用Markdown语法格式化你的文章：

**粗体文本**

*斜体文本*

[链接文字](链接地址)

> 引用内容

列表项：
- 项目1
- 项目2
- 项目3

代码块：
```python
# 这里是代码
print("Hello World")
```

插入图片：
![图片描述](图片路径)"""
        self.content_text.delete(1.0, tk.END)
        self.content_text.insert(tk.END, template)
        # 聚焦到标题输入框
        self.title_entry.focus()
    
    def run_hexo_command(self, command, extra_args=''):
        # 验证命令
        valid_commands = {'server': 's', 'build': 'g', 'clean': 'clean', 'deploy': 'd'}
        if command not in valid_commands:
            messagebox.showerror("错误", "不支持的命令")
            return
        
        # 清空输出区域
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        
        # 启动新线程执行命令
        import threading
        threading.Thread(target=self._execute_command, args=(command, extra_args), daemon=True).start()
        
    def start_server_with_port(self):
        """启动带自定义端口的Hexo服务器"""
        # 检查端口4000是否被占用
        def is_port_in_use(port):
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('localhost', port)) == 0
        
        # 如果端口4000被占用，自动选择一个可用端口
        default_port = "4000"
        if is_port_in_use(4000):
            # 尝试使用4001-4010之间的端口
            for port in range(4001, 4011):
                if not is_port_in_use(port):
                    default_port = str(port)
                    break
        
        # 创建端口选择对话框
        port_window = tk.Toplevel(self.root)
        port_window.title("选择服务器端口")
        port_window.geometry("300x150")
        port_window.resizable(False, False)
        
        # 居中显示
        port_window.update_idletasks()
        width = port_window.winfo_width()
        height = port_window.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        port_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 端口输入框
        ttk.Label(port_window, text="请输入服务器端口号:").pack(pady=10)
        port_var = tk.StringVar(value=default_port)
        port_entry = ttk.Entry(port_window, textvariable=port_var, width=10)
        port_entry.pack(pady=5)
        port_entry.focus()
        
        # 提示信息
        status_text = "(端口4000可用)" if default_port == "4000" else "(端口4000被占用，已选择可用端口)"
        ttk.Label(port_window, text=status_text).pack(pady=5)
        
        # 确认按钮
        def on_ok():
            try:
                port = int(port_var.get())
                if port < 1024 or port > 65535:
                    messagebox.showerror("错误", "端口号必须在1024-65535之间")
                    return
                self.run_hexo_command("server", f"-p {port}")
                port_window.destroy()
            except ValueError:
                messagebox.showerror("错误", "请输入有效的端口号")
        
        # 绑定回车和按钮点击
        port_window.bind('<Return>', lambda event: on_ok())
        ttk.Button(port_window, text="确定", command=on_ok).pack(pady=10)
    
    def _execute_command(self, command, extra_args=''):
        # 执行 Hexo 命令
        hexo_cmd = f"hexo {command} {extra_args}"
        self.log(f"开始执行命令: {hexo_cmd}")
        
        try:
            # 使用 cmd.exe 在博客根目录执行命令
            process = subprocess.Popen(
                f"cmd /c cd /d \"{self.blog_root}\" && {hexo_cmd}",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # 实时显示输出
            for line in process.stdout:
                self.log(line.strip())
            
            # 等待命令完成
            process.wait()
            
            if process.returncode == 0:
                self.log(f"命令执行成功: {hexo_cmd}")
                # 如果是启动服务器，显示提示
                if command == 's' or command == 'server':
                    # 提取端口号
                    import re
                    port_match = re.search(r'-p (\d+)', extra_args)
                    port = port_match.group(1) if port_match else '4000'
                    self.log(f"\n本地服务器已启动，请访问 http://localhost:{port} 查看\n按 Ctrl+C 可以停止服务器")
            else:
                self.log(f"命令执行失败，返回代码: {process.returncode}")
        except Exception as e:
            self.log(f"执行命令出错: {str(e)}")
    
    def log(self, message):
        # 在输出区域显示消息
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
        # 同时输出到控制台
        print(message)
    
    def clear_edit_area(self):
        # 清空编辑区域
        self.title_entry.delete(0, tk.END)
        self.date_entry.delete(0, tk.END)
        self.categories_entry.delete(0, tk.END)
        self.tags_entry.delete(0, tk.END)
        self.tags_entry.insert(0, "用逗号分隔多个标签")
        self.cover_entry.delete(0, tk.END)
        self.content_text.delete(1.0, tk.END)
        
    def edit_post(self, event=None):
        """编辑选中的文章"""
        selected_item = self.posts_tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "请先选择一篇文章")
            return
        
        # 获取选中文章的文件信息
        item = selected_item[0]
        file_name = self.posts_tree.item(item, "tags")[0]
        file_path = os.path.join(self.posts_dir, file_name)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 解析 front matter
                post_info = self.parse_front_matter(content, file_name)
                
                # 清空编辑区域
                self.clear_edit_area()
                
                # 填充文章信息
                self.title_entry.insert(0, post_info['title'])
                self.date_entry.insert(0, post_info['date'])
                self.categories_entry.insert(0, post_info['categories'])
                
                # 处理标签
                if post_info['tags']:
                    tags_str = ', '.join(post_info['tags'])
                    self.tags_entry.delete(0, tk.END)
                    self.tags_entry.insert(0, tags_str)
                
                self.cover_entry.insert(0, post_info['cover'])
                self.content_text.insert(tk.END, post_info['content'])
                
                # 设置当前编辑的文章
                self.current_post = file_path
        except Exception as e:
            self.log(f"读取文章出错: {str(e)}")
            messagebox.showerror("错误", f"读取文章出错: {str(e)}")
    
    def save_post(self):
        """保存当前编辑的文章"""
        # 获取文章信息
        title = self.title_entry.get().strip()
        date = self.date_entry.get().strip()
        categories = self.categories_entry.get().strip()
        tags = self.tags_entry.get().strip()
        cover = self.cover_entry.get().strip()
        content = self.content_text.get(1.0, tk.END).strip()
        
        # 验证必填项
        if not title:
            messagebox.showinfo("提示", "请输入文章标题")
            return
        
        if not content:
            messagebox.showinfo("提示", "请输入文章内容")
            return
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 生成文件名
        if self.current_post:
            # 如果是编辑已有文章，使用原有文件名
            file_path = self.current_post
        else:
            # 如果是新建文章，生成新文件名
            # 从日期提取年月日
            date_part = date.split(' ')[0]  # 获取日期部分 YYYY-MM-DD
            # 将标题中的特殊字符替换为下划线
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
            # 生成文件名
            file_name = f"{date_part}-{safe_title}.md"
            file_path = os.path.join(self.posts_dir, file_name)
        
        # 构建完整的文章内容，包括 front matter
        front_matter = f"---\ntitle: {title}\ndate: {date}\n"
        if categories:
            front_matter += f"categories: {categories}\n"
        if tags:
            # 格式化标签为 JSON 数组格式
            # 替换中文逗号
            tags = tags.replace('，', ',')
            # 分割并去除空白
            tag_list = [tag.strip() for tag in tags.split(',')]
            # 转换为 JSON 格式字符串
            tags_json = json.dumps(tag_list, ensure_ascii=False)
            front_matter += f"tags: {tags_json}\n"
        if cover:
            front_matter += f"cover: {cover}\n"
        front_matter += f"---\n\n"
        
        full_content = front_matter + content
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            # 重新加载文章列表
            self.load_posts()
            
            messagebox.showinfo("成功", "文章保存成功")
        except Exception as e:
            self.log(f"保存文章出错: {str(e)}")
            messagebox.showerror("错误", f"保存文章出错: {str(e)}")
    
    def delete_post(self):
        """删除选中的文章"""
        selected_item = self.posts_tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "请先选择一篇文章")
            return
        
        # 获取选中文章的文件信息
        item = selected_item[0]
        file_name = self.posts_tree.item(item, "tags")[0]
        file_path = os.path.join(self.posts_dir, file_name)
        
        # 确认删除
        if messagebox.askyesno("确认", f"确定要删除文章 '{self.posts_tree.item(item, 'values')[0]}' 吗？"):
            try:
                os.remove(file_path)
                # 重新加载文章列表
                self.load_posts()
                # 如果当前正在编辑的文章被删除，清空编辑区域
                if self.current_post and os.path.abspath(self.current_post) == os.path.abspath(file_path):
                    self.clear_edit_area()
                    self.current_post = None
                
                messagebox.showinfo("成功", "文章删除成功")
            except Exception as e:
                self.log(f"删除文章出错: {str(e)}")
                messagebox.showerror("错误", f"删除文章出错: {str(e)}")
    
    def select_cover(self):
        """选择封面图片"""
        file_path = filedialog.askopenfilename(
            title="选择封面图片",
            filetypes=[("图片文件", "*.jpg;*.jpeg;*.png;*.gif")]
        )
        
        if file_path:
            # 复制图片到 images 目录
            try:
                # 获取文件名
                file_name = os.path.basename(file_path)
                # 目标路径
                dest_path = os.path.join(self.images_dir, file_name)
                
                # 复制文件
                import shutil
                shutil.copy2(file_path, dest_path)
                
                # 设置封面路径（相对于 source 目录）
                relative_path = f"/images/{file_name}"
                self.cover_entry.delete(0, tk.END)
                self.cover_entry.insert(0, relative_path)
            except Exception as e:
                self.log(f"复制图片出错: {str(e)}")
                messagebox.showerror("错误", f"复制图片出错: {str(e)}")
    
    def format_text(self, format_str):
        """格式化选中的文本"""
        try:
            # 获取选中文本的范围
            start = self.content_text.index(tk.SEL_FIRST)
            end = self.content_text.index(tk.SEL_LAST)
            # 获取选中文本
            selected_text = self.content_text.get(start, end)
            # 格式化文本
            formatted_text = format_str.replace("粗体文本", selected_text).replace("斜体文本", selected_text)
            # 替换选中文本
            self.content_text.delete(start, end)
            self.content_text.insert(start, formatted_text)
        except tk.TclError:
            # 如果没有选中的文本，直接插入格式化模板
            self.content_text.insert(tk.INSERT, format_str)
    
    def insert_header(self):
        """插入标题"""
        # 创建标题选择对话框
        header_window = tk.Toplevel(self.root)
        header_window.title("插入标题")
        header_window.geometry("250x150")
        header_window.resizable(False, False)
        
        # 居中显示
        header_window.update_idletasks()
        width = header_window.winfo_width()
        height = header_window.winfo_height()
        x = (header_window.winfo_screenwidth() // 2) - (width // 2)
        y = (header_window.winfo_screenheight() // 2) - (height // 2)
        header_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        ttk.Label(header_window, text="选择标题级别:").pack(pady=10)
        
        # 创建按钮框架
        buttons_frame = ttk.Frame(header_window)
        buttons_frame.pack(pady=10)
        
        for i in range(1, 7):
            ttk.Button(
                buttons_frame,
                text=f"H{i}",
                width=5,
                command=lambda level=i: self._insert_header_level(level, header_window)
            ).pack(side=tk.LEFT, padx=5)
    
    def _insert_header_level(self, level, window):
        """插入指定级别的标题"""
        header_mark = '#' * level
        header_text = f"\n{header_mark} 标题内容\n"
        self.content_text.insert(tk.INSERT, header_text)
        window.destroy()
    
    def insert_link(self):
        """插入链接"""
        # 获取选中的文本（如果有）
        try:
            start = self.content_text.index(tk.SEL_FIRST)
            end = self.content_text.index(tk.SEL_LAST)
            selected_text = self.content_text.get(start, end)
        except tk.TclError:
            selected_text = "链接文字"
        
        # 创建链接对话框
        link_window = tk.Toplevel(self.root)
        link_window.title("插入链接")
        link_window.geometry("400x200")
        link_window.resizable(False, False)
        
        # 居中显示
        link_window.update_idletasks()
        width = link_window.winfo_width()
        height = link_window.winfo_height()
        x = (link_window.winfo_screenwidth() // 2) - (width // 2)
        y = (link_window.winfo_screenheight() // 2) - (height // 2)
        link_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 链接文本输入框
        ttk.Label(link_window, text="链接文本:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        text_entry = ttk.Entry(link_window, width=30)
        text_entry.grid(row=0, column=1, padx=10, pady=10)
        text_entry.insert(0, selected_text)
        
        # 链接地址输入框
        ttk.Label(link_window, text="链接地址:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        url_entry = ttk.Entry(link_window, width=30)
        url_entry.grid(row=1, column=1, padx=10, pady=10)
        url_entry.insert(0, "https://")
        
        # 确定按钮
        def on_ok():
            text = text_entry.get().strip()
            url = url_entry.get().strip()
            if text and url:
                # 如果有选中文本，替换选中文本
                try:
                    start = self.content_text.index(tk.SEL_FIRST)
                    end = self.content_text.index(tk.SEL_LAST)
                    self.content_text.delete(start, end)
                    self.content_text.insert(start, f"[{text}]({url})")
                except tk.TclError:
                    # 否则直接插入
                    self.content_text.insert(tk.INSERT, f"[{text}]({url})")
                link_window.destroy()
        
        # 创建按钮框架
        buttons_frame = ttk.Frame(link_window)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=link_window.destroy).pack(side=tk.LEFT, padx=10)
    
    def insert_image(self):
        """插入图片"""
        # 获取选中的文本（如果有）作为图片描述
        try:
            start = self.content_text.index(tk.SEL_FIRST)
            end = self.content_text.index(tk.SEL_LAST)
            selected_text = self.content_text.get(start, end)
        except tk.TclError:
            selected_text = "图片描述"
        
        # 选择图片文件
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg;*.jpeg;*.png;*.gif")]
        )
        
        if file_path:
            # 复制图片到 images 目录
            try:
                # 获取文件名
                file_name = os.path.basename(file_path)
                # 目标路径
                dest_path = os.path.join(self.images_dir, file_name)
                
                # 复制文件
                import shutil
                shutil.copy2(file_path, dest_path)
                
                # 插入图片Markdown代码
                image_code = f"![{selected_text}](/images/{file_name})"
                # 如果有选中文本，替换选中文本
                try:
                    start = self.content_text.index(tk.SEL_FIRST)
                    end = self.content_text.index(tk.SEL_LAST)
                    self.content_text.delete(start, end)
                    self.content_text.insert(start, image_code)
                except tk.TclError:
                    # 否则直接插入
                    self.content_text.insert(tk.INSERT, image_code)
            except Exception as e:
                self.log(f"插入图片出错: {str(e)}")
                messagebox.showerror("错误", f"插入图片出错: {str(e)}")
    
    def insert_code_block(self):
        """插入代码块"""
        # 创建代码语言选择对话框
        code_window = tk.Toplevel(self.root)
        code_window.title("插入代码块")
        code_window.geometry("300x150")
        code_window.resizable(False, False)
        
        # 居中显示
        code_window.update_idletasks()
        width = code_window.winfo_width()
        height = code_window.winfo_height()
        x = (code_window.winfo_screenwidth() // 2) - (width // 2)
        y = (code_window.winfo_screenheight() // 2) - (height // 2)
        code_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        ttk.Label(code_window, text="选择代码语言:").pack(pady=10)
        
        # 代码语言选择
        languages = ["python", "javascript", "java", "c++", "c#", "html", "css", "bash", "markdown", "none"]
        language_var = tk.StringVar(value="python")
        language_combo = ttk.Combobox(code_window, textvariable=language_var, values=languages, width=15)
        language_combo.pack(pady=5)
        
        # 确定按钮
        def on_ok():
            language = language_var.get()
            code_block = f"\n```" + (language if language != "none" else "") + "\n# 这里是代码\n```\n"
            # 如果有选中文本，替换选中文本
            try:
                start = self.content_text.index(tk.SEL_FIRST)
                end = self.content_text.index(tk.SEL_LAST)
                selected_text = self.content_text.get(start, end)
                if selected_text:
                    code_block = f"\n```" + (language if language != "none" else "") + f"\n{selected_text}\n```\n"
                self.content_text.delete(start, end)
                self.content_text.insert(start, code_block)
            except tk.TclError:
                # 否则直接插入
                self.content_text.insert(tk.INSERT, code_block)
            code_window.destroy()
        
        # 创建按钮框架
        buttons_frame = ttk.Frame(code_window)
        buttons_frame.pack(pady=10)
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=code_window.destroy).pack(side=tk.LEFT, padx=10)

    def insert_unordered_list(self):
        """插入无序列表"""
        # 获取选中的文本（如果有）
        try:
            start = self.content_text.index(tk.SEL_FIRST)
            end = self.content_text.index(tk.SEL_LAST)
            selected_text = self.content_text.get(start, end)
            
            if selected_text:
                # 如果有选中文本，按换行符分割并为每行添加列表标记
                lines = selected_text.split('\n')
                ul_text = "\n" + "\n".join([f"- {line}" if line.strip() else line for line in lines]) + "\n"
                self.content_text.delete(start, end)
                self.content_text.insert(start, ul_text)
            else:
                # 否则插入默认列表项
                self.content_text.insert(tk.INSERT, "\n- 列表项1\n- 列表项2\n- 列表项3\n")
        except tk.TclError:
            # 没有选中的文本，插入默认列表项
            self.content_text.insert(tk.INSERT, "\n- 列表项1\n- 列表项2\n- 列表项3\n")
    
    def insert_ordered_list(self):
        """插入有序列表"""
        # 获取选中的文本（如果有）
        try:
            start = self.content_text.index(tk.SEL_FIRST)
            end = self.content_text.index(tk.SEL_LAST)
            selected_text = self.content_text.get(start, end)
            
            if selected_text:
                # 如果有选中文本，按换行符分割并为每行添加序号
                lines = selected_text.split('\n')
                ol_text = "\n"
                for i, line in enumerate(lines, 1):
                    if line.strip():
                        ol_text += f"{i}. {line}\n"
                    else:
                        ol_text += "\n"
                self.content_text.delete(start, end)
                self.content_text.insert(start, ol_text)
            else:
                # 否则插入默认有序列表项
                self.content_text.insert(tk.INSERT, "\n1. 第一项\n2. 第二项\n3. 第三项\n")
        except tk.TclError:
            # 没有选中的文本，插入默认有序列表项
            self.content_text.insert(tk.INSERT, "\n1. 第一项\n2. 第二项\n3. 第三项\n")
    
    def insert_table(self):
        """插入表格"""
        # 创建表格选择对话框
        table_window = tk.Toplevel(self.root)
        table_window.title("插入表格")
        table_window.geometry("300x200")
        table_window.resizable(False, False)
        
        # 居中显示
        table_window.update_idletasks()
        width = table_window.winfo_width()
        height = table_window.winfo_height()
        x = (table_window.winfo_screenwidth() // 2) - (width // 2)
        y = (table_window.winfo_screenheight() // 2) - (height // 2)
        table_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 行数输入
        ttk.Label(table_window, text="行数: ").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        rows_var = tk.StringVar(value="3")
        rows_entry = ttk.Entry(table_window, textvariable=rows_var, width=5)
        rows_entry.grid(row=0, column=1, padx=10, pady=10)
        
        # 列数输入
        ttk.Label(table_window, text="列数: ").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        cols_var = tk.StringVar(value="3")
        cols_entry = ttk.Entry(table_window, textvariable=cols_var, width=5)
        cols_entry.grid(row=1, column=1, padx=10, pady=10)
        
        # 确定按钮
        def on_ok():
            try:
                rows = int(rows_var.get())
                cols = int(cols_var.get())
                
                if rows < 1 or cols < 1:
                    messagebox.showerror("错误", "行数和列数必须大于0")
                    return
                
                # 构建表格
                table_text = "\n"
                # 表头
                header = "|" + "|" + "|".join([f"表头{i+1}" for i in range(cols)]) + "|\n"
                table_text += header
                # 分隔线
                separator = "|" + "|" + "|".join(["---" for _ in range(cols)]) + "|\n"
                table_text += separator
                # 表格内容
                for i in range(rows):
                    row = "|" + "|" + "|".join([f"单元格{i+1}-{j+1}" for j in range(cols)]) + "|\n"
                    table_text += row
                
                self.content_text.insert(tk.INSERT, table_text)
                table_window.destroy()
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字")
        
        # 创建按钮框架
        buttons_frame = ttk.Frame(table_window)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=table_window.destroy).pack(side=tk.LEFT, padx=10)
    
    def insert_task_list(self):
        """插入任务列表"""
        # 获取选中的文本（如果有）
        try:
            start = self.content_text.index(tk.SEL_FIRST)
            end = self.content_text.index(tk.SEL_LAST)
            selected_text = self.content_text.get(start, end)
            
            if selected_text:
                # 如果有选中文本，按换行符分割并为每行添加任务列表标记
                lines = selected_text.split('\n')
                task_text = "\n" + "\n".join([f"- [ ] {line}" if line.strip() else line for line in lines]) + "\n"
                self.content_text.delete(start, end)
                self.content_text.insert(start, task_text)
            else:
                # 否则插入默认任务列表项
                self.content_text.insert(tk.INSERT, "\n- [ ] 待办事项1\n- [ ] 待办事项2\n- [ ] 待办事项3\n")
        except tk.TclError:
            # 没有选中的文本，插入默认任务列表项
            self.content_text.insert(tk.INSERT, "\n- [ ] 待办事项1\n- [ ] 待办事项2\n- [ ] 待办事项3\n")

if __name__ == "__main__":
    # 确保中文显示正常
    root = tk.Tk()
    # 启动应用程序
    app = HexoBlogManager(root)
    root.mainloop()