import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager  
from faker import Faker
import threading
import json
import os
import random
import time
import queue
import platform
import atexit
import subprocess
import base64
import undetected_chromedriver as uc
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from seleniumwire import webdriver
import uuid
import shutil

# Sử dụng webdriver_manager để tự động tải driver phù hợp với phiên bản Chrome hiện tại
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Ẩn cửa sổ Chrome
options.add_argument("--disable-gpu")  # Vô hiệu hóa GPU (thường sử dụng khi chạy headless)
options.add_argument("--no-sandbox")  # Không sử dụng sandbox (thường cần khi chạy trong môi trường không đồ họa)
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Tạo sự kiện để đồng bộ hóa việc đóng profile
close_event = threading.Event()
# Tạo đối tượng lock toàn cục
driver_lock = threading.Lock()
# Tạo queue để giao tiếp giữa các luồng
update_queue = queue.Queue()
controller_driver = None
controlled_drivers = []

# Tạo cửa sổ chính
root = tk.Tk()
root.title("Quản lý Profile")
fake = Faker()
profiles = []

def generate_fingerprint():
    # Dùng uuid để tạo giá trị ngẫu nhiên độc nhất cho mỗi profile
    unique_seed = uuid.uuid4().hex  # UUID4 tạo ra một chuỗi ngẫu nhiên

    # Canvas Hash
    canvas_hash = f"Canvas Hash: {int(unique_seed[:16], 16)}"  # Lấy 16 ký tự đầu tiên từ uuid làm seed

    # WebGL Fingerprinting
    webgl_vendor = random.choice(["Intel Inc.", "Google Inc.", "AMD", "NVIDIA Corporation"])
    webgl_renderer = random.choice([
        "Intel Iris OpenGL Engine",
        "ANGLE (Intel, Intel(R) HD Graphics 530 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "AMD Radeon Pro 580 OpenGL Engine",
        "NVIDIA GeForce GTX 1070 OpenGL Engine"
    ])
    webgl_hash = f"WebGL Vendor: {webgl_vendor}, Renderer: {webgl_renderer}"

    # Audio Hash
    audio_hash = f"Audio Hash: {int(unique_seed[16:32], 16)}"  # Dùng phần tiếp theo của uuid

    # Timezone and Language
    timezone = fake.timezone()
    language = fake.language_code()

    return f"{canvas_hash}; {webgl_hash}; {audio_hash}; Timezone: {timezone}; Language: {language}"

def get_chrome_version():
    """Lấy phiên bản Chrome đang cài trên máy."""
    try:
        if platform.system() == "Windows":
            # Đối với Windows, chúng ta có thể dùng subprocess để gọi lệnh
            output = subprocess.check_output("reg query \"HKCU\\Software\\Google\\Chrome\\BLBeacon\" /v version", shell=True)
            version = output.decode().split()[-1]  # Lấy phiên bản từ output
        elif platform.system() == "Darwin":  # macOS
            output = subprocess.check_output(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"])
            version = output.decode().strip().split()[-1]
        else:  # Linux
            output = subprocess.check_output(["google-chrome", "--version"])
            version = output.decode().strip().split()[-1]
        return version
    except Exception as e:
        print(f"Không thể lấy phiên bản Chrome: {e}")
        return None

import random

def generate_user_agent(chrome_version):
    """Tạo một User-Agent động dựa trên phiên bản Chrome."""
    
    if chrome_version is None:
        # Nếu không cung cấp phiên bản Chrome, sử dụng mặc định
        chrome_version = "91.0.4472.124"
    
    # Các danh sách lựa chọn
    os_list = [
        "Windows NT 10.0; Win64; x64",
        "Windows NT 6.1; Win32; x86",
        "Macintosh; Intel Mac OS X 10_15_7",
        "X11; Ubuntu; Linux x86_64",
        "Android 10; SM-G973F",
        "Android 11; Pixel 5"
    ]
    
    browser_list = [
        f"Chrome/{chrome_version}",
        "Firefox/92.0",
        "Safari/537.36",
        "Edge/94.0.992.31",
        f"Opera/{chrome_version}",
        "Vivaldi/{chrome_version}"
    ]
    
    engine_list = [
        "AppleWebKit/537.36",
        "Gecko/20100101",
        "Blink/537.36"
    ]
    
    device_list = [
        "Mobile Safari/537.36",
        "Tablet Safari/537.36",
        "Desktop"
    ]
    
    # Chọn ngẫu nhiên các phần tử từ danh sách
    os = random.choice(os_list)
    browser = random.choice(browser_list)
    engine = random.choice(engine_list)
    device = random.choice(device_list)
    
    # Tạo ra User-Agent ngẫu nhiên
    user_agent = f"Mozilla/5.0 ({os}) {engine} (KHTML, like Gecko) {browser} {device}"
    
    return user_agent



def setup_driver(profile):
    """Cập nhật driver với user agent động từ phiên bản Chrome."""
    global driver_lock
    try:
        # Lấy phiên bản Chrome đang cài
        chrome_version = get_chrome_version()
        
        options = uc.ChromeOptions()
        
        # Thêm phần tạo user_data_dir
        user_data_dir = os.path.join(os.getcwd(), f"profile_{profile['name']}")
        options.add_argument(f"--user-data-dir={user_data_dir}")
        
        # Tạo User-Agent dựa trên phiên bản Chrome
        profile['user_agent'] = generate_user_agent(chrome_version)
        options.add_argument(f"--user-agent={profile['user_agent']}")

          # Cấu hình proxy
        if profile['proxy']:
            proxy = profile["proxy"]
            proxy_parts = proxy.split(':')
            if len(proxy_parts) == 4:
                ip = proxy_parts[0]
                port = proxy_parts[1]
                username = proxy_parts[2]
                password = proxy_parts[3]
                proxy_address = f'{ip}:{port}'

                # Sử dụng selenium-wire để cấu hình proxy với thông tin xác thực
                wire_options = {
                    'proxy': {
                        'http': f'http://{username}:{password}@{proxy_address}',
                        'https': f'http://{username}:{password}@{proxy_address}',
                        'no_proxy': 'localhost,127.0.0.1'
                    }
                }

                with driver_lock:
                    driver = webdriver.Chrome(options=options, seleniumwire_options=wire_options)
            else:
                options.add_argument(f'--proxy-server={profile["proxy"]}')
                with driver_lock:
                    driver = webdriver.Chrome(options=options,)

        else:
            with driver_lock:
                driver = webdriver.Chrome(options=options,)

        # Thiết lập độ phân giải màn hình ngẫu nhiên
        screen_resolutions = [
            (1920, 1080),
            (1280, 720),
            (1600, 900),
        ]
        resolution = random.choice(screen_resolutions)
        profile['screen_width'], profile['screen_height'] = resolution
        driver.set_window_size(profile['screen_width'], profile['screen_height'])

        # Giả mạo WebRTC để bảo vệ IP thực
        driver.execute_script(f"""
        Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
        window.navigator.mediaDevices.enumerateDevices = () => Promise.resolve([{{kind: 'audioinput'}}, {{kind: 'videoinput'}}]);
        Object.defineProperty(window, 'RTCPeerConnection', {{
            value: class extends window.RTCPeerConnection {{
                constructor(...args) {{
                    super(...args);
                    this.oldAddIceCandidate = this.addIceCandidate;
                    this.addIceCandidate = (iceCandidate, ...rest) => {{
                        if (!iceCandidate || (iceCandidate && !iceCandidate.candidate)) {{
                            return this.oldAddIceCandidate(iceCandidate, ...rest);
                        }}
                        const newCandidate = new RTCIceCandidate({{
                            candidate: iceCandidate.candidate.replace(/(\\d+\\.\\d+\\.\\d+\\.\\d+)/, "{profile['proxy'].split(':')[0]}"),
                            sdpMLineIndex: iceCandidate.sdpMLineIndex,
                            sdpMid: iceCandidate.sdpMid
                        }});
                        return this.oldAddIceCandidate(newCandidate, ...rest);
                    }};
                }}
            }}
        }});
        """)

        # Thêm tiêu đề HTTP ngẫu nhiên
        driver.execute_cdp_cmd(
            'Network.setExtraHTTPHeaders', {
                "headers": {
                    "DNT": "1",
                    "Referer": "https://www.example.com"
                }
            }
        )

        profile['driver'] = driver  # Lưu driver vào profile
        print(f"Profile {profile['name']} is now open with driver {driver}")
        return driver

    except Exception as e:
        print(f"An error occurred while setting up the driver for profile {profile['name']}: {e}")
        return None

def add_profile():
    profile = {
        "name": f"Profile {len(profiles) + 1}",
        "fingerprint": generate_fingerprint(),
        "user_agent": fake.user_agent(),
        "screen_width": fake.random_int(min=800, max=1920),
        "screen_height": fake.random_int(min=600, max=1080),
        "timezone": fake.timezone(),
        "language": fake.language_code(),
        "proxy": "",
        "checked": False,
         "fake_ip": generate_unique_ip()  # Thêm IP giả duy nhất
    }
    profiles.append(profile)
    update_profile_tree()
    save_profiles()

def generate_unique_ip():
    while True:
        ip = fake.ipv4()
        if not any(profile.get('fake_ip') == ip for profile in profiles):
            return ip

# sắp xếp profile
def arrange_and_zoom_profiles():
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    open_profiles = [p for p in profiles if 'driver' in p and p['driver'] is not None]
    num_profiles = len(open_profiles)
    if num_profiles == 0:
        return
    
    # Xác định số lượng cột và hàng
    cols = 4
    rows = (num_profiles + cols - 1) // cols  # Tính số hàng cần thiết

    for index, profile in enumerate(open_profiles):
        driver = profile['driver']
        
        # Tính toán kích thước và vị trí của mỗi cửa sổ
        width = screen_width // cols
        height = screen_height // rows
        x = (index % cols) * width
        y = (index // cols) * height
        
        driver.set_window_position(x, y)
        driver.set_window_size(width, height)

# Đảm bảo hàm `arrange_and_zoom_profiles` được gọi sau khi mở profile
def start_profile(profile):
    if profile.get('driver'):
        messagebox.showinfo("Thông báo", "Profile này đang mở.")
        return
    
    driver = setup_driver(profile)
    if driver:
        profile['driver'] = driver  # Lưu driver vào profile để xác định trạng thái tạm thời
        try:
            driver.get("https://google.com/")
            print(f"Profile {profile['name']} opened and navigated to Google successfully.")

            # Bắt đầu luồng để kiểm tra trạng thái của trình duyệt
            threading.Thread(target=monitor_profile, args=(profile,)).start()

        except Exception as e:
            print(f"An error occurred while navigating the profile: {e}")
            profile['driver'] = None
    else:
        print(f"Failed to open profile {profile['name']}.")
    
    update_profile_tree()
    save_profiles()
     # Gọi hàm sắp xếp và thu phóng sau khi mở profile
    arrange_and_zoom_profiles()

def monitor_profile(profile):
    driver = profile['driver']
    while driver:
        try:
            # Thử lấy URL hiện tại để kiểm tra xem trình duyệt có mở không
            current_url = driver.current_url
        except Exception as e:
            # Nếu có lỗi, có nghĩa là trình duyệt đã bị đóng
            break
        time.sleep(1)
    
    # Khi trình duyệt bị đóng, đặt yêu cầu cập nhật giao diện vào queue
    profile['driver'] = None
    update_queue.put(profile['name'])  # Đặt tên profile vào queue để nhận biết
    print(f"Profile {profile['name']} closed.")

def process_queue():
    try:
        while not update_queue.empty():
            profile_name = update_queue.get_nowait()
            update_profile_tree()
            print(f"Updated profile tree for {profile_name}")
    except queue.Empty:
        pass
    root.after(100, process_queue)  # Tiếp tục kiểm tra queue sau mỗi 100ms

# Bắt đầu kiểm tra queue
root.after(100, process_queue)

def start_selected_profiles():
    selected_items = profile_tree.selection()
    if not selected_items:
        messagebox.showwarning("Chưa chọn", "Bạn chưa chọn profile để chạy.")
    else:
        for item in selected_items:
            index = int(profile_tree.item(item, 'values')[0]) - 1
            profile = profiles[index]
            threading.Thread(target=start_profile, args=(profile,)).start()

def close_selected_profiles():
    selected_items = profile_tree.selection()
    if not selected_items:
        messagebox.showwarning("Chưa chọn", "Bạn chưa chọn profile để đóng.")
    else:
        for item in selected_items:
            index = int(profile_tree.item(item, 'values')[0]) - 1
            profile = profiles[index]
            close_driver(profile)
        update_profile_tree()
        save_profiles()

def save_profiles():
    # Tạo bản sao của profiles và loại bỏ 'driver'
    profiles_copy = []
    for profile in profiles:
        profile_copy = profile.copy()
        if 'driver' in profile_copy:
            del profile_copy['driver']
        profiles_copy.append(profile_copy)
    
    with open('profiles.json', 'w') as f:
        json.dump(profiles_copy, f)

def load_profiles():
    global profiles
    if os.path.exists('profiles.json'):
        with open('profiles.json', 'r') as f:
            profiles = json.load(f)
    for profile in profiles:
        if "name" not in profile:
            profile["name"] = f"Profile {len(profiles) + 1}"
        if "fingerprint" not in profile:
            profile["fingerprint"] = "Custom"
        if "checked" not in profile:
            profile["checked"] = False
        if "status" not in profile:
            profile["status"] = "Đang đóng"
        # Khởi tạo driver bằng None khi tải
        profile["driver"] = None
    update_profile_tree()

def delete_profile():
    global profiles
    selected_items = profile_tree.selection()
    if not selected_items:
        messagebox.showwarning("Chưa chọn", "Bạn chưa chọn profile cần xóa.")
    else:
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa các profile đã chọn không?"):
            try:
                for item in reversed(selected_items):
                    index = int(profile_tree.item(item, 'values')[0]) - 1
                    profile_name = profiles[index]['name']
                    
                    # Xóa thư mục user_data_dir
                    user_data_dir = os.path.join(os.getcwd(), f"profile_{profile_name}")
                    if os.path.exists(user_data_dir):
                        shutil.rmtree(user_data_dir)
                        print(f"User data directory {user_data_dir} has been deleted.")
                    else:
                        print(f"User data directory {user_data_dir} does not exist.")
                    
                    profiles.pop(index)
                update_profile_tree()
                save_profiles()
            except Exception as e:
                print(f"An error occurred while deleting profiles: {e}")
                messagebox.showerror("Lỗi", "Có lỗi xảy ra khi xóa các profile.")

def update_profile_tree():
    profile_tree.delete(*profile_tree.get_children())
    for i, profile in enumerate(profiles):
        status = "Đang mở" if profile.get('driver') else "Đang đóng"
        values = (i + 1, profile["name"], profile["fingerprint"], profile["proxy"], status)
        profile_tree.insert("", "end", iid=i, values=values)
    save_profiles()

def edit_selected_profiles():
    selected_items = profile_tree.selection()
    if not selected_items:
        messagebox.showwarning("Chưa chọn", "Bạn chưa chọn profile để chỉnh sửa.")
    else:
        try:
            new_proxy = simpledialog.askstring(
                "Chỉnh sửa Proxy",
                "Nhập proxy mới cho các profile đã chọn (định dạng: proxy_ip:proxy_port@username:password):"
            )
            if new_proxy:
                for item in selected_items:
                    index = int(profile_tree.item(item, 'values')[0]) - 1
                    profiles[index]["proxy"] = new_proxy
                    # Xóa driver cũ và khởi tạo lại với proxy mới
                    profile = profiles[index]
                    close_driver(profile)
                    setup_driver(profile)  # Tạo lại driver với proxy mới
                update_profile_tree()
                save_profiles()

        except Exception as e:
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi: {e}")
            print(f"An error occurred while editing profiles: {e}")

#Nút đóng profile
def close_profile(profile):
    if not profile.get('driver'):
        messagebox.showinfo("Thông báo", "Profile này đã đóng.")
        return
    
    driver = profile.get('driver')
    if driver:
        try:
            driver.quit()
            profile['driver'] = None
            print(f"Profile {profile['name']} closed.")
        except Exception as e:
            print(f"An error occurred while closing the profile: {e}")
    update_profile_tree()
    save_profiles()

def get_selected_profile():
    selected_items = profile_tree.selection()
    if not selected_items:
        messagebox.showwarning("Chưa chọn", "Bạn chưa chọn profile.")
        return None
    else:
        index = int(profile_tree.item(selected_items[0], 'values')[0]) - 1
        return profiles[index]


# tạo script
def create_script():
    # Cửa sổ tạo kịch bản
    create_script = tk.Toplevel(root)
    create_script.title("Tạo Kịch Bản")
    create_script.geometry("800x600")
    
    # Chia cửa sổ thành 2 phần: trái và phải
    left_frame = tk.Frame(create_script, width=200, bg='lightgray')
    left_frame.pack(side='left', fill='y')
    
    right_frame = tk.Frame(create_script)
    right_frame.pack(side='right', expand=True, fill='both')
    
    # Các hành động
    actions = [
        "Open URL", "Open Tab", "Close Tab", "Close Window", "Back", "Reload", 
        "Mouse Click Left", "Mouse Click Right", "Scroll", "Enter Text", 
        "Press Key", "Wait Object", "Switch Frame", "Sleep"
    ]
    
    action_var = tk.StringVar()  # Dùng StringVar để lưu hành động đã chọn

    # Tạo RadioButton cho các hành động
    for action in actions:
        radio_button = tk.Radiobutton(left_frame, text=action, variable=action_var, value=action, command=lambda: show_input_fields(action_var.get()))
        radio_button.pack(anchor='w', padx=10, pady=5)

    # Phần bên phải: Chứa các ô nhập liệu và các nút để quản lý sự kiện
    right_top_frame = tk.Frame(right_frame)
    right_top_frame.pack(side='top', fill='x', padx=10, pady=10)
    
    right_bottom_frame = tk.Frame(right_frame)
    right_bottom_frame.pack(side='bottom', fill='x', padx=10, pady=10)
    
    # Các ô nhập liệu (URL, XPath, Time...)
    label_input = tk.Label(right_top_frame, text="Nhập Giá Trị:")
    label_input.pack(pady=5)
    
    value_entry = tk.Entry(right_top_frame, width=40)
    
    # Các ô nhập liệu phụ thuộc vào hành động
    input_label = None
    input_field = None

    def show_input_fields(action):
        nonlocal input_label, input_field

        # Xóa ô nhập liệu trước đó nếu có
        if input_label:
            input_label.destroy()
        if input_field:
            input_field.destroy()

        if action == "Open URL":
            # Hiển thị ô nhập URL
            input_label = tk.Label(right_top_frame, text="Nhập URL:")
            input_label.pack(pady=5)
            input_field = tk.Entry(right_top_frame, width=40)
            input_field.pack(pady=5)

        elif action == "Mouse Click Left" or action == "Mouse Click Right":
            # Hiển thị ô nhập đối tượng CSS/XPath/Full XPath
            input_label = tk.Label(right_top_frame, text="Nhập Đối Tượng (CSS, XPath, Full XPath):")
            input_label.pack(pady=5)
            input_field = tk.Entry(right_top_frame, width=40)
            input_field.pack(pady=5)

        elif action == "Wait Object":
            # Hiển thị ô nhập đối tượng (CSS/XPath/Full XPath)
            input_label = tk.Label(right_top_frame, text="Nhập Đối Tượng (CSS, XPath, Full XPath):")
            input_label.pack(pady=5)
            input_field = tk.Entry(right_top_frame, width=40)
            input_field.pack(pady=5)

        elif action == "Enter Text":
            # Hiển thị ô nhập văn bản
            input_label = tk.Label(right_top_frame, text="Nhập Văn Bản:")
            input_label.pack(pady=5)
            input_field = tk.Entry(right_top_frame, width=40)
            input_field.pack(pady=5)

        elif action == "Scroll":
            # Hiển thị ô nhập số pixel
            input_label = tk.Label(right_top_frame, text="Nhập Số Pixel hoặc Hướng:")
            input_label.pack(pady=5)
            input_field = tk.Entry(right_top_frame, width=40)
            input_field.pack(pady=5)

        elif action == "Press Key":
            # Hiển thị ô nhập phím
            input_label = tk.Label(right_top_frame, text="Nhập Tên Phím (Enter, Esc, v.v):")
            input_label.pack(pady=5)
            input_field = tk.Entry(right_top_frame, width=40)
            input_field.pack(pady=5)

        elif action == "Sleep":
            # Hiển thị ô nhập số giây
            input_label = tk.Label(right_top_frame, text="Nhập Thời Gian Ngủ (Giây):")
            input_label.pack(pady=5)
            input_field = tk.Entry(right_top_frame, width=40)
            input_field.pack(pady=5)

        else:
            # Không hiển thị ô nhập liệu cho các hành động không cần nhập
            pass

    
    # Các nút hành động
    def add_event():
        # Lấy hành động đã chọn từ action_var
        selected_action = action_var.get()  # Đây là hành động người dùng đã chọn từ các RadioButton
        
        if not selected_action:
            messagebox.showwarning("Chưa chọn hành động", "Vui lòng chọn một hành động.")
            return

        # Kiểm tra nếu hành động yêu cầu giá trị và ô nhập liệu có giá trị
        if selected_action not in ["Open Tab", "Close Tab", "Close Window", "Back", "Reload", "Sleep"]:  # Các hành động không yêu cầu giá trị
            event_value = value_entry.get().strip()
            if not event_value:
                messagebox.showwarning("Chưa nhập giá trị", f"Vui lòng nhập giá trị cho hành động {selected_action}.")
                return

        # Lưu lại sự kiện nếu tất cả các kiểm tra đều hợp lệ
        event_value = value_entry.get().strip()
        if not event_value and selected_action not in ["Open Tab", "Close Tab", "Close Window", "Back", "Reload", "Sleep"]:
            messagebox.showwarning("Chưa nhập giá trị", "Vui lòng nhập giá trị cho sự kiện.")
            return
        
        event = {
            "actions": [selected_action],  # Lưu hành động duy nhất đã chọn
            "value": event_value
        }
        events_list.append(event)
        update_event_table()
        value_entry.delete(0, tk.END)

    
    def edit_event():
        selected_item = event_tree.selection()
        if not selected_item:
            messagebox.showwarning("Chưa chọn sự kiện", "Vui lòng chọn sự kiện cần sửa.")
            return
        selected_index = event_tree.index(selected_item[0])
        event = events_list[selected_index]
        
        # Mở cửa sổ sửa sự kiện
        new_value = simpledialog.askstring("Sửa Giá Trị", "Nhập giá trị mới cho sự kiện:", initialvalue=event['value'])
        if new_value:
            event['value'] = new_value
            update_event_table()
    
    def delete_event():
        selected_item = event_tree.selection()
        if not selected_item:
            messagebox.showwarning("Chưa chọn sự kiện", "Vui lòng chọn sự kiện cần xóa.")
            return
        selected_index = event_tree.index(selected_item[0])
        events_list.pop(selected_index)
        update_event_table()
    

    def save_script():
        if not events_list:
            messagebox.showwarning("Không có sự kiện", "Không có sự kiện nào để lưu.")
            return
        
        # Yêu cầu người dùng nhập tên kịch bản
        script_name = simpledialog.askstring("Tên Kịch Bản", "Nhập tên kịch bản để lưu:")
        if script_name:
            # Đảm bảo rằng thư mục "script" tồn tại
            script_directory = 'script'
            if not os.path.exists(script_directory):
                os.makedirs(script_directory)
            
            # Đặt tên tệp và đường dẫn
            file_path = os.path.join(script_directory, f"{script_name}.json")
            
            # Lưu kịch bản dưới dạng JSON
            script_data = []
            for event in events_list:
                script_data.append({
                    "actions": event["actions"],
                    "value": event["value"]
                })
            
            try:
                # Ghi dữ liệu vào tệp JSON
                with open(file_path, 'w') as json_file:
                    json.dump(script_data, json_file, indent=4)
                
                messagebox.showinfo("Thông báo", f"Kịch bản đã được lưu với tên {script_name}.")
            
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu kịch bản: {e}")
    
    
    
    add_btn = tk.Button(right_bottom_frame, text="Thêm Sự Kiện", command=add_event)
    add_btn.grid(row=0, column=0, padx=5, pady=5)
    
    edit_btn = tk.Button(right_bottom_frame, text="Sửa Sự Kiện", command=edit_event)
    edit_btn.grid(row=0, column=1, padx=5, pady=5)
    
    delete_btn = tk.Button(right_bottom_frame, text="Xóa Sự Kiện", command=delete_event)
    delete_btn.grid(row=0, column=2, padx=5, pady=5)
    
    save_btn = tk.Button(right_bottom_frame, text="Lưu Kịch Bản", command=save_script)
    save_btn.grid(row=0, column=3, padx=5, pady=5)
    
    # Bảng hiển thị các lệnh đã tạo
    events_list = []  # Danh sách các sự kiện đã tạo
    
    def update_event_table():
        # Cập nhật bảng sự kiện
        for item in event_tree.get_children():
            event_tree.delete(item)
        for event in events_list:
            event_tree.insert("", "end", values=(', '.join(event['actions']), event['value']))
    
    columns = ('Hành Động', 'Giá Trị')
    event_tree = ttk.Treeview(right_top_frame, columns=columns, show='headings', selectmode="browse")
    event_tree.pack(fill='both', padx=10, pady=10)
    
    event_tree.heading("Hành Động", text="Hành Động")
    event_tree.heading("Giá Trị", text="Giá Trị")
    
    update_event_table()



import tkinter as tk
from tkinter import messagebox
import os
import json

def open_run_script_window():
    # Tạo cửa sổ con
    run_script_window = tk.Toplevel(root)
    run_script_window.title("Chạy Kịch Bản")

    # Chia cửa sổ thành 2 cột
    frame_left = tk.Frame(run_script_window)
    frame_left.pack(side="left", padx=10, pady=10)

    frame_right = tk.Frame(run_script_window)
    frame_right.pack(side="right", padx=10, pady=10)

    # --- Cột bên trái ---
    # Ô nhập số luồng chạy đồng thời
    threads_label = tk.Label(frame_left, text="Số luồng chạy đồng thời:")
    threads_label.pack(padx=5, pady=5)
    threads_entry = tk.Entry(frame_left)
    threads_entry.pack(padx=5, pady=5)

    # Ô nhập số lần chạy chương trình
    runs_label = tk.Label(frame_left, text="Số lần chạy:")
    runs_label.pack(padx=5, pady=5)
    runs_entry = tk.Entry(frame_left)
    runs_entry.pack(padx=5, pady=5)

    # Ô nhập thời gian hẹn giờ chạy chương trình
    delay_label = tk.Label(frame_left, text="Thời gian hẹn giờ (giây):")
    delay_label.pack(padx=5, pady=5)
    delay_entry = tk.Entry(frame_left)
    delay_entry.pack(padx=5, pady=5)

    # --- Cột bên phải ---
    # Listbox hiển thị các file JSON trong thư mục "script"
    listbox_label = tk.Label(frame_right, text="Các file JSON trong thư mục script:")
    listbox_label.pack(padx=5, pady=5)

    listbox = tk.Listbox(frame_right, height=10, width=40)
    listbox.pack(padx=5, pady=5)

    # Đọc các file JSON trong thư mục "script"
    script_folder = 'script'
    if os.path.exists(script_folder):
        json_files = [f for f in os.listdir(script_folder) if f.endswith('.json')]
        for file in json_files:
            listbox.insert(tk.END, file)
    else:
        messagebox.showwarning("Thư mục không tồn tại", f"Không tìm thấy thư mục {script_folder}")

    # --- Danh sách các profile để chọn ---
    profiles_label = tk.Label(frame_right, text="Chọn các profile để chạy kịch bản:")
    profiles_label.pack(padx=5, pady=10)

    profile_checkbuttons = []
    selected_profiles = []

    def select_profile(profile_name, var):
        if var.get() == 1:
            selected_profiles.append(profile_name)
        else:
            selected_profiles.remove(profile_name)

    # Giả sử profiles đã được định nghĩa trước đó
    for profile in profiles:
        var = tk.IntVar()
        cb = tk.Checkbutton(frame_right, text=profile['name'], variable=var,
                            command=lambda name=profile['name'], var=var: select_profile(name, var))
        profile_checkbuttons.append(cb)
        cb.pack(padx=10, pady=5)

    # Hàm chạy kịch bản từ file JSON đã chọn
    def run_script():
        # Kiểm tra nếu người dùng chọn ít nhất một profile
        if not selected_profiles:
            messagebox.showwarning("Chưa chọn profile", "Vui lòng chọn ít nhất một profile.")
            return
        
        # Kiểm tra xem người dùng có chọn file JSON
        selected_file_index = listbox.curselection()
        if not selected_file_index:
            messagebox.showwarning("Chưa chọn file", "Vui lòng chọn một file JSON từ danh sách.")
            return
        
        # Lấy tên file JSON được chọn
        selected_file = listbox.get(selected_file_index[0])
        file_path = os.path.join(script_folder, selected_file)
        
        # Kiểm tra nếu file JSON tồn tại
        if not os.path.exists(file_path):
            messagebox.showwarning("File không tồn tại", f"Không tìm thấy file {selected_file}.")
            return
        
        # Đọc nội dung file JSON
        try:
            with open(file_path, 'r') as f:
                script_content = json.load(f)  # Đọc nội dung file JSON
                print(f"Đã đọc kịch bản từ file {file_path}")
        except json.JSONDecodeError as e:
            messagebox.showerror("Lỗi file JSON", f"Không thể đọc file JSON: {e}")
            return
        except Exception as e:
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi khi đọc file: {e}")
            return

        # Kiểm tra nội dung của script_content
        print("Nội dung của kịch bản:", script_content)

        # Chạy kịch bản cho các profile đã chọn
        for profile_name in selected_profiles:
            profile = next(p for p in profiles if p['name'] == profile_name)
            driver = profile.get('driver')
            if driver:
                try:
                    # Kiểm tra trước khi chạy script
                    print(f"Đang chạy kịch bản cho profile: {profile_name}")
                    driver.execute_script(script_content)
                    print(f"Đã chạy kịch bản cho profile {profile_name}")
                except Exception as e:
                    print(f"Lỗi khi chạy kịch bản cho profile {profile_name}: {e}")
                    messagebox.showerror("Lỗi khi chạy kịch bản", f"Lỗi khi chạy kịch bản cho profile {profile_name}: {e}")
            else:
                print(f"Không tìm thấy driver cho profile {profile_name}")
                messagebox.showwarning("Không có driver", f"Không tìm thấy driver cho profile {profile_name}")
                setup_driver(profile)

    # Nút chạy kịch bản
    run_btn = tk.Button(run_script_window, text="Chạy Kịch Bản", command=run_script)
    run_btn.pack(pady=10)

def execute_script_for_profile(profile, script_content):
    driver = profile.get('driver')
    if driver:
        try:
            driver.execute_script(script_content)
            print(f"Running script for profile {profile['name']}")
        except Exception as e:
            print(f"Error running script for profile {profile['name']}: {e}")

# Tạo frame bên trái
left_frame = tk.Frame(root, width=200, bg='lightgrey')
left_frame.pack(side='left', fill='y')
# Tạo nút Profile
profile_btn = tk.Button(left_frame, text="Profile", command=load_profiles)
profile_btn.pack(pady=50)
# Tạo frame bên phải
right_frame = tk.Frame(root)
right_frame.pack(side='right', expand=True, fill='both')
# Tạo frame cho các nút
button_frame = tk.Frame(right_frame)
button_frame.pack(side='top', pady=10)

add_btn = tk.Button(button_frame, text="Thêm Profile", command=add_profile)
add_btn.grid(row=0, column=0, padx=5)

delete_btn = tk.Button(button_frame, text="Xóa Profile", command=delete_profile)
delete_btn.grid(row=0, column=1, padx=5)
# Tạo nút để mở profile
start_btn = tk.Button(button_frame, text="Khởi động Profile", command=start_selected_profiles)
start_btn.grid(row=0, column=2, padx=5)

edit_multiple_btn = tk.Button(button_frame, text="Thêm proxy cho nhiều profile", command=edit_selected_profiles)
edit_multiple_btn.grid(row=0, column=3, padx=5)
# Tạo nút để đóng profile
close_btn = tk.Button(button_frame, text="Đóng Profile", command=close_selected_profiles)
close_btn.grid(row=0, column=4, padx=5)
# Thêm nút để kích hoạt hàm sắp xếp và thu phóng
arrange_zoom_btn = tk.Button(left_frame, text="Xếp và Thu Phóng", command=arrange_and_zoom_profiles)
arrange_zoom_btn.pack(pady=10)
# Tạo nút mới bên trái để tạo kịch bản và chạy kịch bản
script_btn_frame = tk.Frame(left_frame, bg='lightgrey')
script_btn_frame.pack(side='left', fill='y')

create_script_btn = tk.Button(script_btn_frame, text="Tạo Kịch Bản", command=create_script)
create_script_btn.pack(pady=10)

run_script_btn = tk.Button(script_btn_frame, text="Chạy Kịch Bản", command=open_run_script_window)
run_script_btn.pack(pady=10)

# Cấu hình bảng dạng lưới
cols = ('Số Thứ Tự', 'Tên Profile', 'Fingerprint', 'Proxy', 'Trạng Thái')
profile_tree = ttk.Treeview(right_frame, columns=cols, show='headings', selectmode="browse")
profile_tree = ttk.Treeview(right_frame, columns=cols, show='headings', selectmode="extended")
for col in cols:
    profile_tree.heading(col, text=col)
    profile_tree.column(col, anchor="center")

# Thêm các đường kẻ phân cách
style = ttk.Style()
style.configure("Treeview", rowheight=30, bordercolor="lightgrey", borderwidth=1)



def close_driver(profile):
    driver = profile.get('driver')
    if driver:
        try:
            if driver.service.is_connectable():
                driver.quit()  # Cố gắng đóng driver một cách an toàn
                profile['driver'] = None
                print(f"Profile {profile['name']} closed gracefully.")
            else:
                # Nếu không kết nối, sử dụng taskkill
                pid = driver.service.process.pid
                subprocess.run(["taskkill", "/F", "/PID", str(pid)])
                profile['driver'] = None
                print(f"Closed driver for profile {profile['name']} using taskkill")
        except Exception as e:
            print(f"Error closing driver for profile {profile['name']}: {e}")

# Đảm bảo các hàm gọi đúng cách khi đóng chương trình
def close_main_program(force=False):
    global profiles
    if not force and any(profile.get('driver') for profile in profiles):
        if not messagebox.askyesno("Xác nhận", "Bạn có muốn đóng tất cả profile không?"):
            return

        # Call to close all profiles
        close_all_profiles()
    else:
        # No profiles left open, proceed to close the main program
        root.quit()
        print("Root window destroyed.")

def close_all_profiles():
    global profiles
    for profile in profiles:
        close_driver(profile)
        #time.sleep(0.5)  # Add delay between closing profiles

    #time.sleep(1)  # Ensure all profiles are closed

    # Call the main program closure again
    close_main_program(force=True)

# Đăng ký hàm đóng trình duyệt với atexit
#atexit.register(close_all_created_browsers)
root.protocol("WM_DELETE_WINDOW", close_main_program)


# Hàm để đổi tên profile
def edit_name(event):
    selected_item = profile_tree.selection()[0]
    col = profile_tree.identify_column(event.x)
    index = int(profile_tree.item(selected_item, 'values')[0]) - 1
    profile = profiles[index]

    if col == '#2':  # Đổi tên profile
        new_name = simpledialog.askstring("Tên Profile", "Nhập tên Profile mới:")
        if new_name:
            old_user_data_dir = os.path.join(os.getcwd(), f"profile_{profile['name']}")
            new_user_data_dir = os.path.join(os.getcwd(), f"profile_{new_name}")
            if os.path.exists(old_user_data_dir):
                shutil.move(old_user_data_dir, new_user_data_dir)
            profile["name"] = new_name
            update_profile_tree()
            save_profiles()

    elif col == '#4':  # Đổi proxy
        new_proxy = simpledialog.askstring("Proxy", "Nhập proxy (định dạng: http://username:password@proxy_ip:proxy_port):")
        if new_proxy:
            profile["proxy"] = new_proxy
            # Cập nhật driver với proxy mới
            driver = profile.get('driver')
            if driver:
                driver.quit()  # Đóng driver hiện tại
                profile.pop('driver', None)  # Xóa driver hiện tại khỏi profile
                # Thiết lập lại driver với proxy mới
                setup_driver(profile)
            update_profile_tree()
            save_profiles()

# Liên kết sự kiện click đôi để chỉnh sửa
profile_tree.bind("<Double-1>", edit_name)
profile_tree.pack(expand=True, fill='both')

load_profiles()
root.mainloop()
#----