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

`TC-002-040`–`TC-002-042` giữ kỳ vọng lỗi DB từ Project 2. Nếu thông báo cũ không xuất hiện, kết quả sẽ báo `DB error not reproduced` cùng trạng thái quan sát được. Lỗi chuẩn bị môi trường hiện ở `setUpClass`, còn kiểm tra thất bại hiện theo ID case.

## Kết quả kiểm chứng trên Moodle 5.1.9

Đã chạy toàn bộ 57 ca mỗi level trên Moodle qua Kiri bằng Edge. `TC-002-054` ban đầu gặp lỗi thao tác trình duyệt, sau khi sửa bước rời ô tên đã chạy lại và đạt ở cả hai level. Tổng hợp theo phiên bản runner đã sửa, mỗi level có 52 ca đạt và 5 ca khác với kỳ vọng của Project 2.

- `TC-002-038`–`TC-002-039` yêu cầu lưu khóa 1–2 ký tự. Site hiện bật chính sách mật khẩu nhóm và yêu cầu tối thiểu 8 ký tự.
- `TC-002-040`–`TC-002-042` đều quan sát thấy `Error writing to database` và số nhóm không đổi. Moodle hiện dùng PostgreSQL và thông báo giao diện không khớp chuỗi lỗi cột `enrolmentkey` trong Project 2.

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
