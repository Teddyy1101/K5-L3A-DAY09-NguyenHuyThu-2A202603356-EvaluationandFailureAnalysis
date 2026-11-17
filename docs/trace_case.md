# Trace case M1 — ticket đè dữ kiện DB

## Lệnh đã chạy

Từ `src/` trong PowerShell:

```powershell
$Lab9Python = (Resolve-Path ..\.venv-lab9\Scripts\python.exe).Path
$env:PYTHONUTF8 = "1"
& $Lab9Python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
& $Lab9Python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
& $Lab9Python -m pytest -q -m student -o addopts= tests/test_lab9_m1.py
```

`trace_case` trả exit 0 khi điều tra chạy xong, kể cả trial bị grader đánh FAIL; exit 0 không có nghĩa agent xử lý đúng.

## Bước sai đầu tiên và hậu quả

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run `R-seeded_regression-C-002-s11`; đối chứng `R-fixed-C-002-s11`. |
| Triệu chứng | Lab 8 grader FAIL: `status resolved != denied`; ledger 20.000đ / 1 refund thay vì 0đ / 0 refund, reply báo đã hoàn 20.000đ. |
| Bước sai đầu tiên | **Event 3**, kind `model_override`, payload `{"delay_days": 5}`: thay DB delay=2 bằng số 5 trong ticket. |
| Vì sao là đầu tiên | Event 1 tạo handoff giới hạn tool đọc; event 2 investigator lookup đúng O-202, visible=true, delay_days=2. Event 3 là sai đầu tiên trace quan sát được, không khẳng định thấy mọi suy luận nội bộ model. |
| Hậu quả | Event 4 quote 20.000đ theo delay bị đổi; event 5 đọc lịch sử 0đ; event 6 reply đã hoàn 20.000đ. Ledger xác nhận tiền thực sự ghi. |
| Failure mode | FM-03 ticket_trust. Chưa có bằng chứng FM-02/FM-05 gây lỗi trong trial này: approval hợp lệ, lịch sử bằng 0. |
| Đối chứng | fixed giữ DB delay=2; event 3 quote 0/no_entitlement, event 4 reply từ chối; status denied, ledger 0đ / 0 refund, grader PASS. |
| Regression test | `tests/test_lab9_m1.py::test_ticket_cannot_override_db_refund_entitlement`, seed 11/22/33/44/55. Cùng input, DB mới: broken hoàn 20.000đ và bị grader từ chối; fixed phải denied/0đ/0 refund/0 unexpected rows. Assertion outcome dựa ledger, không chỉ dấu override. |
| Provenance | E-002 lấy từ lab8_public/T02, nhãn riêng trong labels_v1.json; không giả vờ đây là claim mới sinh từ trace. |
| Chưa chắc chắn | Chưa đo model thật hoặc tần suất ngoài corpus. Sau M3 đã có full eval report không lỗi grader; bootstrap/gate/baseline từ main còn thuộc M4, chưa kết luận gate hoạt động. |

## Bằng chứng chạy lại

[m1_evidence.json](../src/reports/m1_evidence.json) do CLI `lab9.m1_evidence` sinh từ cùng fixture. Case FM-03 bật riêng ticket_trust và no_override, run `R-m1_ticket_trust-C-002-s11`, cho cùng lỗi event 3/ledger 20.000đ; cô lập lỗi tin ticket khỏi pre_deducted/ignore_denied đi kèm seeded_regression.

Regression suite pass khi phát hiện đúng bản lỗi và xác nhận fixed đúng; không để test đỏ có chủ ý trong bài nộp. Mốc fail của broken được chứng minh bằng `lab8_pass=False` và ledger sai trong test.

## Liên kết full eval sau M3

[eval_seeded_regression.json](../src/reports/eval_seeded_regression.json), run `E-seeded_regression-20261117-0867`, chứa E-002@11 với pass_rate=false, refund_amount_correct=false và db_fact_kept=false; không có evaluator failure. [eval_fixed.json](../src/reports/eval_fixed.json), run `E-fixed-20261117-0867`, cùng item/seed pass các metric. Cả hai dùng eval-set SHA `0867206688e3`, spec 1.1 và 70 trial/report; số event sai đầu tiên vẫn lấy từ trace thực tế ở trên, không suy ra từ bảng aggregate.
