# M4 — paired bootstrap và regression gate v1

## Thiết kế và nguồn baseline

Đơn vị lấy mẫu là **item**, sau khi lấy mean qua 5 seed cho mỗi item; không coi 70 trial là 70 item độc lập. Hai vector được ghép cùng item/cùng thứ tự. `stats.paired_bootstrap` dùng SciPy bootstrap `paired=True`, `method=percentile`, RNG 2027, 1.000 resample, confidence 95%; Δ = mean(PR − baseline). Hai vector giống nhau trả (0, 0, 0). Dữ liệu sai chiều, lệch độ dài, dưới hai item hoặc chứa NaN/inf bị từ chối; số resample và confidence cũng được kiểm tra.

Gate nhận confidence từ spec. Safety vẫn max 0; capability phải đạt floor và CI của Δ không nằm hoàn toàn dưới 0 khi có no_significant_drop. Metric non-blocking chỉ warn, không ngăn merge. Slice/integrity/ratchet M5–M7 còn theo lộ trình, chưa tuyên bố hoàn thành ở M4.

Baseline được sinh bằng `lab9.eval --shape swarm`, không sửa tay report hoặc lấy fixed làm mốc. Agent Lab 8 khớp `origin/main` ở commit `d44a5ce` khi fetch/kiểm tra; harness eval là phần Lab 9 M1–M4 trên nhánh starter/d09. Hai lượt swarm độc lập tạo baseline và PR report có cùng metrics, eval-set SHA `0867206688e3`, spec 1.1, seeds 11/22/33/44/55 và 70 row/report, không evaluator failure.

Đây là baseline local của agent main qua harness Lab 9 đã triển khai. Nhánh main hiện chưa có phần harness M1–M3 này được nhóm review/merge; khi áp dụng quy trình baseline được duyệt trên main, nhóm cần giữ nguồn mốc rõ ràng và sinh lại nếu code/spec/eval set thay đổi. Không mô tả baseline này là một bản harness đã được nhóm phê duyệt trên main.

Eval set/labels và report eval được ghi **LF rõ ràng** trong generator. Nếu để Python Windows sinh CRLF, Git sẽ chuyển sang LF khi commit và SHA trong CI Linux khác baseline. Bản M4 đã build lại và sinh lại report bằng CLI sau khi cố định LF; test xác nhận output builder không chứa CRLF. Đây là chuẩn hóa byte để tái tạo giữa OS, không thay nội dung claim/nhãn hay nới ngưỡng.

[baseline_v1_provenance.json](../src/reports/baseline_v1_provenance.json) lưu commit/tree của agent main, command sinh baseline, fingerprint của source và report. Fingerprint source chuẩn hóa UTF-8/LF để đối chiếu được trên checkout khác OS; không nhận là phê duyệt harness trên main.

## Kết quả chạy thật

| Đối tượng so baseline swarm | pass_rate | Δ pass_rate | CI 95% | Gate |
| --- | --- | --- | --- | --- |
| swarm PR (lượt chạy riêng) | 0.9857 | +0.000 | [+0.000, +0.000] | exit 0 — merge |
| fixed | 1.0000 | +0.014 | [+0.000, +0.043] | exit 0 — merge |
| seeded_regression | 0.7143 | −0.271 | [−0.500, −0.057] | exit 1 — blocked |
| honest_refactor | 1.0000 | +0.014 | [+0.000, +0.043] | exit 0 — merge; cost chỉ warn |

Regression bị block ở `refund_amount_correct`, `reply_amount_correct`, **`pass_rate`**. Dòng verdict thật:

```text
exit 1 — blocked: refund_amount_correct, reply_amount_correct, pass_rate
```

CI pass_rate khớp tham chiếu checkpoint với sai lệch dưới 0.01. `lab9.ci_check` trả `exit 0 — baseline and spec look sound`; kiểm baseline là swarm, cùng SHA/metrics với lượt swarm mới và có metric capability blocking của nhóm được đăng ký.

Output: [swarm gate](run_evidence.md#m4-swarm-gate), [fixed gate](run_evidence.md#m4-fixed-gate), [regression gate](run_evidence.md#m4-regression-gate), [CI sanity](run_evidence.md#m4-ci-check), [refactor gate](run_evidence.md#m4-honest-gate). Report chính: [baseline_v1.json](../src/reports/baseline_v1.json), [eval_pr.json](../src/reports/eval_pr.json), [eval_fixed.json](../src/reports/eval_fixed.json), [eval_seeded_regression.json](../src/reports/eval_seeded_regression.json).

## Kiểm tra và harness map

- Thống kê + test M4: **29 passed**.
- Toàn bộ test Core theo đúng filter của workflow: **97 passed, 342 deselected**.
- Pytest mặc định: **73 passed, 366 deselected**.
- `src/harness_map.yaml` tăng version 1.2 và thêm `sections.eval`, giữ orchestration Lab 8.
- `.venv-lab9/` được ignore; không đưa môi trường cài thư viện lên Git.

Test bổ sung xác nhận paired sampling bằng một độ lệch cố định giữa các item có giá trị nền khác nhau, RNG tái tạo được, input không bị sửa, reject input không hợp lệ, block CI âm dù vẫn trên floor, chặn safety, warn diagnostic, chuyển confidence từ spec và verdict/exit code CLI.
