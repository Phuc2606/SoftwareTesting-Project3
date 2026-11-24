# Khieu — Create Group in Moodle

Hai level chạy cùng 57 case `TC-002-001`–`TC-002-057` bằng Python 3, Selenium và `unittest`. Mỗi level có runner ngay trong `automation.py`. Cả hai dùng bộ ảnh và file upload tại `Level1/Khieu/fixtures/`, nên giữ nguyên đường dẫn này khi đóng gói. Bốn fixture được trích nguyên byte từ suite Katalon của Project 2.

## Chạy trên PowerShell

Mở PowerShell tại thư mục repo. Cần Chrome hoặc Edge, Moodle đang chạy và một khóa học riêng để test. Lấy ID từ tham số `id` khi mở khóa học, dùng tài khoản có quyền quản lý nhóm. Chạy lần lượt từng level vì suite kiểm tra thay đổi số lượng nhóm.

```powershell
python -m pip install -r requirements.txt
$env:MOODLE_USERNAME = Read-Host 'Moodle username'
$env:MOODLE_PASSWORD = Read-Host 'Moodle password' -MaskInput
$env:MOODLE_COURSE_ID = Read-Host 'Dedicated course ID'
python Level1/Khieu/automation.py --browser edge
python Level2/Khieu/automation.py --browser edge
```

Địa chỉ mặc định là `http://localhost:8082`. Với Level 1 có thể đặt biến `MOODLE_BASE_URL`. Với Level 2, thay URL và locator trong `Level2/Khieu/test_config.csv`. Có thể bỏ `--browser edge` nếu dùng Chrome. Dùng `--list` để kiểm tra danh sách case, `--case TC-002-001` để chạy riêng một case và `--headed` để xem trình duyệt chạy.

Lỗi chuẩn bị môi trường hiện ở `setUpClass`, còn kiểm tra thất bại hiện theo ID case.

## Kết quả kiểm chứng trên Moodle 5.1.9

Lần chạy với kỳ vọng Project 2 trên Moodle qua Kiri bằng Edge cho kết quả 52/57 ca đạt mỗi level, sau khi chạy lại ca `TC-002-054` với bước rời ô tên đã sửa. Năm ca còn lại khác với kỳ vọng Project 2.

Hai level giữ ID và đầu vào của năm ca này. Kết quả mong đợi trong CSV đã được cập nhật cho cấu hình Moodle local:

- `TC-002-038`–`TC-002-039` kiểm tra Moodle báo yêu cầu tối thiểu 8 ký tự và không tạo nhóm. Project 2 mong lưu được khóa 1–2 ký tự.
- `TC-002-040`–`TC-002-042` kiểm tra Moodle báo `Error writing to database` và không tạo nhóm. Project 2 mong chuỗi lỗi cụ thể cho cột `enrolmentkey`. Site hiện dùng PostgreSQL.

Sau khi cập nhật kỳ vọng cho Moodle local, chạy lại toàn bộ bằng Edge cho kết quả **57/57 ca đạt ở mỗi level**.

## Kiểm thử phi chức năng của Member2

Dùng cùng tài khoản và ID khóa học như hai level trên, sau đó chạy:

```powershell
python NonFunctional/Khieu/performance_automation.py --browser edge
python NonFunctional/Khieu/keyboard_automation.py --browser edge
```

| ID | Loại kiểm thử | Cách thực hiện và tiêu chí đạt |
| --- | --- | --- |
| NF-002-001 | Hiệu năng | Sau khi làm nóng ứng dụng, mở trang Groups 7 lần trong cùng phiên đăng nhập. Dùng `time.perf_counter()` đo từ lúc bắt đầu điều hướng tới khi danh sách Groups hiển thị và nút Create group có thể tương tác. Trung vị tối đa 2 giây, lần chậm nhất tối đa 5 giây. |
| NF-002-002 | Khả năng truy cập bằng bàn phím | Dùng Selenium WebDriver gửi Tab và Enter để mở form Create group, gõ tên rồi hủy. Đạt nếu focus tới được từng điều khiển, giá trị nhập đúng và danh sách nhóm không đổi sau khi hủy. |

Hai ca dùng Selenium WebDriver và `unittest`. Ngưỡng thời gian được chọn cho Moodle local, với một phiên đã đăng nhập và không có tải song song. Ca bàn phím kiểm tra luồng mở, nhập tên và hủy.

---

# Phuc — Add a Quiz in Moodle

Tự động hóa kiểm thử chức năng và phi chức năng cho tính năng **Add a Quiz** (`TC-004-001`–`TC-004-022`) trên Moodle local bằng Python 3, Selenium và `unittest`.

- **Level 1 (`Level1/Phuc/automation.py`)**: Kiểm thử hướng dữ liệu (`data-driven`) đọc bộ test case từ `Level1/Phuc/test_data.csv`, khai báo URL và element locator trực tiếp trong script.
- **Level 2 (`Level2/Phuc/automation.py`)**: Tách riêng dữ liệu test (`Level2/Phuc/test_data.csv`) cùng cấu hình URL và UI element locators (`Level2/Phuc/test_config.csv`).
- **Non-Functional (`NonFunctional/Phuc/`)**: Gồm `test_performance.py` và `test_compatibility.py`.

## Chạy trên PowerShell

Cấu hình mặc định sử dụng Moodle local tại `http://127.0.0.1:9501`, `MOODLE_COURSE_ID="4"` và `MOODLE_SECTION_ID="16"`. Cần đặt `MOODLE_USERNAME` và `MOODLE_PASSWORD` trước khi chạy:

```powershell
$env:MOODLE_BASE_URL = "http://127.0.0.1:9501"
$env:MOODLE_USERNAME = Read-Host 'Moodle username'
$env:MOODLE_PASSWORD = Read-Host 'Moodle password' -MaskInput
$env:MOODLE_COURSE_ID = "4"
$env:MOODLE_SECTION_ID = "16"

python Level1/Phuc/automation.py --headed
python Level2/Phuc/automation.py --headed
```

Các tùy chọn hỗ trợ cho `automation.py` của cả Level 1 và Level 2:
- `--list`: Liệt kê các test case mà không mở trình duyệt.
- `--case <ID>`: Chạy một hoặc nhiều test case cụ thể (có thể lặp lại `--case`).
- `--headed`: Hiển thị cửa sổ trình duyệt thay vì chạy headless.
- `--browser {chrome,edge}`: Chọn trình duyệt (`chrome` mặc định hoặc `edge`).

## Xử lý tương tác form Moodle & chuyển đổi Level 2

- Mở mục **Overall feedback** an toàn dựa trên trạng thái hiển thị của khu vực feedback / `iframe` và điền nội dung editor TinyMCE (`Good` / `Bad`) mà không gây trùng khớp thiếu ô gap trên boundary.
- Xử lý trường hợp nút lưu (`#id_submitbutton`) bị che/chặn khi cuộn bằng fallback click qua JavaScript (`ElementClickInterceptedException`).
- Kiểm tra riêng `TC-004-014` khi nhập giá trị không phải số (`abc`) vào ô thời gian dạng số.
- Chuyển toàn bộ đường dẫn (`login_path`, `add_quiz_path`) và locator (`username`, `password`, `login`, `name`, `time_enabled`, `time_minutes`, `grade_to_pass`, `attempts`, `save`, `cancel`, `body`, `feedback_boundary`) sang `Level2/Phuc/test_config.csv`.

## Kiểm thử phi chức năng của Phuc

Chạy hai script kiểm thử phi chức năng trong `NonFunctional/Phuc/` với cùng biến môi trường Moodle local:

```powershell
python NonFunctional/Phuc/test_performance.py
python NonFunctional/Phuc/test_compatibility.py
```

| ID | Loại kiểm thử | Cách thực hiện và tiêu chí đạt | Kết quả ghi nhận |
| --- | --- | --- | --- |
| NFR-01 | Hiệu năng / Thời gian phản hồi (`test_performance.py`) | Dùng `time.perf_counter()` đo thời gian tải form Add a Quiz và thời gian submit/chuyển hướng qua 5 lần chạy (`RUNS = 5`) với fallback JS click khi gặp `ElementClickInterceptedException`. Ngưỡng: trung bình tải form `<= 3.0s` và trung bình submit `<= 4.0s`. | **PASS** — Form load: `min=0.357s`, `mean=0.420s`, `median=0.392s`, `max=0.576s`; Submit: `min=1.665s`, `mean=1.730s`, `median=1.710s`, `max=1.864s`. |
| NFR-02 | Tương thích (`test_compatibility.py`) | Kiểm tra trang Add a Quiz trên **Chrome** và **Edge** ở 3 viewport (`1440x1000`, `768x1024`, `390x844`), kiểm tra hiển thị của `#id_name` và `#id_submitbutton` cùng độ tràn ngang (`scrollWidth - innerWidth`). | **PASS** (6/6 cấu hình) — Cả Chrome và Edge đều hiển thị đầy đủ `#id_name` và `#id_submitbutton` trên cả 3 kích thước màn hình (`overflow = -15px`). |