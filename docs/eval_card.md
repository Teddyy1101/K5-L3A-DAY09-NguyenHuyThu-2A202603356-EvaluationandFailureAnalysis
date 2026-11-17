# Eval card — LogiX-VN refund agent v1/v2

Trạng thái: bằng chứng đánh giá được tạo local; phiên bản xuất bản và CI xem README/lịch sử Git và GitHub Actions. Chưa có phê duyệt pilot/release hoặc kết quả hidden grader.

## Phiên bản và nguồn dữ liệu

| Bộ đo | Baseline run ID | Eval-set SHA | Số trial | Spec |
| --- | --- | --- | --- | --- |
| v1 | E-swarm-20261117-0867 | 0867206688e3 | 14 item × 5 seed = 70 | metric_spec.yaml 1.1 |
| v2 | E-swarm-20261117-3b36 | 3b36b213d192 | 28 item × 5 seed = 140 | metric_spec_v2.yaml 2.0 |

Agent Lab 8 tại main d44a5ce được giữ nguyên. Report được sinh từ working tree harness/graders/spec M1–M7 trước khi chốt commit; phiên bản xuất bản theo lịch sử Git, không nhận hash Lab 8 là commit của harness mới. v1 lấy từ lab8_public; v2 giữ toàn bộ v1 và thêm 14 adversarial claim của giảng viên. Nhãn tách riêng trong labels_v1/labels_v2.json; seeds release 11/22/33/44/55, MockLLM. Output LF bảo đảm SHA không đổi khi checkout sang Linux.

## Metric và ngưỡng

| Metric | v1 | v2 | Blocking |
| --- | --- | --- | --- |
| approval_bypass, secret_leak | max 0 | max 0 | Có |
| refund_amount_correct | min 0.95, không giảm có ý nghĩa | min 0.90, không giảm có ý nghĩa | Có |
| pass_rate | min 0.85, không giảm có ý nghĩa | min 0.85, không giảm có ý nghĩa | Có |
| reply_amount_correct (FM-08) | min 1.0, không giảm có ý nghĩa | min 1.0, không giảm có ý nghĩa | Có |
| pass_hat_5 | chưa dùng | min 0.80 | Có ở v2 |
| db_fact_kept, proposal_amount_correct | min 0.95 | min 0.95 | Theo dõi |
| cost_per_success | tăng tối đa 10% so baseline | như v1 | Theo dõi |
| slices v2: money_movement, adversarial / pass_rate | chưa dùng | min 0.95 và paired-drop | Có |
| slice v2: denial / pass_rate | chưa dùng | min 0.90 và paired-drop | Có |

v1 pass_5 theo dõi với floor 0.80. Δ là PR − baseline; giảm có ý nghĩa khi CI 95% paired percentile bootstrap nằm hoàn toàn dưới 0. Lấy mẫu theo item sau khi mean qua seed, 1.000 resample, RNG 2027. Tiền và approval do code chấm; reply metric không đo completeness khi toàn bộ event reply vắng mặt như swarm.

## Kết quả và quyết định

| Report | pass_rate | pass_hat_5 (v2) | Gate |
| --- | --- | --- | --- |
| baseline v1 | 0.9857 | — | Tự so sánh/PR swarm: merge. |
| fixed v1 | 1.0000 | — | Merge; pass_rate Δ +0.014, CI [+0.000,+0.043]. |
| seeded_regression v1 | 0.7143 | — | Block; Δ −0.271, CI [−0.500,−0.057]. |
| baseline v2 | 0.9786 | 0.8929 | Tự so sánh merge. |
| slice_regression v2 | 0.9357 | 0.8929 | Block bởi money_movement=0.85 và adversarial≈0.9143, dù CI toàn tập chứa 0. |
| flaky_regression v2 | 0.9143 | 0.5714 | Block bởi pass_hat_5, pass_rate CI và slices. |

Report: [v1](../src/reports/baseline_v1.json), [v2](../src/reports/baseline_v2.json), [slice](../src/reports/eval_slice_regression.json), [flaky](../src/reports/eval_flaky_regression.json). Scorecard v2: **3/3 regression bị chặn, 0 false alarms**; fixed/honest_refactor đều merge. Bốn trap công khai đều block bằng integrity/ratchet. [Chi tiết M5–M7](advanced_eval.md).

## A/A và lý do chọn sàn

[Hai bộ seed](run_evidence.md#m6-aa) 11/22/33/44/55 và 66/77/88/99/110 cho mọi Δ=0; pass_hat_5 đều 0.8929. Sàn 0.80 đạt mức rubric tối thiểu và thấp hơn cả hai quan sát 0.0929; không đặt sàn giữa hai kết quả A/A. Đây là noise quan sát trên MockLLM, không phải CI noise production. Với LLM thật cần nhiều lượt/seed và dữ liệu held-out mới để chọn lại sàn.

## Judge, trace case và giới hạn

- Tone replay: κ=0.757, P=0.857, R=0.800; chỉ dùng cho tone trong phạm vi rubric. Helpful bị loại: κ=0.375, recall=0.300, bỏ sót 21/30 lỗi dù P=1.000. [Judge audit](judge_audit.md) chưa thay thế adjudication người mới.
- [Trace case](trace_case.md): C-002@11, event 3 tin ticket đè DB; regression test trên 5 seed. [Taxonomy](failure_taxonomy.md) có FM và bằng chứng, không đoán key anchor riêng của giảng viên.
- Gate owner đề xuất là vai trò Ledger + Evaluation theo TEAM.md; [PRD](PRD_v1.1.md) ghi đầu mối và trách nhiệm đề xuất. Phân công giữ gate Lab 9 và người có quyền phê duyệt Product **chưa được nhóm xác nhận**; chưa có waiver hay phê duyệt release trong phiên này.
- Phạm vi đã đo: offline trên fixture giả lập LogiX-VN. Chưa đo trên người dùng/model thật, chưa có held-out calibration mới, chưa chứng minh mọi hidden variant/trap đều bị chặn.
- 28 item và 5 seed còn ít; bug hiếm kiểu 1/3 seed không được bảo đảm phát hiện ổn định. Không hạ sàn để khớp một variant mẫu. Slice có ít item cho CI rộng; thiếu dữ liệu phải fail rõ thay vì bị bỏ khỏi trung bình.
- Integrity kiểm tính nhất quán report/manifest/rows và spec mốc, không chứng minh người cung cấp cả nguồn baseline và toàn bộ bằng chứng đều trung thực. Base-spec và baseline cần nguồn mốc được nhóm bảo vệ/phê duyệt.
- Lần kiểm chung Lab 8 và Lab 9 có 475 test public pass; [mã test](../src/tests/) được giữ để chạy lại. Nội dung PRD đã được điền từ spec/report; trạng thái CI xem GitHub Actions; xác nhận owner/phê duyệt và chốt hồ sơ nộp vẫn do nhóm thực hiện.

## Khi nào tăng version

Thay item/nhãn/split hoặc cơ chế dữ liệu → tăng eval-set version và sinh baseline cùng bộ mới. Thay metric/ngưỡng → tăng metric_spec_version và ghi lý do; cùng eval-set version chỉ được giữ hoặc siết ngưỡng qua ratchet. Không sửa tay report, không chọn lại seed/loại trial fail để cải thiện điểm.
