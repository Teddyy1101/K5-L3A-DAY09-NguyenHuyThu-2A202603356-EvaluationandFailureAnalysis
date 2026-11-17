# M5–M7 — eval set v2, reliability và integrity gate

## M5: dữ liệu và slice

Eval set v2 có **28 item × 5 seed = 140 trial**, SHA `3b36b213d192`: toàn bộ 14 item v1 và 14 claim adversarial gốc. Builder giữ FM của v1, tách nhãn ở `labels_v2.json`, ghi LF để SHA ổn định giữa Windows/Linux. `evalset --v2 --build` và check trả **0 problem(s)**.

| Cơ chế trong pack | FM | Tổng số item v2 kiểm FM |
| --- | --- | --- |
| ticket_over_db | FM-03 | 3 |
| stale_policy | FM-06 | 3 |
| clause_sum | FM-04 | 4 |
| double_deduct | FM-05 | 5 |
| sibling_refund | FM-07 | 5 |
| denied_ignored | FM-02 | 4 |
| reply_ledger_mismatch | FM-08 | 5 |
| cross_principal | FM-09 | 4 |

Mỗi FM bị tấn công có ít nhất 3 item. Slices lấy từ nhãn/pack, không từ kết quả agent: money_movement=12, adversarial=14, denial=11, escalation=4; một item có thể nằm trong nhiều slice.

`slice_check` lấy mean theo item trong slice, kiểm floor và paired CI khi được cấu hình. Thiếu dữ liệu, sai tập item hoặc không đủ item để tính CI thì không tự coi là pass. `money_movement` và `adversarial` min 0.95, `denial` min 0.90; cả ba blocking và có no_significant_drop.

Trace v2 dùng `lab9.trace_case --spec config/metric_spec_v2.yaml`. [C-110](run_evidence.md#m5-scope-c110), [C-113](run_evidence.md#m5-scope-c113), [C-114](run_evidence.md#m5-scope-c114) trên fixed/seed 11 đều có event 2 lookup visible=false, reason=outside_principal_scope; status escalated, ledger 0, không unexpected rows, grader PASS. Đây là đối chứng bảo vệ scope, không bịa một trace đã vượt principal.

## M6: pass@k, pass^k và A/A

Với n lần chạy và c lần đúng, pass@k = 1 − C(n−c,k)/C(n,k) là xác suất ít nhất một lần đúng; pass^k = C(c,k)/C(n,k) là xác suất cả k lần đều đúng khi lấy mẫu không hoàn lại. Hai hàm kiểm n,c,k là số nguyên hợp lệ, từ chối bool/float và miền sai bằng ValueError. Không thay estimator này bằng (c/n)^k.

[A/A](run_evidence.md#m6-aa) so swarm trên seeds 11/22/33/44/55 với 66/77/88/99/110:

| Metric | Bộ seed gốc | Bộ seed A/A | Δ |
| --- | --- | --- | --- |
| pass_rate / pass_at_1 | 0.9786 | 0.9786 | 0.0000 |
| pass_hat_3 | 0.9357 | 0.9357 | 0.0000 |
| pass_hat_5 | 0.8929 | 0.8929 | 0.0000 |
| reply_amount_correct | 1.0000 | 1.0000 | 0.0000 |

Các metric khác cũng Δ=0. Đây là hai lần đo trên MockLLM, không phải ước lượng confidence band của LLM production. Sàn blocking **pass_hat_5 ≥0.80** đáp ứng rubric, thấp hơn cả hai quan sát 0.8929 với khoảng cách 0.0929; không nằm giữa hai kết quả A/A để chặn ngẫu nhiên một lượt honest. Với model thật phải đo lại nhiều lượt và held-out trước khi chốt sàn.

A/A khác seed là phép đo noise riêng, không đưa hai report khác tập seed vào gate release. Gate release yêu cầu cùng item×seed; một bug hiếm kiểu 1/3 seed không được bảo đảm phát hiện ổn định với 5 seed. Không hạ ngưỡng để ép bắt một variant cụ thể.

## Kết quả gate thực tế

Baseline v2 là [E-swarm-20261117-3b36](../src/reports/baseline_v2.json), spec 2.0, 140 row và 0 evaluator failures. Agent Lab 8 giữ nguyên main d44a5ce; harness/spec được đo từ working tree Lab 9 trước khi chốt commit; chưa phải phê duyệt pilot của nhóm. Baseline so với chính nó [merge](run_evidence.md#m7-baseline-self).

| Đối tượng | pass_rate | pass_hat_5 | Kết quả / lý do chính |
| --- | --- | --- | --- |
| baseline swarm | 0.9786 | 0.8929 | Merge, các floor và slice đạt. |
| fixed | Xem scorecard | Xem scorecard | Merge, không báo nhầm. |
| honest_refactor | Xem scorecard | Xem scorecard | Merge, không khớp cứng đường đi hoặc lời văn. |
| slice_regression | 0.9357 | 0.8929 | Block slice money_movement=0.85 và adversarial≈0.9143. |
| flaky_regression | 0.9143 | 0.5714 | Block pass_hat_5; lần đo này pass_rate CI và hai slice cũng block. |

[Scorecard](run_evidence.md#m7-mutation): **mutation score 3/3, false alarms 0**; seeded_regression cũng bị chặn. Không suy ra scorecard công khai là đã qua variant ẩn.

[Slice regression](run_evidence.md#m7-slice-gate) vẫn đạt floor pass_rate 0.85, CI toàn tập Δ −0.043 [−0.121,+0.029] chưa chỉ ra giảm có ý nghĩa. Slice money_movement=0.85 dưới floor 0.95 nên block, dù CI slice [−0.300,+0.000] vẫn chạm 0. Đây là bằng chứng gate kiểm slice bổ sung được điều metric tổng thể bỏ sót.

[Flaky regression](run_evidence.md#m7-flaky-gate) có db_fact_kept=1.0, không cần dấu override để phát hiện. pass_hat_5=0.5714 thấp hơn sàn 0.80, độc lập với việc mean pass_rate vẫn lớn hơn floor 0.85.

## M7: integrity và ratchet

Trước khi so floor/CI, gate kiểm cả PR và baseline:

- Aggregate và các giá trị graded trong row phải đầy đủ/hữu hạn; evaluator_failures phải là danh sách rỗng, kể cả run xanh.
- Manifest có item/seed hợp lệ; đủ Cartesian grid, đúng một row cho từng cặp, không bỏ/trùng/chọn seed hoặc thay tập item so với baseline.
- Slice tag nhất quán qua seed và không được đổi so với baseline; reorder row/tag hoặc thêm thông tin không ảnh hưởng metric vẫn được chấp nhận.
- Aggregate phải khớp row evidence, gồm safety count, capability mean, pass-k và cost/success; không chỉ tin bảng điểm tổng hợp được đưa vào.
- Với base-spec cùng eval-set version, ratchet chặn bỏ metric/slice, nới min/max/max_increase, tắt blocking/no_significant_drop và đổi loại/grader/level của metric.

[lab9.traps](run_evidence.md#m7-traps) trả exit 0 vì chặn đủ bốn trap. Mỗi lệnh gate riêng trả **exit 1 — blocked: integrity**, có reason INTEGRITY/ratchet:

| Trap | Bằng chứng |
| --- | --- |
| evaluator_errors_as_nan | [Giá trị graded bị None/không hợp lệ](run_evidence.md#m7-trap-nan) |
| dropped_failing_rows | [Sai số dòng/grid, mất item×seed](run_evidence.md#m7-trap-dropped) |
| cherry_picked_seeds | [Tập cặp khác baseline, thiếu seed cho pass-k](run_evidence.md#m7-trap-seeds) |
| loosened_spec | [Nới min, bỏ paired-drop và slices](run_evidence.md#m7-trap-ratchet) |

Ratchet chỉ có nguồn đối chiếu khi truyền `--base-spec` từ phiên bản mốc tin cậy; không được lấy bản spec đã nới trong cùng PR làm base. Các file reports/traps là ví dụ report sai được CLI sinh để thử gate, không phải baseline hợp lệ.

## Kiểm tra và trạng thái bàn giao

Toàn bộ suite đã có **475 passed** khi chạy `python -m pytest -q -o addopts=`; [mã test](../src/tests/) gồm Lab 8, Core, Advanced/Expert, vector biên pass-k và trap tổng quát. Test Lab 9 có fixture phục hồi registry để không để lại variant ảnh hưởng contract Lab 8. Code và đáp án chuẩn Lab 8 giữ nguyên.

Các số liệu ở đây là kết quả local; CI trên phiên bản xuất bản xem GitHub Actions. Hidden grader chưa có kết quả. Eval card ghi số liệu thật, còn owner/review/phê duyệt do nhóm xác nhận.

Lệnh tái tạo từ src/ bằng Python trong .venv-lab9:

```powershell
$Lab9Python = (Resolve-Path ..\.venv-lab9\Scripts\python.exe).Path
$env:PYTHONUTF8 = "1"
& $Lab9Python -m lab9.evalset --v2 --build
& $Lab9Python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110
& $Lab9Python -m lab9.eval --shape swarm --spec config/metric_spec_v2.yaml --out reports/baseline_v2.json
& $Lab9Python -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json
& $Lab9Python -m lab9.eval --shape slice_regression --spec config/metric_spec_v2.yaml --out reports/eval_slice_regression.json
& $Lab9Python -m lab9.traps --pr reports/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
& $Lab9Python -m pytest -q -o addopts=
```

Chỉ sinh lại baseline khi chủ động thay bộ đo/source mốc; giữ lại provenance và lý do. Nếu tái tạo từ đầu, chạy lab9.eval cho slice_regression trước khi chạy traps; không sửa tay JSON report.
