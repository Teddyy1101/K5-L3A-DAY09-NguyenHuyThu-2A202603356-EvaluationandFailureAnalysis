# Judge audit M2 — tone đạt ngưỡng, helpful bị loại

## Kết quả hiệu chuẩn

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt cả ba | Dùng có giới hạn cho tone; không dùng chấm số tiền/approval. |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt κ và recall | Loại khỏi release gate; giữ để phân tích lỗi, sửa rubric rồi hiệu chuẩn lại. |

**FAIL là lớp dương:** TP là cả người và judge cùng phát hiện lỗi; FN là lỗi theo nhãn người nhưng judge cho PASS. Không đảo nghĩa lớp dương thành PASS.

| Tiêu chí | TP | FP | FN | TN | Tỉ lệ lỗi judge quan sát | Sensitivity / specificity | Sau Rogan–Gladen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tone_ok | 24 | 4 | 6 | 66 | 28/100 = 0.280 | 24/30 = 0.800; 66/70 ≈ 0.943 | 0.300 |
| helpful | 9 | 0 | 21 | 70 | 9/100 = 0.090 | 9/30 = 0.300; 70/70 = 1.000 | 0.300 |

Precision = TP/(TP+FP), recall = TP/(TP+FN); mẫu số 0 cho precision/recall trả 0. Kappa hiệu chỉnh agreement ngẫu nhiên; khi p_e=1 thì không xác định và calibration phải FAIL. Giá trị dùng so ngưỡng là số chưa làm tròn; bảng chỉ làm tròn để hiển thị.

Rogan–Gladen: `(p_observed + specificity - 1) / (sensitivity + specificity - 1)`, clip [0, 1]. Nếu mẫu số bằng 0, không thể hiệu chỉnh: hàm raise ValueError, CLI báo correction unavailable thay vì bịa tỉ lệ. Các rate ngoài [0, 1] hoặc NaN/inf bị từ chối.

Cả hai tỉ lệ sau hiệu chỉnh bằng 0.300 vì sensitivity/specificity được ước lượng trên chính tập có 30 nhãn FAIL/100. Đây không phải bằng chứng đã ước lượng đúng lỗi production hoặc đã sửa các verdict sai. Rogan–Gladen không cứu một judge có κ/recall không đạt floor.

## Review bất đồng và hành động sửa rubric

PASS/FAIL trong hai cột là nhãn nguyên bản của CSV. Kết luận review phân biệt bằng chứng nhìn thấy với điều chỉ được note cung cấp; không mặc định mọi nhãn người đều đúng và không sửa nhãn công khai để cải thiện điểm.

| # | Case / tiêu chí | Judge | Nhãn người | Nhận định từ bằng chứng hiện có | Hành động sửa rubric / kiểm tra tiếp |
| --- | --- | --- | --- | --- | --- |
| 1 | H-008 / tone: “Em đã hoàn tiền cho anh rồi nha…” | PASS | FAIL | Theo quy ước CS trong note, nhãn người hợp lý: xưng hô suồng sã và “nha” không đúng giọng xử lý khiếu nại. | Nêu rõ đại từ/cách kết câu được chấp nhận, thêm negative example không cho thân thiện bù lỗi xưng hô. |
| 2 | H-017 / tone: “Dạ, bạn ơi… rồi nha.” | PASS | FAIL | Theo note, khách lớn tuổi nên nhãn người hợp lý; chỉ có reply thì chưa tự chứng minh tuổi khách. | Cấp ngữ cảnh đại từ phù hợp; mặc định “anh/chị”, không lấy chữ “Dạ” làm đủ điều kiện PASS. |
| 3 | H-029 / tone: “…không cần nhắn thêm.” | PASS | FAIL | Nhãn người hợp lý: mệnh lệnh đóng kênh hỗ trợ dù đầu câu lịch sự. | Chấm cả câu và tác động với khách; thêm ví dụ có “Dạ/vui lòng” nhưng vẫn FAIL vì áp đặt. |
| 4 | H-042 / tone: thông báo số tiền và thời gian 3–5 ngày | FAIL | PASS | Nhãn người hợp lý cho tone: ngắn nhưng lịch sự, đủ thông tin; không có căn cứ bắt buộc thêm lời xin lỗi. | Không bắt xin lỗi máy móc cho mọi trạng thái; chấm lỗi cụ thể thay vì độ dài. |
| 5 | H-051 / tone: “…đã refund…ạ.” | FAIL | PASS | Theo note, CS LogiX cho phép “refund”, nên nhãn người hợp lý. | Ghi rõ từ vay mượn được cho phép; không phạt chỉ vì một từ tiếng Anh. |
| 6 | H-063 / tone: “…sẽ hoàn thêm…” | PASS | FAIL | Note xác định lời hứa vượt kết quả hệ thống; ưu tiên nhãn người theo rubric hiện tại, nhưng reply riêng không đủ kiểm chứng quyền hoàn thêm. | Tách tiêu chí lời hứa có căn cứ; dùng ledger/policy để kiểm sự thật và quyền hạn bằng code, tránh trộn toàn bộ vào tone. |
| 7 | H-070 / tone: reply kèm emoji cười | PASS | FAIL | Nhãn người hợp lý theo bối cảnh khiếu nại và note về emoji không phù hợp. | Quy định emoji theo bối cảnh, thêm ví dụ tone không chuyên nghiệp dù phần chữ lịch sự. |
| 8 | H-081 / tone: từ chối theo policy, kết câu “ạ” | FAIL | PASS | **Chưa kết luận độc lập.** Note nói nhãn người sai vì đọc nhầm ticket, nhưng reply nhìn riêng lịch sự và CSV không có ticket gốc để kiểm. | Giữ nguyên nhãn phục vụ replay; đưa case tới người gán nhãn với ticket/rubric gốc, tách outcome khỏi tone trước khi sửa nhãn ở version mới. |
| 9 | H-088 / tone: lặp “Dạ, dạ” | FAIL | PASS | Nhãn người hợp lý: lỗi gõ nhẹ không đủ chứng minh giọng bất lịch sự. | Phân biệt lỗi hình thức nhỏ với lỗi tone ảnh hưởng khách; cho phép lỗi gõ không đổi nghĩa. |
| 10 | H-094 / tone: tiếng Việt không dấu | PASS | FAIL | Theo chuẩn ngôn ngữ CS trong note, nhãn người hợp lý; đây là yêu cầu của rubric, không đồng nhất mọi câu không dấu với bất lịch sự. | Viết rõ yêu cầu tiếng Việt có dấu/chất lượng ngôn ngữ thay vì để judge tự đoán tiêu chuẩn. |
| 11 | HL-015 / helpful: reply nói 55.000đ, note ledger 40.000đ | PASS | FAIL | Với ledger trong note, nhãn người đúng về số tiền; judge bị lời lịch sự che lỗi sự thật. | Chấm tiền bằng code so ledger, thêm negative example lịch sự nhưng sai tiền; không cho tone bù lỗi factual. |
| 12 | HL-016 / helpful: lời xin lỗi dài, reply 55.000đ, note ledger 35.000đ | PASS | FAIL | Với ledger trong note, nhãn người đúng; nhiều câu xin lỗi không sửa được số tiền sai. | Rubric đặt factual correctness là điều kiện bắt buộc; rút bớt trọng số độ dài/lời xin lỗi, kết hợp code grader M3. |

## Kết luận

- `tone_ok` đạt floor trên tập public, có thể dùng cho tiêu chí giọng điệu đã mô tả rõ. Vẫn có 6 FN và 4 FP; kết quả không bảo đảm mọi reply tone tốt đều được judge nhận đúng.
- `helpful` bị loại: bỏ sót **21/30 lỗi (70%)**, recall 0.300 và κ 0.375 không đạt. Precision 1.000 chỉ nói các lỗi mà nó đã đánh dấu đều đúng trên tập này, không nói nó tìm đủ lỗi. Không hạ floors để đưa judge này vào gate.
- Tiền, approval và reply so ledger thuộc code grader M3. Các thay đổi rubric ở bảng trên là đề xuất cần kiểm lại trên dữ liệu mới; backend hiện là replay nên sửa rubric không tự tạo ra verdict mới.
- Chưa có held-out với nhãn người mới, dữ liệu người dùng thật hoặc phép đo uncertainty của calibration. Note ledger/tuổi khách là context do CSV cung cấp, không phải một phép kiểm DB mới trong M2. Nhóm cần review/duyệt các kết luận audit khi nộp.
- Không đổi CSV/nhãn/floor để làm đẹp số liệu. Nếu adjudication xác nhận nhãn H-081 sai, sửa trong dataset version mới có nguồn và review, rồi hiệu chuẩn lại; không sửa ngầm tập public v1.

## Kiểm tra triển khai

26 test M2 pass, 2 test bootstrap chưa chọn (M4). Test bổ sung kiểm input lệch độ dài/nhãn sai, P/R mẫu số 0, κ hoàn toàn đồng thuận/bất đồng và κ không xác định, Rogan–Gladen clip/input không hợp lệ, quyết định tone/helpful, constant judge trả FAIL rõ ràng và giá trị sát floor không được làm tròn thành PASS. Không triển khai bootstrap M4 hay pass@k/pass^k M6 trong lượt M2.
