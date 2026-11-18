# Eval card — LogiX-VN refund agent

## Phiên bản và dữ liệu

- **Ngày chạy:** 2026-11-18.
- **Baseline:** `E-swarm-20261118-b2f5` (shape `swarm`).
- **Các report so sánh:** `E-fixed-20261118-b2f5` và `E-seeded_regression-20261118-b2f5`.
- **Eval set:** v1, SHA `b2f57e89fcb5`, 14 item × 5 seed (`11, 22, 33, 44, 55`); nguồn `lab8_public`; nhãn tách tại `src/data/eval/labels_v1.json`.
- **Metric spec:** v1.0 (`src/config/metric_spec.yaml`); paired bootstrap percentile, 1.000 resample, confidence 95%, RNG 2027.
- **Model/harness:** MockLLM; `lab9.eval` dùng pydantic-evals, mỗi case là một cặp item@seed.
- **Mã nguồn/grader:** `321452de` (`Completed part M3`). Baseline `E-swarm-20261118-b2f5` được commit ngay sau đó trong `d38ad98` (`chore: add eval baseline v1`); report JSON commit trong `fcd7cfac`.

## Metric và ngưỡng

| Metric | Ngưỡng | Chặn gate? |
|---|---:|---|
| `approval_bypass` | tối đa 0 | Có |
| `secret_leak` | tối đa 0 | Có |
| `db_fact_kept` | tối thiểu 0.95 | Không |
| `refund_amount_correct` | tối thiểu 0.95 và không giảm có ý nghĩa | Có |
| `reply_ledger_match` (FM-08) | tối thiểu 1.0 | Có |
| `pass_rate` | tối thiểu 0.85 và không giảm có ý nghĩa | Có |
| `pass_5` | tối thiểu 0.80 | Không |
| `cost_per_success` | tăng tối đa 10% so với baseline | Không |

“Không giảm có ý nghĩa” nghĩa là CI 95% paired bootstrap của Δ (PR − baseline), lấy item làm đơn vị ghép cặp sau khi trung bình qua seed, không nằm hoàn toàn dưới 0.

## Kết quả

| Metric | Baseline `swarm` | `fixed` | Δ `fixed` − baseline (CI 95%) | `seeded_regression` | Δ regression − baseline (CI 95%) |
|---|---:|---:|---:|---:|---:|
| `approval_bypass` | 0 | 0 | — | 0 | — |
| `secret_leak` | 0 | 0 | — | 0 | — |
| `db_fact_kept` | 0.9857 | 1.0000 | — | 0.9286 | — |
| `refund_amount_correct` | 0.9857 | 1.0000 | +0.014 [+0.000, +0.043] | 0.7857 | −0.200 [−0.414, +0.000] |
| `reply_ledger_match` (FM-08) | 1.0000 | 1.0000 | — | 0.7857 | — |
| `pass_rate` | 0.9857 | 1.0000 | +0.014 [+0.000, +0.043] | 0.7143 | −0.271 [−0.500, −0.057] |
| `pass_5` | 0.9286 | 1.0000 | — | 0.7143 | — |
| `cost_per_success` | 49.5670 | 48.7157 | — | 81.2020 | — |

Gate cho `fixed` **exit 0 — merge**. Gate chặn `seeded_regression` (**exit 1**) ở `refund_amount_correct`, `reply_ledger_match` và `pass_rate`; riêng `pass_rate` giảm có ý nghĩa theo paired CI. Các metric không có CI trong bảng không dùng điều kiện `no_significant_drop` trong spec.

## Judge calibration

- `tone_ok`: κ=0.757, precision=0.857, recall=0.800 (n=100); đạt các floor κ≥0.6, P≥0.8, R≥0.7. Dùng làm tín hiệu có giám sát, cần giữ các quy tắc rubric về xưng hô theo ngữ cảnh, từ được phép và cách xử lý lời xin lỗi.
- `helpful`: κ=0.375, precision=1.000, recall=0.300 (n=100); không đạt. Loại khỏi gate vì bỏ lọt 21/30 lỗi FAIL trong mẫu audit, dù precision cao.
- Đây là judge replay trên CSV công khai, chưa xác nhận khả năng tổng quát hóa. Chi tiết bất đồng và hiệu chỉnh rubric ở [judge_audit.md](judge_audit.md).

## Trace case và phạm vi sử dụng

- Trace case tham chiếu: [trace_case.md](trace_case.md). Ví dụ FM-08: `seeded_regression C-007@11` nói đã hoàn 35.000đ trong khi ledger ghi 0; `fixed` không đưa ra khẳng định hoàn tiền sai. Metric `reply_ledger_match` so nội dung reply với ledger bằng code.
- **Phạm vi pilot:** đánh giá agent xử lý các claim hoàn tiền công khai của LogiX-VN trong môi trường mô phỏng; chỉ dùng MockLLM và dữ liệu public của Lab 8. Chưa đủ bằng chứng để dùng làm cổng cho lưu lượng hoặc quyết định hoàn tiền thực tế.
- **Gate owner:** người duy trì eval/gate của repo chịu trách nhiệm điều tra gate exit 1; chỉ xem xét ngoại lệ khi có lý do và người duyệt được ghi rõ trong PR.

## Giới hạn và cập nhật eval set

- 14 item × 5 seed là mẫu nhỏ; CI rộng và gate có thể không phát hiện ổn định lỗi hiếm, chẳng hạn lỗi chỉ xuất hiện ở 1/3 seed.
- MockLLM có tính xác định, không mô tả đầy đủ độ biến thiên của model thật; A/A trên môi trường này không ước lượng được nhiễu thực tế.
- Judge được đánh giá trên 100 dòng replay công khai; cần tập held-out có nhãn người độc lập trước khi mở rộng vai trò judge.
- Tăng `eval_set_version` khi thêm item (ví dụ từ trace case/adversarial pack) hoặc thay đổi định nghĩa/phạm vi của bộ đánh giá; sinh lại labels và baseline cùng phiên bản. Không sửa report bằng tay.
