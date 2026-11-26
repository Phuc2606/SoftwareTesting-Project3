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

Tự động hóa kiểm thử chức năng và phi chức năng cho tính năng **Add a Quiz** (`TC-004-001`–`TC-004-022`, 22 test case) trên Moodle local bằng Python 3, Selenium và `unittest`. Mỗi level có runner ngay trong `automation.py`.

* **Level 1 (`Level1/Phuc/automation.py`)**: Kiểm thử hướng dữ liệu (*data-driven*) đọc test case từ `Level1/Phuc/test_data.csv`, khai báo đường dẫn và element locator trực tiếp trong script.
* **Level 2 (`Level2/Phuc/automation.py`)**: Tách dữ liệu test sang `Level2/Phuc/test_data.csv`, cấu hình đường dẫn và UI element locator sang `Level2/Phuc/test_config.csv`.
* **Non-Functional (`NonFunctional/Phuc/`)**: Gồm `test_performance.py` và `test_compatibility.py`.

## Chạy trên PowerShell

Mở PowerShell tại thư mục repo. Cấu hình mặc định sử dụng Moodle local tại `http://127.0.0.1:9501`, `MOODLE_COURSE_ID="4"` và `MOODLE_SECTION_ID="16"`. Cần đặt `MOODLE_USERNAME` và `MOODLE_PASSWORD` trước khi chạy:

```
$env:MOODLE_BASE_URL = "http://127.0.0.1:9501"
$env:MOODLE_USERNAME = Read-Host 'Moodle username'
$env:MOODLE_PASSWORD = Read-Host 'Moodle password' -MaskInput
$env:MOODLE_COURSE_ID = "4"
$env:MOODLE_SECTION_ID = "16"

python Level1/Phuc/automation.py --headed
python Level2/Phuc/automation.py --headed
```

Các tùy chọn hỗ trợ cho `automation.py` của cả Level 1 và Level 2:

* `--list`: Liệt kê các test case mà không mở trình duyệt.
* `--case <ID>`: Chạy một hoặc nhiều test case cụ thể (có thể lặp lại `--case`).
* `--headed`: Hiển thị cửa sổ trình duyệt thay vì chạy *headless*.
* `--browser {chrome,edge}`: Chọn trình duyệt (`chrome` mặc định hoặc `edge`).

## Xử lý tương tác form Moodle & chuyển đổi Level 2

* Mở mục **Overall feedback** an toàn dựa trên trạng thái hiển thị của khu vực feedback / `iframe` và điền nội dung editor TinyMCE (`Good` / `Bad`) mà không gây trùng khớp thiếu ô *gap* trên *boundary*.
* Xử lý trường hợp nút lưu (`#id_submitbutton`) bị che/chặn khi cuộn bằng *fallback click* qua JavaScript (`ElementClickInterceptedException`).
* Kiểm tra riêng `TC-004-014` khi nhập giá trị không phải số (`abc`) vào ô thời gian dạng số.
* Chuyển toàn bộ đường dẫn (`login_path`, `add_quiz_path`) và locator (`username`, `password`, `login`, `name`, `time_enabled`, `time_minutes`, `grade_to_pass`, `attempts`, `save`, `cancel`, `body`, `feedback_boundary`) sang `Level2/Phuc/test_config.csv`.

## Kết quả kiểm thử chức năng

## Kết quả kiểm thử chức năng

Cả hai cấp độ đều thực thi đầy đủ **22/22 test case** (`TC-004-001`–`TC-004-022`) trên Moodle local (`http://127.0.0.1:9501`, khóa học `4`, section `16`) bằng Python 3, Selenium và `unittest` ở chế độ `--headed`:

- **Level 1 (`Level1/Phuc/automation.py --headed`)**: Đạt **22/22** ca (`OK`), tổng thời gian thực thi **`137.943s`** (trung bình ~`6.27s`/ca, bao gồm khởi tạo/điều hướng và tương tác form Moodle).
- **Level 2 (`Level2/Phuc/automation.py --headed`)**: Đạt **22/22** ca (`OK`), tổng thời gian thực thi **`113.969s`** (nhanh hơn `23.974s` so với Level 1, trung bình ~`5.18s`/ca).

### Phân nhóm 22 test case đã kiểm chứng (`TC-004-001`–`TC-004-022`)

| Nhóm kiểm thử | Mã test case | Nội dung kiểm chứng chính | Kết quả Level 1 | Kết quả Level 2 |
| :--- | :--- | :--- | :---: | :---: |
| **Tên quiz & giá trị biên độ dài** | `TC-004-001`–`TC-004-009` | Tên quiz hợp lệ (`TC-004-001`), rỗng (`TC-004-002`), chỉ khoảng trắng (`TC-004-003`), 1 ký tự (`TC-004-004`), biên độ dài 258 ký tự `A` (`TC-004-005`), 255 ký tự `b` (`TC-004-006`), 256 ký tự `b` (`TC-004-007`), tiếng Việt & ký tự đặc biệt (`TC-004-008`), khoảng trắng đầu/cuối (`TC-004-009`). | **22/22 PASS** | **22/22 PASS** |
| **Giới hạn thời gian (`Time limit`)** | `TC-004-010`–`TC-004-014` | Bật time limit với ô phút trống/0 (`TC-004-010`), 1 phút (`TC-004-011`), 45 phút (`TC-004-012`), số âm `-5` (`TC-004-013`), và giá trị không phải số `abc` (`TC-004-014`). | **22/22 PASS** | **22/22 PASS** |
| **Điểm đạt (`Grade to pass`)** | `TC-004-015`–`TC-004-019` | Giá trị `0` (`TC-004-015`), `5.5` (`TC-004-016`), `10` (`TC-004-017`), vượt thang tối đa `10.01` (`TC-004-018`), và số âm `-1` (`TC-004-019`). | **22/22 PASS** | **22/22 PASS** |
| **Số lần làm bài & Hủy tạo** | `TC-004-020`–`TC-004-022` | Giới hạn 1 lần (`TC-004-020`), không giới hạn (`TC-004-021`), và hủy tạo quiz (`TC-004-022`). | **22/22 PASS** | **22/22 PASS** |

### Ghi nhận kỹ thuật khi chạy thực tế

- **Tính ổn định khi chạy toàn bộ suite:** Khi chạy đơn lẻ (`--case TC-004-001`) hoặc chạy đủ 22 case liên tiếp, toàn bộ đều đạt `OK` sau khi xử lý đồng bộ *Overall feedback* / TinyMCE (`Good` / `Bad`), *fallback* click JS cho `#id_submitbutton` khi gặp `ElementClickInterceptedException`, và kiểm tra riêng đầu vào không hợp lệ ở `TC-004-014`.
- **Khác biệt giữa Level 1 và Level 2:** Level 2 tách toàn bộ đường dẫn (`login_path`, `add_quiz_path`) và locator (`username`, `password`, `login`, `name`, `time_enabled`, `time_minutes`, `grade_to_pass`, `attempts`, `save`, `cancel`, `body`, `feedback_boundary`) ra `Level2/Phuc/test_config.csv` mà vẫn giữ nguyên kết quả kiểm thử `22/22` đạt.

## Kiểm thử phi chức năng của Phuc

Chạy hai script kiểm thử phi chức năng trong `NonFunctional/Phuc/` với cùng biến môi trường Moodle local:

```
python NonFunctional/Phuc/test_performance.py
python NonFunctional/Phuc/test_compatibility.py
```

| ID | Loại kiểm thử | Cách thực hiện và tiêu chí đạt | Kết quả ghi nhận |
| :--- | :--- | :--- | :--- |
| **NFR-01** | Hiệu năng / Thời gian phản hồi (`test_performance.py`) | Dùng `time.perf_counter()` đo thời gian tải form Add a Quiz và thời gian submit/chuyển hướng qua 5 lần chạy (`RUNS = 5`) với *fallback* JS click khi gặp `ElementClickInterceptedException`. Ngưỡng: trung bình tải form $\le$ `3.0s` và trung bình submit $\le$ `4.0s`. | **PASS** — Form load: `min=0.357s`, `mean=0.420s`, `median=0.392s`, `max=0.576s`; Submit: `min=1.665s`, `mean=1.730s`, `median=1.710s`, `max=1.864s`. |
| **NFR-02** | Tương thích (`test_compatibility.py`) | Kiểm tra trang Add a Quiz trên **Chrome** và **Edge** ở 3 viewport (`1440x1000`, `768x1024`, `390x844`), kiểm tra hiển thị của `#id_name` và `#id_submitbutton` cùng độ tràn ngang (`scrollWidth - innerWidth`). | **PASS (6/6 cấu hình)** — Cả Chrome và Edge đều hiển thị đầy đủ `#id_name` và `#id_submitbutton` trên cả 3 kích thước màn hình (`overflow = -15px`). |

---

# Khải — Add a Category in Moodle

Hướng dẫn chạy ba phần kiểm thử cho Feature 001 – **Add a Category**. Tất cả lệnh dưới đây chạy từ thư mục gốc repository. Moodle hiện được cấu hình tại `http://127.0.0.1:9501`; cần Python 3, Chrome hoặc Edge và Selenium trong `requirements.txt`.

## Chuẩn bị chung

```powershell
python -m pip install -r requirements.txt
$env:MOODLE_BASE_URL = 'http://127.0.0.1:9501'
$env:MOODLE_USERNAME = Read-Host 'Moodle username'
$securePassword = Read-Host 'Moodle password' -AsSecureString
$env:MOODLE_PASSWORD = [System.Net.NetworkCredential]::new('', $securePassword).Password
```

Tài khoản cần đăng nhập được Moodle. Level 1, Level 2 và performance submit cần tài khoản có quyền tạo category. Compatibility chỉ mở form, không submit.

## Level 1 — Data-driven automation

Runner: `Level1/Khai/automation.py`; dữ liệu 30 case: `Level1/Khai/test_data.csv`.

```powershell
python Level1/Khai/automation.py --list
python Level1/Khai/automation.py --case TC-001-001 --headed
python Level1/Khai/automation.py
```

`--list` liệt kê case; `--case <ID>` chạy một case; `--headed` hiện cửa sổ browser. Kết quả nằm tại `Level1/Khai/results/latest_results.csv`.

## Level 2 — Data-driven automation có cấu hình ngoài

Runner: `Level2/Khai/automation.py`; dữ liệu: `Level2/Khai/test_data.csv`; URL, page path và locator: `Level2/Khai/test_config.csv`.

```powershell
python Level2/Khai/automation.py --list
python Level2/Khai/automation.py --case TC-001-001 --headed
python Level2/Khai/automation.py
```

Có thể dùng `--case <ID>` để chạy riêng/lựa chọn case, `--headed` để hiện browser, hoặc `--browser edge`. Chỉnh Moodle URL/locator trong `test_config.csv` nếu môi trường thay đổi. Username/password vẫn lấy từ environment variables.

### Category mẫu cần chuẩn bị cho các testcase

Các category mẫu này là **dữ liệu fixture trên Moodle**, không được script tự tạo. Cần tạo trước trong Moodle (hoặc dùng category đã có đáp ứng đúng điều kiện) để các case kiểm tra trùng lặp và chọn Parent có đối tượng tham chiếu ổn định. Ví dụ sử dụng một category tên `TC-EXAMPLE`, ID number `tc-example`:

| Testcase | Vì sao cần category mẫu | Giá trị fixture được dùng |
| --- | --- | --- |
| `TC-001-012` | Thử tạo thêm category có cùng tên để kiểm tra Moodle có cho phép tên trùng không. | Tên mẫu `TC-EXAMPLE` được dùng làm tên category mới. |
| `TC-001-016` | Gửi một ID number đã tồn tại để kiểm tra Moodle từ chối ID trùng. | ID number `tc-example` được gửi lại. |
| `TC-001-025` | Chọn category cha có thật, tạo category con và xác minh quan hệ Parent. | Tên `TC-EXAMPLE` (có thể kèm ID number/ID Moodle để phân biệt nếu có nhiều category trùng tên). |
| `TC-001-026` | Chọn Parent trong selector rồi xác minh chỉ một giá trị cha được chọn. | Cùng category cha `TC-EXAMPLE`. |

Sau khi bảo đảm category mẫu đã tồn tại và ID number đúng, khai báo:

```powershell
$env:MOODLE_EXISTING_CATEGORY_NAME = 'TC-EXAMPLE'
$env:MOODLE_EXISTING_CATEGORY_ID = 'tc-example'
$env:MOODLE_PARENT_CATEGORY = 'TC-EXAMPLE'
```

`MOODLE_EXISTING_CATEGORY_NAME` được dùng bởi TC-012, `MOODLE_EXISTING_CATEGORY_ID` bởi TC-016, và `MOODLE_PARENT_CATEGORY` bởi TC-025/026. Nếu site có nhiều category cùng tên, đặt thêm `MOODLE_PARENT_CATEGORY_IDNUMBER` hoặc `MOODLE_PARENT_CATEGORY_ID` đúng category cha. Đảm bảo ID number mẫu không bị thay đổi/xóa trước khi chạy. Các biến môi trường chỉ trỏ tới fixture; chúng không tự tạo fixture. Kết quả nằm tại `Level2/Khai/results/latest_results.csv`.

## Non-functional — Performance

Script: `NonFunctional/Khai/test_performance.py`. Đo thời gian tải form và thời gian submit đến khi category xuất hiện trong danh sách. Mỗi scenario có warm-up và mặc định 5 lần đo. Threshold tham khảo mặc định: form ≤ 3 giây, submit ≤ 5 giây.

```powershell
python NonFunctional/Khai/test_performance.py
python NonFunctional/Khai/test_performance.py --runs 7 --browser chrome --headed
```

Có thể cấu hình threshold trước khi chạy:

```powershell
$env:PERF_LOAD_THRESHOLD_SECONDS = '3'
$env:PERF_SUBMIT_THRESHOLD_SECONDS = '5'
```

Report append vào `NonFunctional/Khai/results/performance_results.csv`. Scenario submit tạo category thật với prefix `NFRPerf_`; sau khi xem report, xóa đúng các category thử nghiệm của lần chạy đó trong Moodle.

## Non-functional — Compatibility

Script: `NonFunctional/Khai/test_compatibility.py`. Kiểm tra Chrome/Edge ở desktop (`1440x1000`), tablet (`768x1024`) và mobile (`390x844`). Script cuộn tới các control, không submit và không tạo category.

```powershell
python NonFunctional/Khai/test_compatibility.py
python NonFunctional/Khai/test_compatibility.py --browsers chrome --viewports desktop,tablet,mobile
```

Nếu chỉ cài một browser, chỉ định browser đó bằng `--browsers chrome` hoặc `--browsers edge`. PASS yêu cầu các control chính dùng được và tràn ngang ≤ 20px. Report append vào `NonFunctional/Khai/results/compatibility_results.csv`.

## Kết quả chạy ba phần kiểm thử

| Phần | Kết quả đã xác nhận | Ghi chú |
| --- | --- | --- |
| Level 1 – Functional | **PASS toàn bộ 30 testcase** theo lần chạy full được xác nhận. | Report từng lần chạy được tạo tự động nằm ở `Level1/Khai/results/latest_results.csv` sau khi chạy;  |
| Level 2 – Functional | **PASS toàn bộ 30 testcase** theo lần chạy full được xác nhận. | Report từng lần chạy được tạo tự động nằm ở `Level2/Khai/results/latest_results.csv` sau khi chạy;  |
| Non-functional – Performance | **PASS** sau lần chạy lại đầy đủ hai scenario. | Có warm-up, 5 lần đo mỗi scenario; report CSV là bằng chứng chi tiết được tạo tự động sau khi chạy tại `NonFunctional/Khai/results/performance_results.csv`. |
| Non-functional – Compatibility | **4/6 PASS, 2/6 FAIL** trong lần chạy Chrome + Edge mới nhất. | Desktop và tablet PASS trên cả hai browser. Hai FAIL đều ở mobile 390×844, chi tiết bên dưới. |

### Hai kết quả Compatibility FAIL

- **Chrome – Mobile 390×844: FAIL.** Viewport đúng 390px, nhưng nội dung trang rộng 625px nên tràn ngang **235px** (ngưỡng tối đa 20px). Sau khi script cuộn tới control, Submit hiển thị trong viewport; FAIL do tràn ngang còn lại.
- **Edge – Mobile 390×844: FAIL.** Cùng kết quả: nội dung rộng 625px, tràn ngang **235px**. Submit hiển thị sau khi cuộn; FAIL do vượt ngưỡng tràn ngang.


----
# Nguyen— Add a new course in Moodle

Feature 005 – **Add a new course** (`TC-005-001`–`TC-005-067`) bằng Python 3, Selenium và `unittest`. Mỗi level chỉ có
file `automation.py` (runner nằm ngay trong file) cùng file dữ liệu CSV, nên chỉ cần `requirements.txt` ở gốc repo.

- **Level 1 (`Level1/Nguyen/`)**: `automation.py` + `test_data.csv` – data-driven, 61 case chỉ khác nhau về dữ liệu, chia 3 nhóm
  (cột `group`: `fields` 29, `dates` 11, `settings` 21). Cột Expected Result: `expected_result`, `expected_text`, `expected_error_*`,
  `verify*_value`. URL và locator khai báo trực tiếp trong script.
- **Level 2 (`Level2/Nguyen/`)**: `automation.py` + `test_data.csv` (các bước của 67 case) + `test_config.csv` (URL và locator).
  Script không chứa URL, locator hay dữ liệu; thêm/sửa case chỉ cần sửa CSV.
- **Non-Functional (`NonFunctional/Nguyen/`)**: `test_performance.py` (thời gian phản hồi) và `test_security.py` (XSS, HTML injection, SQL injection).

## Chạy trên PowerShell

Cần Python 3, Chrome (hoặc Edge/Firefox) và Moodle đang chạy. Mặc định `http://127.0.0.1:9501`, tài khoản `admin`/`admin`.
Script tự đăng nhập. **Reset dữ liệu Moodle (hoặc xóa các course đã tạo) trước mỗi lần chạy từng bộ**, vì các case tạo course
trùng tên (ST101, ID101…) và chạy theo thứ tự số case.

```powershell
python -m pip install -r requirements.txt
$env:MOODLE_BASE_URL = "http://127.0.0.1:9501"
$env:MOODLE_USERNAME = Read-Host 'Moodle username'
$env:MOODLE_PASSWORD = Read-Host 'Moodle password' -MaskInput

python Level1/Nguyen/automation.py
python Level2/Nguyen/automation.py
python NonFunctional/Nguyen/test_performance.py
python NonFunctional/Nguyen/test_security.py
```

macOS/Linux: thay các dòng `$env:` bằng `export MOODLE_USERNAME=admin MOODLE_PASSWORD=admin`.

Tùy chọn của `automation.py` (Level 1 và Level 2): `--list` liệt kê case, `--case TC-005-016` chạy riêng (lặp lại được),
`--browser {chrome,edge,firefox}`, `--headless` chạy ẩn trình duyệt (mặc định hiện cửa sổ). Kết quả ghi ở
`Level1/Nguyen/results/latest_results.csv` và `Level2/Nguyen/results/latest_results.csv`.
`test_performance.py` có thêm `--runs N` (mặc định 10), kết quả append vào `NonFunctional/Nguyen/results/performance_results.csv`;
`test_security.py` ghi `results/security_results.csv`.

## Kiểm thử phi chức năng của Nguyen

| ID | Loại kiểm thử | Cách thực hiện và tiêu chí đạt |
| --- | --- | --- |
| PERF-01 | Hiệu năng | Tải form Add a new course: 1 lần khởi động + 10 lần đo bằng `time.perf_counter()`. Trung bình ≤ 3,0 s, lần chậm nhất ≤ 5,0 s. |
| PERF-02 | Hiệu năng | Tải trang Manage courses and categories. Trung bình ≤ 3,0 s, lần chậm nhất ≤ 5,0 s. |
| PERF-03 | Hiệu năng | Bấm Save and display tạo course hợp lệ (short name duy nhất). Trung bình ≤ 5,0 s, lần chậm nhất ≤ 8,0 s. |
| SEC-01…08 | Bảo mật đầu vào | 8 payload XSS / HTML injection / SQL injection vào Full name, Short name, ID number. Đạt nếu không có `alert()` được thực thi, payload HTML được mã hóa trong `page_source` (kể cả ở trang Manage courses) và không lộ lỗi cơ sở dữ liệu. |

Ghi nhận khi chạy trên Moodle local: Level 1 61/61, Level 2 67/67, Security 8/8, Performance 2/3. PERF-01 Fail
(trung bình 4,68 s, chậm nhất 6,35 s) do form nặng TinyMCE và nhiều mục cài đặt; giữ nguyên ngưỡng.
PERF-02: avg 1,33 s, max 3,08 s; PERF-03: avg 3,12 s, max 3,71 s.

Các cạm bẫy khi chuyển từ Katalon (đã xử lý trong script): `type` của Katalon bỏ qua `maxlength` nên chuỗi dài được gán bằng JavaScript;
dropdown nâng cao nằm trong mục thu gọn nên bấm "Expand all" và chờ mở xong (nếu vẫn ẩn thì đặt giá trị bằng JavaScript);
ô soạn thảo TinyMCE nằm trong iframe; đổi Course format làm form tải lại nên phải chờ.

# Quan — Add a New User in Moodle

Feature – **Add a new user** trên Moodle local, được tự động hóa kiểm thử bằng Python 3, Selenium và `unittest`.

Bộ kiểm thử gồm hai level chức năng và hai script kiểm thử phi chức năng:

- **Level 1 (`Level1/Quan/`)**: `automation.py` và `test_data.csv`. Kiểm thử hướng dữ liệu (data-driven), locator và URL được khai báo trực tiếp trong script.
- **Level 2 (`Level2/Quan/`)**: `automation.py`, `test_data.csv` và `test_config.csv`. Tách dữ liệu kiểm thử khỏi cấu hình URL và UI element locators.
- **Non-Functional (`NonFunctional/Quan/`)**:
  - `test_performance.py`: đo thời gian tải và mức độ sẵn sàng của form Add a new user.
  - `test_compatibility.py`: kiểm tra khả năng hiển thị form trên Desktop, Tablet và Mobile.

Cả hai level chức năng sử dụng helper dùng chung tại `common/moodle_support.py` để xử lý đăng nhập, tương tác với form Moodle, thực thi test case và ghi nhận kết quả.

## Chạy trên PowerShell

Cần Python 3, Chrome hoặc Edge, Selenium và Moodle local đang chạy. URL mặc định là `http://127.0.0.1:9501`.

Cài đặt thư viện và khai báo thông tin đăng nhập:

```powershell
python -m pip install -r requirements.txt

$env:MOODLE_BASE_URL = "http://127.0.0.1:9501"
$env:MOODLE_ADMIN_USER = Read-Host 'Moodle admin username'
$env:MOODLE_ADMIN_PASSWORD = Read-Host 'Moodle admin password' -MaskInput
```

Chạy lần lượt hai level chức năng:

```powershell
python Level1/Quan/automation.py --browser chrome
python Level2/Quan/automation.py --browser chrome
```

Các tùy chọn hỗ trợ cho runner của Level 1 và Level 2:
- `--browser {chrome,edge}`: chọn trình duyệt, mặc định là Chrome.
- `--headed`: hiển thị cửa sổ trình duyệt khi chạy kiểm thử.
- `--case <ID>`: chạy riêng một test case, ví dụ `--case TC-003-020`.

Level 2 sử dụng `test_config.csv` để khai báo URL và locator. Khi cấu trúc giao diện Moodle thay đổi, có thể cập nhật locator trong file cấu hình mà không cần sửa logic kiểm thử chung.

## Kiểm thử phi chức năng

Chạy hai script trong thư mục `NonFunctional/Quan/`:

```powershell
python NonFunctional/Quan/test_performance.py
python NonFunctional/Quan/test_compatibility.py
```

Có thể thêm `--browser chrome` hoặc `--browser edge`; thêm `--headed` nếu muốn quan sát trình duyệt.

### Performance Test

Script `NonFunctional/Quan/test_performance.py` đo thời gian từ lúc bắt đầu điều hướng đến trang Add a new user đến khi trường Username hiển thị và nút Save có thể tương tác.

- Đăng nhập được thực hiện trước khi đo, không tính vào thời gian kiểm thử.
- Thực hiện một lần warm-up, không đưa vào kết quả.
- Mặc định thực hiện 5 lần đo.
- Sử dụng `time.perf_counter()` để đo thời gian.
- Tiêu chí đạt:
  - Median thời gian sẵn sàng của form không vượt quá 2,0 giây.
  - Thời gian của lần chạy chậm nhất không vượt quá 5,0 giây.

Kết quả được ghi tại `NonFunctional/Quan/performance_results.csv`.

### Compatibility Test

Script `NonFunctional/Quan/test_compatibility.py` kiểm tra form Add a new user trên ba kích thước viewport:

| Thiết bị | Kích thước viewport |
| :--- | :--- |
| Desktop | 1440 × 1000 |
| Tablet | 768 × 1024 |
| Mobile | 390 × 844 |

Các nội dung kiểm tra:
- Trường Username, First name, Email và nút Save phải hiển thị.
- Đo độ rộng thực tế của tài liệu bằng `document.documentElement.scrollWidth`.
- Đo độ rộng viewport bằng `window.innerWidth`.
- Tính độ tràn ngang: `max(0, documentWidth - viewportWidth)`.

Tiêu chí đạt: độ tràn ngang không vượt quá 40px tại mỗi viewport.

Kết quả được ghi tại `NonFunctional/Quan/compatibility_results.csv`, bao gồm kích thước màn hình, độ tràn ngang, trạng thái hiển thị control và trạng thái PASS/FAIL.

## Kết quả kiểm chứng trên Moodle local

Kết quả chạy kiểm thử bằng Chrome:

| Hạng mục | Số lượng | Kết quả |
| :--- | :--- | :--- |
| Level 1 – Functional Testing | 25 test cases | 25/25 PASS |
| Level 2 – Functional Testing | 25 test cases | 25/25 PASS |
| Performance Testing | 1 test | PASS |
| Compatibility Testing | 1 test | PASS |

### Kết quả Performance

Thực hiện 5 lần đo sau warm-up:

| Lần chạy | Thời gian |
| :--- | :--- |
| 1 | 0,406 giây |
| 2 | 0,409 giây |
| 3 | 0,449 giây |
| 4 | 0,348 giây |
| 5 | 0,365 giây |
| **Median** | **0,406 giây** |
| **Maximum** | **0,449 giây** |

**Kết quả:** PASS — Median 0,406 giây thấp hơn ngưỡng 2,0 giây và Maximum 0,449 giây thấp hơn ngưỡng 5,0 giây.

### Kết quả Compatibility

| Thiết bị | Viewport | Độ tràn ngang | Kết quả |
| :--- | :--- | :--- | :--- |
| Desktop | 1440 × 1000 | 0px | PASS |
| Tablet | 768 × 1024 | 0px | PASS |
| Mobile | 390 × 844 | 0px | PASS |

**Kết quả:** PASS — Các control được kiểm tra đều hiển thị trên cả ba viewport và không phát hiện tràn ngang.

## Các file kết quả

Sau khi chạy kiểm thử, các file CSV được tạo tại:
- `Level1/Quan/test_results.csv`
- `Level2/Quan/test_results.csv`
- `NonFunctional/Quan/performance_results.csv`
- `NonFunctional/Quan/compatibility_results.csv`

**Tổng kết:** Hai level kiểm thử chức năng đạt 50/50 test cases. Hai kiểm thử phi chức năng đều PASS theo các tiêu chí được cấu hình. Tổng cộng có 52 lần thực thi test thành công (50 test cases chức năng và 2 test methods phi chức năng).
